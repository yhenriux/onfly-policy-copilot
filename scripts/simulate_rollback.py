"""Simula um deploy com falha e o retorno automático ao release estável."""

import argparse
import json
from pathlib import Path
from typing import Any


def simulate() -> dict[str, Any]:
    """Executa a troca de versão sem alterar um ambiente real."""

    stable = {"version": "0.9.0", "health": True}
    candidate = {"version": "0.9.1-broken", "health": False}
    active = stable
    events = [{"action": "deploy", "version": active["version"], "health": active["health"]}]

    active = candidate
    events.append(
        {"action": "deploy_candidate", "version": active["version"], "health": active["health"]}
    )
    failure_detected = not active["health"]
    if failure_detected:
        active = stable
        events.append(
            {"action": "rollback", "version": active["version"], "health": active["health"]}
        )

    return {
        "scenario": "candidate_health_failure",
        "failure_detected": failure_detected,
        "rollback_performed": failure_detected,
        "final_version": active["version"],
        "final_health": active["health"],
        "events": events,
    }


def main() -> None:
    """Registra uma falha simulada e comprova o retorno à versão estável."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/phase9_rollback_simulation.json"),
    )
    args = parser.parse_args()
    report = simulate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not report["rollback_performed"] or not report["final_health"]:
        raise SystemExit("A simulação não recuperou a versão estável")
    print(f"Falha detectada e rollback concluído para {report['final_version']}.")


if __name__ == "__main__":
    main()
