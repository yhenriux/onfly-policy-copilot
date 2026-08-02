"""Testes das respostas frequentes montadas a partir dos chunks recuperados."""

from datetime import date

import pytest

from app.domain.models import RetrievedChunk
from app.generation.grounded_answers import build_grounded_answer, rewrite_frequent_question


def _chunk(document: str, section: str, text: str, position: int) -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id="aurora_tecnologia",
        document_id=f"aurora_{document}",
        title="Documento recuperado",
        version="v1",
        valid_from=date(2026, 7, 1),
        valid_until=None,
        source="knowledge.md",
        chunk_id=f"chunk_{position}",
        position=position,
        section=section,
        text=text,
        document_hash="document_hash",
        chunk_hash=f"hash_{position}",
        score=0.95,
    )


@pytest.mark.parametrize(
    ("question", "document", "expected"),
    [
        ("Posso despachar uma mala?", "bagagem", "23 kg"),
        ("Quanto posso gastar com hotel?", "hospedagem", "R$ 480,00"),
        ("Como peço o reembolso?", "reembolso", "8 dias úteis"),
        ("Posso usar aplicativo de transporte?", "transporte_local", "aeroporto"),
    ],
)
def test_main_question_uses_retrieved_evidence(
    question: str,
    document: str,
    expected: str,
) -> None:
    evidence = _chunk(document, "Regra principal", f"Orientação com {expected}.", 1)
    answer = build_grounded_answer(question, [evidence])

    assert answer is not None
    assert expected in answer.answer
    assert answer.chunks == [evidence]


def test_grounded_answer_ignores_document_from_another_subject() -> None:
    unrelated = _chunk("hospedagem", "Limite", "R$ 480,00", 1)

    assert build_grounded_answer("Posso despachar mala?", [unrelated]) is None


def test_frequent_question_is_expanded_without_changing_unknown_question() -> None:
    assert "hospedagem" in rewrite_frequent_question("Quanto posso gastar com hotel?")
    assert rewrite_frequent_question("Qual é a política sobre eventos?") == (
        "Qual é a política sobre eventos?"
    )
