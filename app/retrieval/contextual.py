"""Coordena recuperação híbrida, re-ranking e seleção de contexto."""

from time import perf_counter

from app.domain.models import RetrievedChunk
from app.observability.metrics import operational_metrics
from app.observability.tracing import record_timing
from app.retrieval.context import select_context
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalCrossEncoderReranker


class ContextualRetriever:
    """Entrega somente os melhores candidatos não redundantes ao modelo gerador."""

    def __init__(
        self,
        hybrid: HybridRetriever,
        reranker: LocalCrossEncoderReranker,
        *,
        rerank_top_n: int,
        max_context_characters: int,
        redundancy_threshold: float,
    ) -> None:
        self._hybrid = hybrid
        self._reranker = reranker
        self._rerank_top_n = rerank_top_n
        self._max_context_characters = max_context_characters
        self._redundancy_threshold = redundancy_threshold

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Recupera mais candidatos, reordena e monta o contexto final."""

        candidates = self._hybrid.search(
            query,
            query_vector,
            tenant_id=tenant_id,
            limit=self._rerank_top_n,
        )
        reranking_started = perf_counter()
        reranked = self._reranker.rerank(query, candidates, limit=self._rerank_top_n)
        reranking_ms = (perf_counter() - reranking_started) * 1_000
        record_timing("reranking", reranking_ms)
        operational_metrics.observe_latency("reranking", reranking_ms)
        return select_context(
            reranked,
            limit=limit,
            max_characters=self._max_context_characters,
            redundancy_threshold=self._redundancy_threshold,
        )
