"""Monta o acesso ao Qdrant conforme a execução local ou em containers."""

from app.core.config import Settings
from app.retrieval.dense import QdrantVectorStore


def build_vector_store(settings: Settings) -> QdrantVectorStore:
    """Mantém a escolha do modo do Qdrant em um único lugar."""

    if settings.qdrant_mode == "server":
        api_key = (
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key is not None
            else None
        )
        return QdrantVectorStore(
            collection_name=settings.qdrant_collection,
            url=str(settings.qdrant_url),
            api_key=api_key,
        )
    return QdrantVectorStore(
        collection_name=settings.qdrant_collection,
        path=settings.qdrant_path,
    )
