"""Falha o processo quando o relatório viola os limites de qualidade."""

import argparse
import json
from pathlib import Path

from app.evaluation.runner import check_regression_gate


def main() -> None:
    """Compara um relatório de avaliação com limites mínimos versionados."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("data/evaluation/regression_thresholds_v1.json"),
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    failures = check_regression_gate(report, thresholds)
    if failures:
        for failure in failures:
            print(f"FALHA: {failure}")
        raise SystemExit(1)
    print("Gate de regressão aprovado.")


if __name__ == "__main__":
    main()
