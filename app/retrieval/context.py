"""Seleção de contexto útil, sem repetição excessiva e dentro do limite."""

from app.domain.models import RetrievedChunk
from app.retrieval.lexical import tokenize


def _similarity(first: str, second: str) -> float:
    """Mede a parcela de palavras compartilhadas entre dois trechos."""

    first_tokens = set(tokenize(first))
    second_tokens = set(tokenize(second))
    if not first_tokens and not second_tokens:
        return 1.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def select_context(
    ranked: list[RetrievedChunk],
    *,
    limit: int,
    max_characters: int,
    redundancy_threshold: float,
) -> list[RetrievedChunk]:
    """Seleciona trechos distintos sem ultrapassar o orçamento de caracteres."""

    selected: list[RetrievedChunk] = []
    used_characters = 0
    for chunk in ranked:
        if len(selected) >= limit:
            break
        if any(
            _similarity(chunk.text, current.text) >= redundancy_threshold for current in selected
        ):
            continue
        chunk_size = len(chunk.text)
        if used_characters + chunk_size > max_characters:
            continue
        selected.append(chunk)
        used_characters += chunk_size
    return selected
