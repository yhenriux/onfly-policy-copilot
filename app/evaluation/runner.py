"""Gate que compara um relatório com limites mínimos versionados."""

from typing import Any


def metric_value(report: dict[str, Any], path: str) -> float:
    """Lê uma métrica por caminho como `retrieval.reranked.mrr`."""

    value: Any = report
    for part in path.split("."):
        value = value[part]
    return float(value)


def check_regression_gate(
    report: dict[str, Any], thresholds: dict[str, dict[str, float]]
) -> list[str]:
    """Devolve cada limite violado; lista vazia significa gate aprovado."""

    failures: list[str] = []
    for path, minimum in thresholds.get("minimums", {}).items():
        actual = metric_value(report, path)
        if actual < minimum:
            failures.append(f"{path}: {actual:.4f} abaixo do mínimo {minimum:.4f}")
    for path, maximum in thresholds.get("maximums", {}).items():
        actual = metric_value(report, path)
        if actual > maximum:
            failures.append(f"{path}: {actual:.4f} acima do máximo {maximum:.4f}")
    return failures
