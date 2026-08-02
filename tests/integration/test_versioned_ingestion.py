"""Testes integrados de duplicidade, versão ativa e exclusão lógica."""

from datetime import date

import pytest
from qdrant_client import QdrantClient

from app.core.exceptions import DocumentVersionConflictError
from app.domain.models import LoadedDocument
from app.ingestion.pipeline import ingest_document
from app.retrieval.dense import QdrantVectorStore


class _EmbeddingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0, 0.0] for _ in texts]


def _document(version: str, food_limit: int) -> LoadedDocument:
    return LoadedDocument(
        tenant_id="aurora_tecnologia",
        document_id="politica_aurora",
        title="Política Aurora",
        version=version,
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source=f"policy_{version}.md",
        text=(
            "# Política\n\n"
            f"## Alimentação\nLimite de R$ {food_limit}.\n\n"
            "## Reembolso\nPrazo de 10 dias."
        ),
    )


async def test_reingestion_skips_duplicate_and_rejects_changed_same_version() -> None:
    provider = _EmbeddingProvider()
    store = QdrantVectorStore(
        collection_name="versioned_test",
        client=QdrantClient(location=":memory:"),
    )

    try:
        first = await ingest_document(_document("v1", 120), provider=provider, vector_store=store)
        duplicate = await ingest_document(
            _document("v1", 120), provider=provider, vector_store=store
        )

        assert first.status == "indexed"
        assert duplicate.status == "skipped"
        assert store.count() == first.chunks_indexed
        assert provider.calls == 1

        with pytest.raises(DocumentVersionConflictError, match="nova versão"):
            await ingest_document(_document("v1", 130), provider=provider, vector_store=store)
    finally:
        store.close()


async def test_new_version_becomes_active_and_logical_delete_hides_document() -> None:
    provider = _EmbeddingProvider()
    store = QdrantVectorStore(
        collection_name="lifecycle_test",
        client=QdrantClient(location=":memory:"),
    )

    try:
        v1 = await ingest_document(_document("v1", 120), provider=provider, vector_store=store)
        v2 = await ingest_document(_document("v2", 130), provider=provider, vector_store=store)

        assert store.count() == v1.chunks_indexed + v2.chunks_indexed
        assert store.count(active_only=True) == v2.chunks_indexed
        active_results = store.search(
            [1.0, 0.0, 0.0],
            tenant_id="aurora_tecnologia",
            limit=10,
        )
        assert {result.version for result in active_results} == {"v2"}

        affected = store.logical_delete(
            tenant_id="aurora_tecnologia",
            document_id="politica_aurora",
        )
        assert affected == store.count()
        assert (
            store.search(
                [1.0, 0.0, 0.0],
                tenant_id="aurora_tecnologia",
                limit=10,
            )
            == []
        )

        v3 = await ingest_document(_document("v3", 140), provider=provider, vector_store=store)
        reindexed = store.search(
            [1.0, 0.0, 0.0],
            tenant_id="aurora_tecnologia",
            limit=10,
        )
        assert len(reindexed) == v3.chunks_indexed
        assert {result.version for result in reindexed} == {"v3"}
    finally:
        store.close()
