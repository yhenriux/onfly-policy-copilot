"""Fusão de rankings pelo método Reciprocal Rank Fusion, ou RRF."""

from dataclasses import replace

from app.domain.models import RetrievedChunk


def reciprocal_rank_fusion(
    dense: list[RetrievedChunk],
    lexical: list[RetrievedChunk],
    *,
    limit: int,
    rrf_k: int = 60,
    dense_weight: float = 1.0,
    lexical_weight: float = 1.0,
) -> list[RetrievedChunk]:
    """Combina posições; um item bem colocado nas duas buscas recebe mais força."""

    if rrf_k <= 0:
        raise ValueError("rrf_k deve ser maior que zero")
    if dense_weight < 0 or lexical_weight < 0 or dense_weight + lexical_weight == 0:
        raise ValueError("Ao menos um peso do RRF deve ser positivo")

    combined: dict[str, RetrievedChunk] = {}
    scores: dict[str, float] = {}
    for weight, ranking, source in (
        (dense_weight, dense, "dense"),
        (lexical_weight, lexical, "lexical"),
    ):
        for fallback_rank, chunk in enumerate(ranking, start=1):
            key = f"{chunk.tenant_id}:{chunk.document_id}:{chunk.version}:{chunk.chunk_id}"
            rank = chunk.dense_rank if source == "dense" else chunk.lexical_rank
            rank = rank or fallback_rank
            scores[key] = scores.get(key, 0.0) + weight / (rrf_k + rank)
            previous = combined.get(key)
            if previous is None:
                combined[key] = chunk
            elif source == "lexical":
                combined[key] = replace(
                    previous,
                    lexical_score=chunk.lexical_score,
                    lexical_rank=rank,
                )

    ordered = sorted(combined, key=lambda key: (-scores[key], key))[:limit]
    return [replace(combined[key], score=scores[key]) for key in ordered]
