"""Testes das métricas usadas na comparação da Fase 3."""

from math import log2

import pytest

from app.evaluation.retrieval import calculate_metrics


def test_calculate_recall_and_mrr() -> None:
    metrics = calculate_metrics([1, 2, None, 6], k=5)
    assert metrics.recall_at_k == 0.5
    assert metrics.mean_reciprocal_rank == pytest.approx((1 + 0.5 + 1 / 6) / 4)
    assert metrics.ndcg_at_k == pytest.approx((1 + 1 / log2(3)) / 4)


def test_metrics_require_cases() -> None:
    with pytest.raises(ValueError, match="ao menos um caso"):
        calculate_metrics([], k=5)
