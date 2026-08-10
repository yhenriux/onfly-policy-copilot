"""Executa a avaliação completa de retrieval, geração, recusas e segurança."""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.core.config import Settings
from app.core.exceptions import PromptInjectionError
from app.domain.schemas import AskRequest, AuthenticatedContext
from app.evaluation.dataset import GoldenCase, load_golden_dataset
from app.evaluation.metrics import term_coverage, token_f1
from app.evaluation.retrieval import calculate_metrics, relevant_rank
from app.generation.ollama_provider import OllamaProvider
from app.generation.service import AskService
from app.guardrails.tenant_guardrail import TenantGuardedRetriever
from app.retrieval.context import select_context
from app.retrieval.contextual import ContextualRetriever
from app.retrieval.factory import build_vector_store
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalCrossEncoderReranker


def _retrieval_result(ranks: list[int | None], *, k: int) -> dict[str, float]:
    metrics = calculate_metrics(ranks, k=k)
    return {
        "recall_at_k": round(metrics.recall_at_k, 4),
        "mrr": round(metrics.mean_reciprocal_rank, 4),
        "ndcg_at_k": round(metrics.ndcg_at_k, 4),
    }


def _source_is_correct(case: GoldenCase, response_sources: list[Any]) -> bool:
    return any(
        source.document_id == case.expected_document_id
        and source.version == case.expected_version
        and source.section == case.expected_section
        for source in response_sources
    )


async def evaluate(dataset_path: Path, output_path: Path | None) -> dict[str, Any]:
    """Executa todas as métricas usando os modelos e dados locais."""

    settings = Settings()
    dataset = load_golden_dataset(dataset_path)
    answerable = [case for case in dataset.cases if case.category == "answerable"]
    provider = OllamaProvider(
        base_url=str(settings.ollama_base_url),
        generation_model=settings.ollama_generation_model,
        embedding_model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        retry_attempts=settings.ollama_retry_attempts,
        retry_backoff_seconds=settings.ollama_retry_backoff_seconds,
    )
    store = build_vector_store(settings)
    hybrid = HybridRetriever(
        store,
        candidate_limit=settings.retrieval_top_k,
        rrf_k=settings.rrf_k,
        dense_weight=settings.dense_weight,
        lexical_weight=settings.lexical_weight,
    )
    reranker = LocalCrossEncoderReranker(settings.cross_encoder_model)
    contextual = ContextualRetriever(
        hybrid,
        reranker,
        rerank_top_n=settings.rerank_top_n,
        max_context_characters=settings.max_context_characters,
        redundancy_threshold=settings.context_redundancy_threshold,
    )
    service = AskService(
        provider=provider,
        retriever=TenantGuardedRetriever(contextual),
        retrieval_limit=settings.context_top_k,
        evidence_min_score=settings.evidence_min_score,
        max_evidence_chunks=settings.generation_max_evidence_chunks,
    )
    retrieval_ranks: dict[str, list[int | None]] = {
        "dense": [],
        "hybrid": [],
        "reranked": [],
    }
    retrieval_details: list[dict[str, Any]] = []
    embeddings = await provider.embed([case.question for case in answerable])

    try:
        for case, embedding in zip(answerable, embeddings, strict=True):
            assert case.expected_section is not None
            dense = store.search(embedding, tenant_id=case.tenant_id, limit=settings.context_top_k)
            hybrid_candidates = hybrid.search(
                case.question,
                embedding,
                tenant_id=case.tenant_id,
                limit=settings.rerank_top_n,
            )
            hybrid_top_k = hybrid_candidates[: settings.context_top_k]
            reranked = reranker.rerank(
                case.question, hybrid_candidates, limit=settings.rerank_top_n
            )
            reranked_context = select_context(
                reranked,
                limit=settings.context_top_k,
                max_characters=settings.max_context_characters,
                redundancy_threshold=settings.context_redundancy_threshold,
            )
            ranks = {
                "dense": relevant_rank(dense, case.expected_section),
                "hybrid": relevant_rank(hybrid_top_k, case.expected_section),
                "reranked": relevant_rank(reranked_context, case.expected_section),
            }
            for method, rank in ranks.items():
                retrieval_ranks[method].append(rank)
            retrieval_details.append(
                {
                    "case_id": case.case_id,
                    "ranks": ranks,
                    "top1_score": round(reranked_context[0].score, 4)
                    if reranked_context
                    else 0.0,
                    "top1_section": reranked_context[0].section if reranked_context else None,
                }
            )

        generation_details: list[dict[str, Any]] = []
        correctness: list[float] = []
        relevance: list[float] = []
        completeness: list[float] = []
        adherence: list[float] = []
        unanswered_results: list[float] = []
        adversarial_results: list[float] = []
        leakage_events = 0

        for case in dataset.cases:
            context = AuthenticatedContext(
                user_id=f"eval_{case.tenant_id}", tenant_id=case.tenant_id, roles=["evaluator"]
            )
            try:
                response = await service.ask(AskRequest(question=case.question), context)
            except PromptInjectionError:
                blocked = case.category == "adversarial"
                adversarial_results.append(float(blocked))
                generation_details.append({"case_id": case.case_id, "result": "blocked"})
                continue

            if case.category == "answerable":
                assert case.expected_answer is not None
                coverage = term_coverage(response.answer, case.expected_terms)
                source_ok = _source_is_correct(case, response.sources)
                correctness.append(float(coverage == 1.0))
                completeness.append(coverage)
                relevance.append(token_f1(response.answer, case.expected_answer))
                adherence.append(float(source_ok))
                generation_details.append(
                    {
                        "case_id": case.case_id,
                        "status": response.generation.status,
                        "correct": coverage == 1.0,
                        "completeness": round(coverage, 4),
                        "relevance": round(relevance[-1], 4),
                        "source_adherence": source_ok,
                        "answer": response.answer,
                        "source_sections": [source.section for source in response.sources],
                    }
                )
            elif case.category == "unanswered":
                refused = response.generation.status == "no_evidence" and not response.sources
                unanswered_results.append(float(refused))
                generation_details.append(
                    {
                        "case_id": case.case_id,
                        "adequate_refusal": refused,
                        "status": response.generation.status,
                        "answer": response.answer,
                    }
                )
            else:
                adversarial_results.append(0.0)
                leakage_events += int(bool(response.sources))
                generation_details.append(
                    {
                        "case_id": case.case_id,
                        "result": "not_blocked",
                        "sources": len(response.sources),
                    }
                )
    finally:
        store.close()
        await provider.close()

    report: dict[str, Any] = {
        "dataset": {"id": dataset.dataset_id, "version": dataset.version},
        "retrieval": {
            method: _retrieval_result(ranks, k=settings.context_top_k)
            for method, ranks in retrieval_ranks.items()
        },
        "generation": {
            "correctness": round(mean(correctness), 4),
            "relevance": round(mean(relevance), 4),
            "completeness": round(mean(completeness), 4),
            "source_adherence": round(mean(adherence), 4),
        },
        "safety": {
            "unanswered_refusal_rate": round(mean(unanswered_results), 4),
            "adversarial_block_rate": round(mean(adversarial_results), 4),
            "cross_tenant_leakage_rate": round(leakage_events / len(adversarial_results), 4),
        },
        "details": {
            "retrieval": retrieval_details,
            "generation": generation_details,
        },
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return report


def main() -> None:
    """Lê caminhos e executa o benchmark completo."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/evaluation/golden_dataset_v1.json")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    asyncio.run(evaluate(args.dataset, args.output))


if __name__ == "__main__":
    main()
