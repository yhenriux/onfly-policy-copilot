"""Coordena busca vetorial, BM25 e fusão RRF."""

from app.domain.models import RetrievedChunk
from app.retrieval.dense import QdrantVectorStore
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.lexical import BM25Retriever


class HybridRetriever:
    """Produz um ranking híbrido mantendo os sinais das duas buscas."""

    def __init__(
        self,
        store: QdrantVectorStore,
        *,
        candidate_limit: int,
        rrf_k: int,
        dense_weight: float,
        lexical_weight: float,
    ) -> None:
        self._store = store
        self._lexical = BM25Retriever(store)
        self._candidate_limit = candidate_limit
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight
        self._lexical_weight = lexical_weight

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Executa as duas buscas dentro do mesmo tenant e combina seus rankings."""

        if not tenant_id.strip():
            raise ValueError("tenant_id é obrigatório em toda busca")
        dense = self._store.search(
            query_vector,
            tenant_id=tenant_id,
            limit=self._candidate_limit,
        )
        lexical = self._lexical.search(
            query,
            tenant_id=tenant_id,
            limit=self._candidate_limit,
        )
        return reciprocal_rank_fusion(
            dense,
            lexical,
            limit=limit,
            rrf_k=self._rrf_k,
            dense_weight=self._dense_weight,
            lexical_weight=self._lexical_weight,
        )
