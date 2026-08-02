"""Teste do cálculo de percentil usado no benchmark da Fase 4."""

from scripts.evaluate_reranking import _percentile_95


def test_percentile_95_uses_upper_sample() -> None:
    assert _percentile_95([1.0, 2.0, 3.0, 4.0]) == 4.0
