"""Métricas simples para comparar rankings de recuperação."""

from dataclasses import dataclass
from math import log2

from app.domain.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Resumo da presença e posição das seções esperadas."""

    recall_at_k: float
    mean_reciprocal_rank: float
    ndcg_at_k: float


def relevant_rank(results: list[RetrievedChunk], expected_section: str) -> int | None:
    """Informa a primeira posição da seção esperada, quando ela foi encontrada."""

    return next(
        (rank for rank, chunk in enumerate(results, start=1) if chunk.section == expected_section),
        None,
    )


def calculate_metrics(ranks: list[int | None], *, k: int) -> RetrievalMetrics:
    """Calcula Recall@k e MRR para uma lista de posições esperadas."""

    if not ranks:
        raise ValueError("É necessário informar ao menos um caso de avaliação")
    recalled = sum(rank is not None and rank <= k for rank in ranks)
    reciprocal_sum = sum(1 / rank for rank in ranks if rank is not None)
    ndcg_sum = sum(1 / log2(rank + 1) for rank in ranks if rank is not None and rank <= k)
    return RetrievalMetrics(
        recall_at_k=recalled / len(ranks),
        mean_reciprocal_rank=reciprocal_sum / len(ranks),
        ndcg_at_k=ndcg_sum / len(ranks),
    )
