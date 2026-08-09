"""Testes da geração estruturada, fontes, ausência e fallback."""

import json
import logging
from datetime import date

import pytest

from app.core.exceptions import OllamaUnavailableError
from app.domain.models import RetrievedChunk
from app.domain.schemas import AskRequest, AuthenticatedContext, GenerationOutput
from app.generation.provider import ProviderResult
from app.generation.service import AskService


class _Provider:
    provider_name = "test-provider"
    generation_model = "test-model"
    prompt_version = "test_prompt_v1"

    def __init__(self, output: GenerationOutput | None = None, *, fails: bool = False) -> None:
        self.output = output
        self.fails = fails
        self.generation_calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> ProviderResult:
        self.generation_calls += 1
        if self.fails:
            raise OllamaUnavailableError("temporariamente indisponível", attempts=3)
        assert self.output is not None
        return ProviderResult(
            output=self.output,
            provider=self.provider_name,
            model=self.generation_model,
            prompt_version=self.prompt_version,
            attempts=1,
        )


class _Retriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        return self._results[:limit]


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


def _request() -> AskRequest:
    return AskRequest(question="Quando devo prestar contas?")


def _context() -> AuthenticatedContext:
    return AuthenticatedContext(
        tenant_id="aurora_tecnologia", user_id="user_123", roles=["traveler"]
    )


async def test_service_returns_only_sources_cited_by_structured_output() -> None:
    provider = _Provider(
        GenerationOutput(
            answer="O prazo é de 10 dias úteis.",
            cited_source_positions=[1],
            confidence="high",
        )
    )
    service = AskService(provider=provider, retriever=_Retriever([_chunk()]), retrieval_limit=5)
    response = await service.ask(_request(), _context())
    assert response.answer == "O prazo é de 10 dias úteis."
    assert response.sources[0].chunk_id == "chunk_001"
    assert response.generation.status == "generated"
    assert response.generation.prompt_version == "test_prompt_v1"
    assert response.trace is not None
    assert response.trace.documents[0].document_id == "policy_v1"
    assert {"ollama_embedding", "retrieval", "ollama_generation", "total"} <= set(
        response.trace.timings_ms
    )


async def test_grounded_answer_requires_evidence_above_minimum_score() -> None:
    low_score = _chunk()
    low_score = RetrievedChunk(
        tenant_id=low_score.tenant_id,
        document_id="bagagem",
        title=low_score.title,
        version=low_score.version,
        valid_from=low_score.valid_from,
        valid_until=low_score.valid_until,
        source=low_score.source,
        chunk_id=low_score.chunk_id,
        position=low_score.position,
        section="Bagagem",
        text=low_score.text,
        document_hash=low_score.document_hash,
        chunk_hash=low_score.chunk_hash,
        score=0.2,
    )
    provider = _Provider(
        GenerationOutput(
            answer="Não encontrei uma regra aplicável.",
            cited_source_positions=[],
            confidence="low",
        )
    )
    service = AskService(
        provider=provider,
        retriever=_Retriever([low_score]),
        retrieval_limit=5,
        evidence_min_score=0.5,
    )

    response = await service.ask(AskRequest(question="Qual é a regra de bagagem?"), _context())

    assert response.generation.status == "no_evidence"
    assert provider.generation_calls == 0


async def test_service_log_contains_configuration_but_not_question(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = _Provider(
        GenerationOutput(
            answer="O prazo é de 10 dias úteis.",
            cited_source_positions=[1],
            confidence="high",
        )
    )
    service = AskService(provider=provider, retriever=_Retriever([_chunk()]), retrieval_limit=5)
    with caplog.at_level(logging.INFO, logger="app.generation.service"):
        await service.ask(_request(), _context())

    record = json.loads(caplog.records[-1].message)
    assert record["event"] == "rag_trace"
    assert record["model"] == "test-model"
    assert record["prompt_version"] == "test_prompt_v1"
    assert record["documents"][0]["chunk_id"] == "chunk_001"
    assert "Quando devo solicitar" not in caplog.text


async def test_service_reports_absence_without_calling_generation() -> None:
    provider = _Provider()
    service = AskService(provider=provider, retriever=_Retriever([]), retrieval_limit=5)
    response = await service.ask(_request(), _context())
    assert response.sources == []
    assert response.generation.status == "no_evidence"
    assert provider.generation_calls == 0


async def test_service_preserves_source_when_model_misses_strong_evidence() -> None:
    provider = _Provider(
        GenerationOutput(
            answer="A política não contém essa informação.",
            cited_source_positions=[],
            confidence="low",
        )
    )
    service = AskService(provider=provider, retriever=_Retriever([_chunk()]), retrieval_limit=5)
    response = await service.ask(_request(), _context())
    assert response.sources[0].chunk_id == "chunk_001"
    assert response.generation.status == "degraded"
    assert "Prazo de 10 dias úteis." in response.answer


async def test_service_uses_controlled_fallback_on_generation_failure() -> None:
    provider = _Provider(fails=True)
    service = AskService(provider=provider, retriever=_Retriever([_chunk()]), retrieval_limit=5)
    response = await service.ask(_request(), _context())
    assert response.generation.status == "degraded"
    assert response.generation.attempts == 3
    assert response.confidence == "low"
    assert response.sources[0].chunk_id == "chunk_001"


async def test_service_rejects_source_position_outside_authorized_context() -> None:
    provider = _Provider(
        GenerationOutput(
            answer="Resposta com fonte inventada.",
            cited_source_positions=[2],
            confidence="high",
        )
    )
    service = AskService(provider=provider, retriever=_Retriever([_chunk()]), retrieval_limit=5)
    response = await service.ask(_request(), _context())
    assert response.generation.status == "degraded"
    assert response.confidence == "low"
