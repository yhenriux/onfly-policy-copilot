"""Testes dos documentos, metadados e perguntas sintéticas da Fase 1."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.ingestion.chunker import chunk_by_section
from app.ingestion.loaders import load_manifest
from app.ingestion.normalizer import normalize_document


class _QuestionCase(BaseModel):
    case_id: str
    category: Literal["common", "critical", "ambiguous", "unanswered", "adversarial"]
    tenant_id: str
    question: str
    expected_section: str | None
    expected_contains: str | None


class _QuestionCatalog(BaseModel):
    dataset_id: str
    version: str
    description: str
    cases: list[_QuestionCase]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_manifests_define_required_metadata_for_both_tenants() -> None:
    manifests = sorted((_project_root() / "data" / "tenants").glob("*/metadata*.json"))
    documents = [load_manifest(path) for path in manifests]

    assert {document.tenant_id for document in documents} == {
        "aurora_tecnologia",
        "brisa_sistemas",
    }
    assert {(document.tenant_id, document.version) for document in documents} == {
        ("aurora_tecnologia", "v1"),
        ("aurora_tecnologia", "v2"),
        ("brisa_sistemas", "v1"),
    }

    chunks = [
        chunk for document in documents for chunk in chunk_by_section(normalize_document(document))
    ]
    assert all(chunk.tenant_id for chunk in chunks)
    assert all(chunk.document_id for chunk in chunks)
    assert all(chunk.version for chunk in chunks)
    assert all(chunk.section for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert all(chunk.valid_from for chunk in chunks)


def test_question_catalog_covers_all_planned_categories() -> None:
    path = _project_root() / "data" / "evaluation" / "questions_v1.json"
    catalog = _QuestionCatalog.model_validate_json(path.read_text(encoding="utf-8"))

    assert {case.category for case in catalog.cases} == {
        "common",
        "critical",
        "ambiguous",
        "unanswered",
        "adversarial",
    }
    assert len({case.case_id for case in catalog.cases}) == len(catalog.cases)


def test_same_question_has_conflicting_expected_answers() -> None:
    path = _project_root() / "data" / "evaluation" / "questions_v1.json"
    raw_catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog = _QuestionCatalog.model_validate(raw_catalog)
    cases = [
        case
        for case in catalog.cases
        if case.question == "Qual é o limite diário de alimentação em viagem nacional?"
    ]

    assert {case.tenant_id for case in cases} == {"aurora_tecnologia", "brisa_sistemas"}
    assert {case.expected_contains for case in cases} == {"R$ 120,00", "R$ 85,00"}
