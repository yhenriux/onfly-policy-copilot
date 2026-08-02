"""Validação da fronteira entre empresas antes e depois da recuperação."""

from typing import Protocol

from app.core.exceptions import TenantIsolationError
from app.domain.models import RetrievedChunk


class TenantRetriever(Protocol):
    """Contrato mínimo de uma busca que exige contexto de empresa."""

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Busca trechos somente dentro da empresa explicitamente autorizada."""
        ...


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
        """Valida a empresa antes da busca e confere cada resultado depois dela."""
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
