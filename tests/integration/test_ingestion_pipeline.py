"""Teste integrado de divisão, embeddings e persistência no Qdrant."""

import json
from datetime import date

import httpx
from qdrant_client import QdrantClient

from app.domain.models import LoadedDocument
from app.generation.ollama_provider import OllamaProvider
from app.ingestion.pipeline import ingest_document
from app.retrieval.dense import QdrantVectorStore


async def test_pipeline_embeds_and_persists_document_chunks() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        embeddings = [[1.0, 0.0, 0.0] for _ in payload["input"]]
        return httpx.Response(200, json={"embeddings": embeddings})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    provider = OllamaProvider(
        base_url="http://ollama.test",
        generation_model="llama3.2:1b",
        embedding_model="all-minilm",
        timeout_seconds=1,
        client=client,
    )
    store = QdrantVectorStore(
        collection_name="ingestion_test",
        client=QdrantClient(location=":memory:"),
    )
    document = LoadedDocument(
        tenant_id="aurora_tecnologia",
        document_id="policy_v1",
        title="Política Aurora",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
        source="policy.md",
        text="# Política\n\n## Alimentação\nLimite de R$ 120.\n\n## Reembolso\n10 dias.",
    )

    try:
        result = await ingest_document(document, provider=provider, vector_store=store)

        assert result.status == "indexed"
        assert result.chunks_indexed == 2
        assert store.count() == 2
    finally:
        await provider.close()
        store.close()
