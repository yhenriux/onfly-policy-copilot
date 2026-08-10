"""Testes do Ollama, structured output, timeout e novas tentativas."""

import json
from datetime import date

import httpx
import pytest

from app.core.exceptions import OllamaUnavailableError
from app.domain.models import RetrievedChunk
from app.generation.ollama_provider import OllamaProvider


async def _no_wait(seconds: float) -> None:
    assert seconds >= 0


def _provider(client: httpx.AsyncClient, *, retry_attempts: int = 3) -> OllamaProvider:
    return OllamaProvider(
        base_url="http://ollama.test",
        generation_model="llama3.2:1b",
        embedding_model="all-minilm",
        timeout_seconds=1,
        retry_attempts=retry_attempts,
        retry_backoff_seconds=0.01,
        client=client,
        sleep=_no_wait,
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id="aurora_tecnologia",
        document_id="policy_v1",
        title="Política Aurora",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
        source="policy.md",
        chunk_id="chunk_001",
        position=1,
        section="Reembolso",
        text="Prazo de 10 dias úteis.",
        document_hash="document_hash",
        chunk_hash="chunk_hash",
        score=0.9,
    )


async def test_provider_generates_embeddings_and_structured_answer() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
        body = json.loads(request.content)
        assert body["format"]["properties"]["cited_source_positions"]
        content = {
            "answer": "Prazo de 10 dias úteis.",
            "cited_source_positions": [1],
            "confidence": "high",
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = _provider(client)
    try:
        embeddings = await provider.embed(["Quando solicitar reembolso?"])
        result = await provider.generate("Quando solicitar reembolso?", [_chunk()])
    finally:
        await provider.close()

    assert embeddings == [[0.1, 0.2, 0.3]]
    assert result.output.answer == "Prazo de 10 dias úteis."
    assert result.output.cited_source_positions == [1]
    assert result.prompt_version == "policy_answer_v2"
    assert result.attempts == 1


async def test_provider_normalizes_low_confidence_when_source_is_cited() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        content = {
            "answer": "Prazo de 10 dias úteis.",
            "cited_source_positions": [1],
            "confidence": "low",
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = _provider(client)
    try:
        result = await provider.generate("Quando solicitar reembolso?", [_chunk()])
    finally:
        await provider.close()

    assert result.output.confidence == "medium"


async def test_provider_retries_transient_failure_with_backoff() -> None:
    calls = 0
    waits: list[float] = []

    async def wait(seconds: float) -> None:
        waits.append(seconds)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"embeddings": [[0.1]]})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(
        base_url="http://ollama.test",
        generation_model="llama3.2:1b",
        embedding_model="all-minilm",
        timeout_seconds=1,
        retry_attempts=3,
        retry_backoff_seconds=0.1,
        client=client,
        sleep=wait,
    )
    try:
        result = await provider.embed(["question"])
    finally:
        await provider.close()
    assert result == [[0.1]]
    assert calls == 3
    assert waits == [0.1, 0.2]


async def test_provider_maps_connection_failure_after_retries() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = _provider(client, retry_attempts=2)
    try:
        with pytest.raises(OllamaUnavailableError, match="after 2 attempts") as error:
            await provider.embed(["question"])
    finally:
        await provider.close()
    assert error.value.attempts == 2


async def test_provider_retries_timeout() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("demorou demais", request=request)
        return httpx.Response(200, json={"embeddings": [[0.2]]})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = _provider(client, retry_attempts=2)
    try:
        result = await provider.embed(["question"])
    finally:
        await provider.close()
    assert result == [[0.2]]
    assert calls == 2
