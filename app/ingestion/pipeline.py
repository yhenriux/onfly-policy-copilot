"""Coordena as etapas que transformam um documento em trechos pesquisáveis."""

from app.core.exceptions import DocumentVersionConflictError
from app.domain.models import IngestionResult, LoadedDocument
from app.ingestion.chunker import ChunkingConfig, chunk_by_section
from app.ingestion.embeddings import EmbeddingProvider, embed_chunks
from app.ingestion.indexer import index_chunks
from app.ingestion.normalizer import normalize_document
from app.retrieval.dense import QdrantVectorStore


async def ingest_document(
    document: LoadedDocument,
    *,
    provider: EmbeddingProvider,
    vector_store: QdrantVectorStore,
    chunking_config: ChunkingConfig | None = None,
) -> IngestionResult:
    """Executa a carga completa e evita duplicar uma versão já conhecida."""

    normalized = normalize_document(document)
    existing_hashes = vector_store.version_hashes(
        tenant_id=normalized.tenant_id,
        document_id=normalized.document_id,
        version=normalized.version,
    )
    if normalized.document_hash in existing_hashes:
        return IngestionResult(
            status="skipped",
            tenant_id=normalized.tenant_id,
            document_id=normalized.document_id,
            version=normalized.version,
            document_hash=normalized.document_hash,
            chunks_indexed=0,
        )
    if existing_hashes:
        raise DocumentVersionConflictError(
            "A versão informada já existe com outro conteúdo. Crie uma nova versão."
        )

    chunks = chunk_by_section(normalized, chunking_config)
    embeddings = await embed_chunks(chunks, provider)
    index_chunks(chunks, embeddings, vector_store)
    return IngestionResult(
        status="indexed",
        tenant_id=normalized.tenant_id,
        document_id=normalized.document_id,
        version=normalized.version,
        document_hash=normalized.document_hash,
        chunks_indexed=len(chunks),
    )
