"""Testes que impedem resultados de uma empresa dentro do contexto de outra."""

from dataclasses import replace
from datetime import date

import pytest

from app.core.exceptions import TenantIsolationError
from app.domain.models import RetrievedChunk
from app.guardrails.tenant_guardrail import TenantGuardedRetriever


def _chunk(tenant_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        tenant_id=tenant_id,
        document_id="policy",
        title="Política",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id=f"chunk_{tenant_id}",
        position=1,
        section="Alimentação",
        text="Regra da empresa.",
        document_hash="document",
        chunk_hash="chunk",
        score=0.9,
    )


class _LeakyRetriever:
    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        return [_chunk("brisa_sistemas")]


class _SafeRetriever(_LeakyRetriever):
    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        return [replace(_chunk(tenant_id), text=f"Regra exclusiva de {tenant_id}")]


def test_post_retrieval_validation_blocks_cross_tenant_payload() -> None:
    retriever = TenantGuardedRetriever(_LeakyRetriever())
    with pytest.raises(TenantIsolationError, match="outro tenant"):
        retriever.search("pergunta", [1.0], tenant_id="aurora_tecnologia", limit=5)


def test_each_authenticated_tenant_receives_only_its_own_payload() -> None:
    retriever = TenantGuardedRetriever(_SafeRetriever())
    aurora = retriever.search("pergunta", [1.0], tenant_id="aurora_tecnologia", limit=5)
    brisa = retriever.search("pergunta", [1.0], tenant_id="brisa_sistemas", limit=5)
    assert {chunk.tenant_id for chunk in aurora} == {"aurora_tecnologia"}
    assert {chunk.tenant_id for chunk in brisa} == {"brisa_sistemas"}
    assert aurora[0].text != brisa[0].text
