"""Testes da combinação reproduzível de rankings."""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.models import RetrievedChunk
from app.retrieval.fusion import reciprocal_rank_fusion


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id="aurora",
        document_id="policy",
        title="Política",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id=chunk_id,
        position=1,
        section="Seção",
        text="Texto",
        document_hash="doc",
        chunk_hash=chunk_id,
        score=1.0,
    )


def test_rrf_rewards_chunk_present_in_both_rankings() -> None:
    shared = _chunk("shared")
    dense = [replace(_chunk("dense"), dense_rank=1), replace(shared, dense_rank=2)]
    lexical = [replace(_chunk("lexical"), lexical_rank=1), replace(shared, lexical_rank=2)]
    result = reciprocal_rank_fusion(dense, lexical, limit=3, rrf_k=60)
    assert result[0].chunk_id == "shared"
    assert result[0].dense_rank == 2
    assert result[0].lexical_rank == 2


def test_rrf_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        reciprocal_rank_fusion([], [], limit=1, rrf_k=0)
