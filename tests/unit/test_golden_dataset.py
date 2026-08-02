"""Teste da estrutura e cobertura do golden dataset versionado."""

from pathlib import Path

from app.evaluation.dataset import load_golden_dataset


def test_golden_dataset_covers_all_required_categories() -> None:
    dataset = load_golden_dataset(Path("data/evaluation/golden_dataset_v1.json"))
    assert dataset.version == "v1"
    assert len(dataset.cases) == 10
    assert {case.category for case in dataset.cases} == {
        "answerable",
        "unanswered",
        "adversarial",
    }
    answerable = [case for case in dataset.cases if case.category == "answerable"]
    assert all(case.expected_answer for case in answerable)
    assert all(case.expected_section for case in answerable)
