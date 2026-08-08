"""Extração determinística de relações simples e auditáveis das políticas."""

import re

from app.domain.models import DocumentChunk
from app.knowledge_graph.models import KnowledgeGraphDocument, KnowledgeGraphFact

_AMOUNT_PATTERN = re.compile(
    r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:[.,][0-9]{1,2})?|[0-9]+(?:[.,][0-9]{1,2})?)",
    re.IGNORECASE,
)
_TOPIC_TERMS = (
    "alimentação",
    "hospedagem",
    "passagem",
    "transporte",
    "reembolso",
    "bagagem",
    "hotel",
    "carro",
    "viagem",
)


def _topic(chunk: DocumentChunk) -> str:
    haystack = f"{chunk.section} {chunk.text}".lower()
    return next((term for term in _TOPIC_TERMS if term in haystack), "política")


def _phrases(text: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    lowered = text.lower()
    values: list[str] = []
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            fragment = text[index : index + 180].split(".", 1)[0].strip()
            values.append(fragment)
    return tuple(dict.fromkeys(values))


def _amount(text: str) -> float | None:
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1)
    if "," in raw and "." in raw:
        normalized = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        normalized = raw.replace(",", ".")
    elif raw.count(".") == 1 and len(raw.rsplit(".", 1)[1]) == 2:
        normalized = raw
    else:
        normalized = raw.replace(".", "")
    return float(normalized)


def extract_document_graph(chunks: list[DocumentChunk]) -> KnowledgeGraphDocument:
    """Extrai apenas fatos explicáveis; o texto completo continua no Qdrant."""

    if not chunks:
        raise ValueError("Não é possível criar um grafo sem chunks")
    first = chunks[0]
    facts = tuple(
        KnowledgeGraphFact(
            tenant_id=chunk.tenant_id,
            document_id=chunk.document_id,
            version=chunk.version,
            chunk_id=chunk.chunk_id,
            section=chunk.section,
            topic=_topic(chunk),
            statement=chunk.text[:500],
            conditions=_phrases(chunk.text, ("quando", "em viagem", "durante")),
            exceptions=_phrases(chunk.text, ("exceto", "exceção", "não se aplica")),
            amount=_amount(chunk.text),
            currency="BRL" if "R$" in chunk.text else None,
        )
        for chunk in chunks
    )
    return KnowledgeGraphDocument(
        tenant_id=first.tenant_id,
        document_id=first.document_id,
        title=first.title,
        version=first.version,
        valid_from=first.valid_from.isoformat(),
        valid_until=first.valid_until.isoformat() if first.valid_until else None,
        facts=facts,
    )
