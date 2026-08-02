"""Testes de redundância e orçamento do contexto enviado ao LLM."""

from datetime import date

from app.domain.models import RetrievedChunk
from app.retrieval.context import select_context


def _chunk(chunk_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id="aurora",
        document_id="policy",
        title="Política",
        version="v2",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id=chunk_id,
        position=1,
        section="Seção",
        text=text,
        document_hash="document",
        chunk_hash=chunk_id,
        score=1.0,
    )


def test_context_removes_redundancy_and_respects_budget() -> None:
    first = _chunk("first", "prazo para reembolso em oito dias úteis")
    duplicate = _chunk("duplicate", "prazo para reembolso em oito dias úteis")
    useful = _chunk("useful", "nota fiscal obrigatória")
    too_large = _chunk("large", "x" * 100)

    result = select_context(
        [first, duplicate, useful, too_large],
        limit=5,
        max_characters=len(first.text) + len(useful.text),
        redundancy_threshold=0.8,
    )
    assert [chunk.chunk_id for chunk in result] == ["first", "useful"]


def test_empty_texts_are_considered_redundant() -> None:
    result = select_context(
        [_chunk("first", ""), _chunk("second", "")],
        limit=2,
        max_characters=200,
        redundancy_threshold=0.8,
    )
    assert [chunk.chunk_id for chunk in result] == ["first"]
