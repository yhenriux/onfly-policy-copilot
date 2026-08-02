"""Compara qualidade e latência antes e depois do re-ranking local."""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from app.core.config import Settings
from app.evaluation.retrieval import calculate_metrics, relevant_rank
from app.generation.ollama_provider import OllamaProvider
from app.retrieval.context import select_context
from app.retrieval.dense import QdrantVectorStore
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalCrossEncoderReranker


def _percentile_95(values: list[float]) -> float:
    """Devolve uma aproximação simples do percentil 95 para a amostra pequena."""

    ordered = sorted(values)
    index = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[index]


async def evaluate(dataset_path: Path, output_path: Path | None) -> dict[str, Any]:
    """Executa o ranking híbrido e compara com o contexto após CrossEncoder."""

    settings = Settings()
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    provider = OllamaProvider(
        base_url=str(settings.ollama_base_url),
        generation_model=settings.ollama_generation_model,
        embedding_model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    store = QdrantVectorStore(
        path=settings.qdrant_path,
        collection_name=settings.qdrant_collection,
    )
    hybrid_retriever = HybridRetriever(
        store,
        candidate_limit=settings.retrieval_top_k,
        rrf_k=settings.rrf_k,
        dense_weight=settings.dense_weight,
        lexical_weight=settings.lexical_weight,
    )
    reranker = LocalCrossEncoderReranker(settings.cross_encoder_model)
    embeddings = await provider.embed([case["question"] for case in cases])
    ranks: dict[str, list[int | None]] = {"before": [], "after": []}
    latencies: dict[str, list[float]] = {"before": [], "after": []}
    details: list[dict[str, Any]] = []

    try:
        warmup_started = perf_counter()
        warmup_candidates = hybrid_retriever.search(
            cases[0]["question"],
            embeddings[0],
            tenant_id=cases[0]["tenant_id"],
            limit=settings.rerank_top_n,
        )
        reranker.rerank(cases[0]["question"], warmup_candidates, limit=settings.rerank_top_n)
        cold_start_ms = (perf_counter() - warmup_started) * 1_000

        for case, embedding in zip(cases, embeddings, strict=True):
            before_started = perf_counter()
            candidates = hybrid_retriever.search(
                case["question"],
                embedding,
                tenant_id=case["tenant_id"],
                limit=settings.rerank_top_n,
            )
            before_latency = (perf_counter() - before_started) * 1_000
            before = candidates[: settings.context_top_k]

            after_started = perf_counter()
            reranked = reranker.rerank(
                case["question"],
                candidates,
                limit=settings.rerank_top_n,
            )
            after = select_context(
                reranked,
                limit=settings.context_top_k,
                max_characters=settings.max_context_characters,
                redundancy_threshold=settings.context_redundancy_threshold,
            )
            rerank_latency = (perf_counter() - after_started) * 1_000

            before_rank = relevant_rank(before, case["expected_section"])
            after_rank = relevant_rank(after, case["expected_section"])
            ranks["before"].append(before_rank)
            ranks["after"].append(after_rank)
            latencies["before"].append(before_latency)
            latencies["after"].append(before_latency + rerank_latency)
            details.append(
                {
                    "case_id": case["case_id"],
                    "rank_before": before_rank,
                    "rank_after": after_rank,
                    "retrieval_ms": round(before_latency, 2),
                    "rerank_and_context_ms": round(rerank_latency, 2),
                }
            )
    finally:
        store.close()

    comparison: dict[str, Any] = {}
    for stage in ("before", "after"):
        metrics = calculate_metrics(ranks[stage], k=settings.context_top_k)
        comparison[stage] = {
            "recall_at_k": round(metrics.recall_at_k, 4),
            "mrr": round(metrics.mean_reciprocal_rank, 4),
            "mean_latency_ms": round(mean(latencies[stage]), 2),
            "p95_latency_ms": round(_percentile_95(latencies[stage]), 2),
        }
    report = {
        "dataset_id": dataset["dataset_id"],
        "cases": len(cases),
        "k": settings.context_top_k,
        "cross_encoder_model": settings.cross_encoder_model,
        "cold_start_ms": round(cold_start_ms, 2),
        "comparison": comparison,
        "details": details,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return report


def main() -> None:
    """Lê os caminhos do benchmark e inicia a execução."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/retrieval_phase3.json")
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    asyncio.run(evaluate(arguments.dataset, arguments.output))


if __name__ == "__main__":
    main()
