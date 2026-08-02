"""Testes do versionamento do release e da simulação de rollback."""

import json
from pathlib import Path

from app.core.config import Settings
from app.generation.prompts import PROMPT_VERSION
from scripts.simulate_rollback import simulate


def test_release_manifest_matches_application_and_prompt() -> None:
    release = json.loads(Path("release.json").read_text(encoding="utf-8"))

    assert release["application_version"] == Settings().app_version
    assert release["prompt_version"] == PROMPT_VERSION


def test_failed_candidate_returns_to_stable_release() -> None:
    result = simulate()

    assert result["failure_detected"] is True
    assert result["rollback_performed"] is True
    assert result["final_version"] == "0.9.0"
    assert result["final_health"] is True
