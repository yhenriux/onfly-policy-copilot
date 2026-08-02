"""Proteção contra instruções maliciosas encontradas dentro dos documentos."""

import re

from app.domain.models import RetrievedChunk
from app.guardrails.input_guardrail import normalize_security_text

_DOCUMENT_ATTACK_PATTERNS = (
    r"ignore (previous|all|the) instructions",
    r"ignore (as |todas as )?instrucoes",
    r"desconsidere (as )?instrucoes",
    r"system prompt",
    r"voce agora e",
    r"you are now",
    r"revele (o )?segredo",
)


def contains_malicious_instruction(text: str) -> bool:
    """Sinaliza frases típicas que tentam transformar dado em comando."""

    normalized = normalize_security_text(text)
    return any(re.search(pattern, normalized) for pattern in _DOCUMENT_ATTACK_PATTERNS)


def keep_safe_document_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Remove do contexto qualquer chunk com instrução maliciosa conhecida."""

    return [chunk for chunk in chunks if not contains_malicious_instruction(chunk.text)]
