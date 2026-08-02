"""Testes da busca por palavras BM25."""

import pytest

from app.retrieval.lexical import BM25Retriever, bm25_scores, tokenize


class _Source:
    def active_payloads(self, *, tenant_id: str) -> list[dict[str, object]]:
        assert tenant_id == "aurora_tecnologia"
        base = {
            "tenant_id": tenant_id,
            "document_id": "policy",
            "title": "Política",
            "version": "v2",
            "valid_from": "2026-01-01",
            "valid_until": None,
            "source": "policy.md",
            "position": 1,
            "document_hash": "doc",
            "chunk_hash": "chunk",
            "is_active": True,
            "is_deleted": False,
        }
        return [
            {**base, "chunk_id": "hotel", "section": "Hotel", "text": "Limite de hotel R$ 480"},
            {
                **base,
                "chunk_id": "food",
                "section": "Alimentação",
                "text": "Diária de alimentação R$ 130",
            },
        ]


def test_tokenize_normalizes_accents() -> None:
    assert tokenize("Alimentação DIÁRIA") == ["alimentacao", "diaria"]


def test_bm25_prioritizes_matching_terms() -> None:
    scores = bm25_scores("reembolso comprovante", ["hotel e diária", "reembolso com comprovante"])
    assert scores[1] > scores[0]


def test_bm25_retriever_requires_tenant_and_returns_matching_chunk() -> None:
    retriever = BM25Retriever(_Source())
    result = retriever.search("alimentação", tenant_id="aurora_tecnologia", limit=2)
    assert result[0].chunk_id == "food"
    assert result[0].lexical_rank == 1

    with pytest.raises(ValueError, match="tenant_id é obrigatório"):
        retriever.search("alimentação", tenant_id="", limit=2)
