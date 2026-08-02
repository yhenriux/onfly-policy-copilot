"""Testes do reordenador local sem baixar modelo durante a suíte."""

from datetime import date
from math import exp

import pytest

from app.domain.models import RetrievedChunk
from app.retrieval.reranker import LocalCrossEncoderReranker


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
        score=0.1,
    )


class _Model:
    def predict(self, sentences: list[tuple[str, str]], **kwargs: object) -> list[float]:
        assert len(sentences) == 2
        assert kwargs["show_progress_bar"] is False
        return [0.2, 0.9]


class _InvalidModel:
    def predict(self, sentences: list[tuple[str, str]], **kwargs: object) -> list[float]:
        return [0.2]


def test_cross_encoder_reorders_candidates() -> None:
    reranker = LocalCrossEncoderReranker("test", model=_Model())
    result = reranker.rerank(
        "Qual é o prazo?",
        [_chunk("first", "Hotel"), _chunk("second", "Prazo de reembolso")],
        limit=2,
    )
    assert [chunk.chunk_id for chunk in result] == ["second", "first"]
    assert result[0].rerank_rank == 1
    assert result[0].rerank_score == pytest.approx(1 / (1 + exp(-0.9)))


def test_cross_encoder_validates_score_count_and_empty_input() -> None:
    reranker = LocalCrossEncoderReranker("test", model=_InvalidModel())
    assert reranker.rerank("pergunta", [], limit=2) == []
    with pytest.raises(ValueError, match="um score para cada candidato"):
        reranker.rerank("pergunta", [_chunk("a", "A"), _chunk("b", "B")], limit=2)
