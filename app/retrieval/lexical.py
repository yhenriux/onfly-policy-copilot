"""Busca BM25, que encontra trechos pelas palavras usadas na pergunta."""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from datetime import date
from typing import Any, Protocol

from app.domain.models import RetrievedChunk

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class PayloadSource(Protocol):
    """Fonte que fornece somente trechos ativos da empresa solicitada."""

    def active_payloads(self, *, tenant_id: str) -> list[dict[str, Any]]:
        """Lista apenas textos pesquisáveis da empresa informada."""
        ...


def tokenize(text: str) -> list[str]:
    """Normaliza acentos e separa o texto em palavras comparáveis."""

    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return _TOKEN_PATTERN.findall(without_accents)


def bm25_scores(
    query: str,
    documents: Sequence[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Calcula a relevância lexical de cada documento para uma pergunta."""

    if not documents:
        return []
    document_tokens = [tokenize(document) for document in documents]
    query_tokens = set(tokenize(query))
    average_length = sum(map(len, document_tokens)) / len(document_tokens) or 1.0
    frequencies = [Counter(tokens) for tokens in document_tokens]
    scores = [0.0] * len(documents)

    for term in query_tokens:
        containing = sum(term in frequency for frequency in frequencies)
        inverse_frequency = math.log(1 + (len(documents) - containing + 0.5) / (containing + 0.5))
        for index, frequency in enumerate(frequencies):
            occurrences = frequency[term]
            if not occurrences:
                continue
            length_adjustment = 1 - b + b * len(document_tokens[index]) / average_length
            scores[index] += (
                inverse_frequency
                * (occurrences * (k1 + 1))
                / (occurrences + k1 * length_adjustment)
            )
    return scores


class BM25Retriever:
    """Ordena os trechos ativos de um tenant pela correspondência de palavras."""

    def __init__(self, source: PayloadSource) -> None:
        self._source = source

    def search(self, query: str, *, tenant_id: str, limit: int) -> list[RetrievedChunk]:
        """Pesquisa sem permitir uma consulta sem contexto de empresa."""

        if not tenant_id.strip():
            raise ValueError("tenant_id é obrigatório em toda busca")
        payloads = self._source.active_payloads(tenant_id=tenant_id)
        searchable = [f"{item['title']} {item['section']} {item['text']}" for item in payloads]
        scored = sorted(
            zip(payloads, bm25_scores(query, searchable), strict=True),
            key=lambda item: (-item[1], str(item[0]["chunk_id"])),
        )
        results: list[RetrievedChunk] = []
        for rank, (payload, score) in enumerate(scored[:limit], start=1):
            if score <= 0:
                continue
            results.append(_from_payload(payload, score=score, rank=rank))
        return results


def _from_payload(payload: dict[str, Any], *, score: float, rank: int) -> RetrievedChunk:
    """Converte os metadados persistidos no modelo usado pela aplicação."""

    return RetrievedChunk(
        tenant_id=str(payload["tenant_id"]),
        document_id=str(payload["document_id"]),
        title=str(payload["title"]),
        version=str(payload["version"]),
        valid_from=date.fromisoformat(str(payload["valid_from"])),
        valid_until=(
            date.fromisoformat(str(payload["valid_until"]))
            if payload.get("valid_until") is not None
            else None
        ),
        source=str(payload["source"]),
        chunk_id=str(payload["chunk_id"]),
        position=int(payload["position"]),
        section=str(payload["section"]),
        text=str(payload["text"]),
        document_hash=str(payload["document_hash"]),
        chunk_hash=str(payload["chunk_hash"]),
        score=score,
        lexical_score=score,
        lexical_rank=rank,
    )
