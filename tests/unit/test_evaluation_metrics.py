"""Testes das métricas de geração e do gate de regressão."""

from app.evaluation.metrics import term_coverage, token_f1
from app.evaluation.runner import check_regression_gate


def test_generation_metrics_measure_terms_and_relevance() -> None:
    answer = "O limite é de R$ 130,00 por pessoa."
    assert term_coverage(answer, ["R$ 130,00", "por pessoa"]) == 1.0
    assert 0 < token_f1(answer, "Limite de R$ 130,00 por pessoa") <= 1


def test_regression_gate_reports_minimum_and_maximum_failures() -> None:
    report = {"quality": {"score": 0.7}, "safety": {"leakage": 0.1}}
    thresholds = {
        "minimums": {"quality.score": 0.8},
        "maximums": {"safety.leakage": 0.0},
    }
    failures = check_regression_gate(report, thresholds)
    assert len(failures) == 2


def test_regression_gate_accepts_equal_limits() -> None:
    report = {"quality": {"score": 0.8}, "safety": {"leakage": 0.0}}
    thresholds = {
        "minimums": {"quality.score": 0.8},
        "maximums": {"safety.leakage": 0.0},
    }
    assert check_regression_gate(report, thresholds) == []
