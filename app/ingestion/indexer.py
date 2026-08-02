"""Ativa uma versão e grava seus trechos no armazenamento vetorial."""

from app.domain.models import DocumentChunk
from app.retrieval.dense import QdrantVectorStore


def index_chunks(
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
    vector_store: QdrantVectorStore,
) -> None:
    """Desativa versões anteriores e grava a nova versão como ativa."""

    if not chunks:
        raise ValueError("Nenhum trecho foi informado para indexação")
    vector_store.ensure_collection(vector_size=len(embeddings[0]))
    vector_store.deactivate_versions(
        tenant_id=chunks[0].tenant_id,
        document_id=chunks[0].document_id,
    )
    vector_store.upsert(chunks, embeddings)
