"""Compara dense, BM25 e híbrida usando os dados sintéticos versionados."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.evaluation.retrieval import calculate_metrics, relevant_rank
from app.generation.ollama_provider import OllamaProvider
from app.retrieval.dense import QdrantVectorStore
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.lexical import BM25Retriever


async def evaluate(dataset_path: Path, output_path: Path | None) -> dict[str, Any]:
    """Executa os três rankings e devolve resultados reproduzíveis."""

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
    lexical_retriever = BM25Retriever(store)
    embeddings = await provider.embed([case["question"] for case in cases])
    ranks: dict[str, list[int | None]] = {"dense": [], "bm25": [], "hybrid": []}
    details: list[dict[str, Any]] = []

    try:
        for case, embedding in zip(cases, embeddings, strict=True):
            dense = store.search(
                embedding,
                tenant_id=case["tenant_id"],
                limit=settings.retrieval_top_k,
            )
            lexical = lexical_retriever.search(
                case["question"],
                tenant_id=case["tenant_id"],
                limit=settings.retrieval_top_k,
            )
            hybrid = reciprocal_rank_fusion(
                dense,
                lexical,
                limit=settings.retrieval_top_k,
                rrf_k=settings.rrf_k,
                dense_weight=settings.dense_weight,
                lexical_weight=settings.lexical_weight,
            )
            case_ranks = {
                "dense": relevant_rank(dense, case["expected_section"]),
                "bm25": relevant_rank(lexical, case["expected_section"]),
                "hybrid": relevant_rank(hybrid, case["expected_section"]),
            }
            for method, rank in case_ranks.items():
                ranks[method].append(rank)
            details.append({"case_id": case["case_id"], "ranks": case_ranks})
    finally:
        store.close()

    metrics = {}
    for method, method_ranks in ranks.items():
        result = calculate_metrics(method_ranks, k=settings.context_top_k)
        metrics[method] = {
            "recall_at_k": round(result.recall_at_k, 4),
            "mrr": round(result.mean_reciprocal_rank, 4),
        }
    report = {
        "dataset_id": dataset["dataset_id"],
        "cases": len(cases),
        "k": settings.context_top_k,
        "configuration": {
            "rrf_k": settings.rrf_k,
            "dense_weight": settings.dense_weight,
            "lexical_weight": settings.lexical_weight,
        },
        "metrics": metrics,
        "details": details,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return report


def main() -> None:
    """Lê argumentos simples e inicia a avaliação."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/retrieval_phase3.json")
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    asyncio.run(evaluate(arguments.dataset, arguments.output))


if __name__ == "__main__":
    main()
