"""Reordenação local dos candidatos usando pergunta e trecho juntos."""

from collections.abc import Sequence
from dataclasses import replace
from importlib import import_module
from math import exp
from typing import Protocol, cast

from app.domain.models import RetrievedChunk


class PairScorer(Protocol):
    """Contrato mínimo de um modelo que pontua pares de textos."""

    def predict(self, sentences: list[tuple[str, str]], **kwargs: object) -> Sequence[float]:
        """Atribui uma pontuação a cada par de pergunta e evidência."""
        ...


class LocalCrossEncoderReranker:
    """Usa um CrossEncoder local e carrega o modelo somente quando necessário."""

    def __init__(self, model_name: str, *, model: PairScorer | None = None) -> None:
        self._model_name = model_name
        self._model = model

    def _get_model(self) -> PairScorer:
        if self._model is None:
            cross_encoder = import_module("sentence_transformers").CrossEncoder
            self._model = cast(PairScorer, cross_encoder(self._model_name))
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Pontua cada candidato e devolve o ranking mais relevante primeiro."""

        if not candidates:
            return []
        pairs = [(query, f"{chunk.title}\n{chunk.section}\n{chunk.text}") for chunk in candidates]
        raw_scores = self._get_model().predict(pairs, show_progress_bar=False)
        logits = [float(score) for score in raw_scores]
        if len(logits) != len(candidates):
            raise ValueError("O CrossEncoder deve devolver um score para cada candidato")
        scores = [1 / (1 + exp(-max(-60.0, min(60.0, logit)))) for logit in logits]
        ordered = sorted(
            zip(candidates, scores, strict=True),
            key=lambda item: (-item[1], item[0].chunk_id),
        )[:limit]
        return [
            replace(chunk, score=score, rerank_score=score, rerank_rank=rank)
            for rank, (chunk, score) in enumerate(ordered, start=1)
        ]
