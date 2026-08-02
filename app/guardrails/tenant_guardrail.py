"""Validação da fronteira entre empresas antes e depois da recuperação."""

from typing import Protocol

from app.core.exceptions import TenantIsolationError
from app.domain.models import RetrievedChunk


class TenantRetriever(Protocol):
    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]: ...


class TenantGuardedRetriever:
    """Exige tenant na entrada e confere o tenant de cada resultado."""

    def __init__(self, retriever: TenantRetriever) -> None:
        self._retriever = retriever

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        if not tenant_id.strip():
            raise TenantIsolationError("A recuperação exige um tenant autenticado")
        chunks = self._retriever.search(
            query,
            query_vector,
            tenant_id=tenant_id,
            limit=limit,
        )
        if any(chunk.tenant_id != tenant_id for chunk in chunks):
            raise TenantIsolationError("A recuperação devolveu dados de outro tenant")
        return chunks
