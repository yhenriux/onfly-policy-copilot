"""Teste da coordenação entre recuperação, re-ranking e contexto."""

from datetime import date
from typing import cast

from app.domain.models import RetrievedChunk
from app.retrieval.contextual import ContextualRetriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalCrossEncoderReranker


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id="aurora",
        document_id="policy",
        title="Política",
        version="v2",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id=chunk_id,
        position=1,
        section="Seção",
        text=f"Texto distinto {chunk_id}",
        document_hash="document",
        chunk_hash=chunk_id,
        score=1.0,
    )


class _Hybrid:
    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        assert tenant_id == "aurora"
        assert limit == 3
        return [_chunk("a"), _chunk("b"), _chunk("c")]


class _Reranker:
    def rerank(
        self, query: str, candidates: list[RetrievedChunk], *, limit: int
    ) -> list[RetrievedChunk]:
        return list(reversed(candidates))[:limit]


def test_contextual_retriever_returns_final_context_limit() -> None:
    retriever = ContextualRetriever(
        cast(HybridRetriever, _Hybrid()),
        cast(LocalCrossEncoderReranker, _Reranker()),
        rerank_top_n=3,
        max_context_characters=1_000,
        redundancy_threshold=0.9,
    )
    result = retriever.search("pergunta", [1.0], tenant_id="aurora", limit=2)
    assert [chunk.chunk_id for chunk in result] == ["c", "b"]
