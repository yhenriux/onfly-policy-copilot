"""Geração dos vetores numéricos usados na busca por significado."""

from collections.abc import Awaitable
from typing import Protocol

from app.domain.models import DocumentChunk


class EmbeddingProvider(Protocol):
    """Operação necessária para transformar textos em vetores."""

    def embed(self, texts: list[str]) -> Awaitable[list[list[float]]]:
        """Devolve um vetor para cada texto sem impor um fornecedor específico."""
        ...


async def embed_chunks(
    chunks: list[DocumentChunk],
    provider: EmbeddingProvider,
) -> list[list[float]]:
    """Gera vetores incluindo título e seção para preservar o contexto."""

    texts = [f"{chunk.title}\nSeção: {chunk.section}\n{chunk.text}" for chunk in chunks]
    embeddings = await provider.embed(texts)
    if len(embeddings) != len(chunks) or not embeddings or not embeddings[0]:
        raise ValueError("O provedor não devolveu um vetor válido para cada trecho")
    return embeddings
