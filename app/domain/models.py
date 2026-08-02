"""Modelos que representam documentos e trechos de políticas."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    """Documento lido do arquivo, antes da limpeza do texto."""

    tenant_id: str
    document_id: str
    title: str
    version: str
    valid_from: date
    valid_until: date | None
    source: str
    text: str


@dataclass(frozen=True, slots=True)
class NormalizedDocument:
    """Documento com texto limpo e uma assinatura calculada pelo conteúdo."""

    tenant_id: str
    document_id: str
    title: str
    version: str
    valid_from: date
    valid_until: date | None
    source: str
    text: str
    document_hash: str


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """Trecho rastreável que será armazenado para pesquisa."""

    tenant_id: str
    document_id: str
    title: str
    version: str
    valid_from: date
    valid_until: date | None
    source: str
    chunk_id: str
    position: int
    section: str
    text: str
    document_hash: str
    chunk_hash: str


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Trecho encontrado, com os sinais usados para explicar seu ranking."""

    tenant_id: str
    document_id: str
    title: str
    version: str
    valid_from: date
    valid_until: date | None
    source: str
    chunk_id: str
    position: int
    section: str
    text: str
    document_hash: str
    chunk_hash: str
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Resultado da carga de uma versão de documento."""

    status: Literal["indexed", "skipped"]
    tenant_id: str
    document_id: str
    version: str
    document_hash: str
    chunks_indexed: int
