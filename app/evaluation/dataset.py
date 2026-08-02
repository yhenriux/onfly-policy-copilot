"""Leitura e validação do golden dataset versionado."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GoldenCase(BaseModel):
    """Caso com pergunta, comportamento esperado e fonte correta."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: Literal["answerable", "unanswered", "adversarial"]
    tenant_id: str
    question: str
    expected_answer: str | None
    expected_terms: list[str] = Field(default_factory=list)
    expected_document_id: str | None
    expected_version: str | None
    expected_section: str | None


class GoldenDataset(BaseModel):
    """Conjunto imutável de referência para comparar versões do sistema."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    version: str
    description: str
    cases: list[GoldenCase] = Field(min_length=1)


def load_golden_dataset(path: Path) -> GoldenDataset:
    """Lê o JSON e falha cedo quando algum caso está incompleto."""

    return GoldenDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
