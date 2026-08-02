"""Testes do armazenamento e do filtro de busca por empresa."""

from datetime import date

import pytest
from qdrant_client import QdrantClient

from app.domain.models import DocumentChunk
from app.retrieval.dense import QdrantVectorStore


def test_qdrant_persists_payload_and_filters_by_tenant() -> None:
    client = QdrantClient(location=":memory:")
    store = QdrantVectorStore(collection_name="test_policies", client=client)
    chunks = [
        DocumentChunk(
            tenant_id="aurora_tecnologia",
            document_id="aurora_v1",
            title="Política Aurora",
            version="v1",
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 12, 31),
            source="aurora.md",
            chunk_id="chunk_aurora",
            position=1,
            section="Reembolso",
            text="Prazo de 10 dias.",
            document_hash="document_hash_aurora",
            chunk_hash="chunk_hash_aurora",
        ),
        DocumentChunk(
            tenant_id="brisa_sistemas",
            document_id="brisa_v1",
            title="Política Brisa",
            version="v1",
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 12, 31),
            source="brisa.md",
            chunk_id="chunk_brisa",
            position=1,
            section="Reembolso",
            text="Prazo de 20 dias.",
            document_hash="document_hash_brisa",
            chunk_hash="chunk_hash_brisa",
        ),
    ]

    try:
        store.ensure_collection(vector_size=3)
        store.upsert(chunks, [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        results = store.search(
            [1.0, 0.0, 0.0],
            tenant_id="aurora_tecnologia",
            limit=5,
        )

        assert store.count() == 2
        assert len(results) == 1
        assert results[0].tenant_id == "aurora_tecnologia"
        assert results[0].document_id == "aurora_v1"
        assert results[0].version == "v1"
        assert results[0].valid_until == date(2026, 12, 31)
        assert results[0].document_hash == "document_hash_aurora"

        store.reset()
        assert not client.collection_exists("test_policies")
    finally:
        store.close()


def test_dense_search_rejects_missing_tenant() -> None:
    store = QdrantVectorStore(
        collection_name="test_policies", client=QdrantClient(location=":memory:")
    )
    try:
        with pytest.raises(ValueError, match="tenant_id é obrigatório"):
            store.search([1.0], tenant_id=" ", limit=1)
    finally:
        store.close()
