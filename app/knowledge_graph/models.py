"""Contratos do grafo de conhecimento, independentes do Neo4j."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeGraphFact:
    """Regra extraída de um chunk e vinculada à evidência original."""

    tenant_id: str
    document_id: str
    version: str
    chunk_id: str
    section: str
    topic: str
    statement: str
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    amount: float | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeGraphDocument:
    """Documento e fatos que serão persistidos como nós e relações."""

    tenant_id: str
    document_id: str
    title: str
    version: str
    valid_from: str
    valid_until: str | None
    extractor_version: str
    facts: tuple[KnowledgeGraphFact, ...]
