"""Testes da limpeza de texto e do hash usado para detectar mudanças."""

from datetime import date

from app.domain.models import LoadedDocument
from app.ingestion.normalizer import normalize_document, normalize_text


def _loaded_document(text: str) -> LoadedDocument:
    return LoadedDocument(
        tenant_id="aurora_tecnologia",
        document_id="politica_aurora",
        title="Política Aurora",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        text=text,
    )


def test_normalize_text_removes_noise_without_removing_sections() -> None:
    text = "# Política\r\n\r\n\r\n## Reembolso\r\nPrazo   de  10 dias.  "

    normalized = normalize_text(text)

    assert normalized == "# Política\n\n## Reembolso\nPrazo de 10 dias."


def test_equivalent_texts_generate_the_same_document_hash() -> None:
    first = normalize_document(_loaded_document("## Reembolso\nPrazo  de 10 dias."))
    second = normalize_document(_loaded_document("## Reembolso\r\nPrazo de 10 dias.  "))

    assert first.text == second.text
    assert first.document_hash == second.document_hash
