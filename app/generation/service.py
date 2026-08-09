"""Serviço que recupera evidências e coordena a geração confiável."""

import asyncio
import logging
from time import perf_counter
from typing import Literal, Protocol

from app.core.exceptions import (
    InvalidGenerationOutputError,
    OllamaUnavailableError,
    TenantIsolationError,
)
from app.core.logging import log_structured
from app.domain.models import RetrievedChunk
from app.domain.schemas import (
    AskRequest,
    AskResponse,
    AuthenticatedContext,
    ExecutionDocument,
    ExecutionTrace,
    GenerationMetadata,
    SourceReference,
)
from app.generation.grounded_answers import (
    GROUNDED_ANSWER_VERSION,
    build_grounded_answer,
    rewrite_frequent_question,
)
from app.generation.provider import GenerationProvider, ProviderResult
from app.guardrails.input_guardrail import ensure_safe_question
from app.guardrails.output_guardrail import keep_safe_document_chunks
from app.observability.langsmith import trace_quality_signal
from app.observability.metrics import operational_metrics
from app.observability.tracing import current_trace, record_timing

logger = logging.getLogger(__name__)


class Retriever(Protocol):
    """Busca fontes usando a pergunta, seu vetor e a empresa autorizada."""

    def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Recupera evidências já filtradas pela empresa autenticada."""
        ...


class AskHandler(Protocol):
    """Operação assíncrona usada pela rota HTTP de perguntas."""

    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        """Executa uma pergunta usando somente o contexto autenticado recebido."""
        ...


class AskService:
    """Recupera fontes autorizadas e coordena geração, validação e fallback."""

    def __init__(
        self,
        *,
        provider: GenerationProvider,
        retriever: Retriever,
        retrieval_limit: int,
        evidence_min_score: float = 0.5,
        max_evidence_chunks: int = 1,
    ) -> None:
        self._provider = provider
        self._retriever = retriever
        self._retrieval_limit = retrieval_limit
        self._evidence_min_score = evidence_min_score
        self._max_evidence_chunks = max_evidence_chunks

    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        """Executa recuperação e devolve sempre uma resposta validada."""

        started_at = perf_counter()
        ensure_safe_question(request.question)
        retrieval_query = rewrite_frequent_question(request.question)
        embedding_started = perf_counter()
        query_embeddings = await self._provider.embed([retrieval_query])
        self._record_latency("ollama_embedding", embedding_started)
        if not query_embeddings:
            raise ValueError("O provedor não devolveu o vetor da pergunta")
        retrieval_started = perf_counter()
        chunks = await asyncio.to_thread(
            self._retriever.search,
            retrieval_query,
            query_embeddings[0],
            tenant_id=context.tenant_id,
            limit=self._retrieval_limit,
        )
        self._record_latency("retrieval", retrieval_started)
        if any(chunk.tenant_id != context.tenant_id for chunk in chunks):
            raise TenantIsolationError("O serviço recebeu dados de outro tenant")
        chunks = keep_safe_document_chunks(chunks)
        grounded_chunks = [chunk for chunk in chunks if chunk.score >= self._evidence_min_score]
        grounded = build_grounded_answer(request.question, grounded_chunks)
        if grounded is not None:
            response = AskResponse(
                answer=grounded.answer,
                sources=[_source(chunk) for chunk in grounded.chunks],
                confidence="high",
                request_id=current_trace().request_id,
                latency_ms=_elapsed_ms(started_at),
                generation=GenerationMetadata(
                    provider="grounded-synthesizer",
                    model=GROUNDED_ANSWER_VERSION,
                    prompt_version=GROUNDED_ANSWER_VERSION,
                    status="generated",
                    attempts=0,
                ),
            )
            return self._finalize(response, chunks, context)
        evidence_chunks = [chunk for chunk in chunks if chunk.score >= self._evidence_min_score][
            : self._max_evidence_chunks
        ]
        if not evidence_chunks:
            return self._finalize(self._response_without_evidence(started_at), chunks, context)
        try:
            generation_started = perf_counter()
            result = await self._provider.generate(request.question, evidence_chunks)
            self._record_latency("ollama_generation", generation_started)
            response = self._response_from_generation(result, evidence_chunks, started_at)
            return self._finalize(response, chunks, context)
        except OllamaUnavailableError as error:
            self._record_latency("ollama_generation", generation_started)
            response = self._degraded_response(
                evidence_chunks[0], started_at, attempts=error.attempts
            )
            return self._finalize(response, chunks, context)
        except InvalidGenerationOutputError:
            self._record_latency("ollama_generation", generation_started)
            response = self._degraded_response(evidence_chunks[0], started_at, attempts=1)
            return self._finalize(response, chunks, context)

    def _response_from_generation(
        self,
        result: ProviderResult,
        chunks: list[RetrievedChunk],
        started_at: float,
    ) -> AskResponse:
        """Aceita somente fontes que realmente estavam no contexto autorizado."""

        if not result.output.evidence_found:
            # O retrieval já validou que existe evidência acima do limite mínimo.
            # Se o modelo pequeno não conseguir usá-la, mostramos a fonte sem inventar.
            return self._degraded_response(chunks[0], started_at, attempts=result.attempts)
        if result.output.confidence == "low":
            # Modelos pequenos podem produzir uma conclusão curta e errada mesmo com a fonte certa.
            # Nesse caso, a aplicação mostra o texto autorizado em vez de confiar na interpretação.
            return self._degraded_response(chunks[0], started_at, attempts=result.attempts)
        if any(position > len(chunks) for position in result.output.cited_source_positions):
            raise InvalidGenerationOutputError("A geração citou uma posição não autorizada")
        positions = dict.fromkeys(result.output.cited_source_positions)
        cited = [chunks[position - 1] for position in positions]
        return AskResponse(
            answer=result.output.answer,
            sources=[_source(chunk) for chunk in cited],
            confidence=result.output.confidence,
            request_id=current_trace().request_id,
            latency_ms=_elapsed_ms(started_at),
            generation=_metadata(result, status="generated"),
        )

    def _response_without_evidence(self, started_at: float) -> AskResponse:
        """Responde sem chamar o gerador quando nenhuma fonte foi recuperada."""

        return AskResponse(
            answer="Não encontrei evidências suficientes nas políticas autorizadas.",
            sources=[],
            confidence="low",
            request_id=current_trace().request_id,
            latency_ms=_elapsed_ms(started_at),
            generation=GenerationMetadata(
                provider=self._provider.provider_name,
                model=self._provider.generation_model,
                prompt_version=self._provider.prompt_version,
                status="no_evidence",
                attempts=0,
            ),
        )

    def _degraded_response(
        self, chunk: RetrievedChunk, started_at: float, *, attempts: int
    ) -> AskResponse:
        """Evita inventar uma resposta quando a geração não está disponível."""

        return AskResponse(
            answer=f"Esta é a orientação encontrada na política:\n\n{chunk.text}",
            sources=[_source(chunk)],
            confidence="low",
            request_id=current_trace().request_id,
            latency_ms=_elapsed_ms(started_at),
            generation=GenerationMetadata(
                provider=self._provider.provider_name,
                model=self._provider.generation_model,
                prompt_version=self._provider.prompt_version,
                status="degraded",
                attempts=attempts,
            ),
        )

    def _record_latency(self, component: str, started_at: float) -> None:
        """Registra o tempo no rastro da requisição e nas métricas agregadas."""

        milliseconds = (perf_counter() - started_at) * 1_000
        record_timing(component, milliseconds)
        operational_metrics.observe_latency(component, milliseconds)

    def _finalize(
        self,
        response: AskResponse,
        chunks: list[RetrievedChunk],
        context: AuthenticatedContext,
    ) -> AskResponse:
        """Fecha o rastro, registra configuração e devolve a resposta final."""

        trace = current_trace()
        record_timing("total", float(response.latency_ms))
        operational_metrics.observe_latency("total", float(response.latency_ms))
        retries = max(0, response.generation.attempts - 1)
        if retries:
            operational_metrics.increment("retries_total", retries)
        if response.generation.status == "degraded":
            operational_metrics.increment("fallbacks_total")
        operational_metrics.increment("answers_total")
        operational_metrics.increment(f"answers_status_{response.generation.status}_total")
        operational_metrics.increment(f"answers_confidence_{response.confidence}_total")
        operational_metrics.observe_value("sources_per_answer", float(len(response.sources)))
        # Ollama é executado localmente neste projeto: o custo monetário por resposta é zero.
        operational_metrics.observe_value("estimated_local_cost_usd", 0.0)
        operational_metrics.observe_value(
            "estimated_output_tokens", float(len(response.answer.split()))
        )
        top1_score = chunks[0].score if chunks else 0.0
        operational_metrics.observe_value("retrieval_top1_score", top1_score)
        operational_metrics.observe_value(
            "retrieval_top1_evidence_eligible",
            1.0 if top1_score >= self._evidence_min_score else 0.0,
        )
        trace_quality_signal(
            status=response.generation.status,
            confidence=response.confidence,
            source_count=len(response.sources),
            top1_score=round(top1_score, 4),
        )
        documents = [
            ExecutionDocument(
                document_id=chunk.document_id,
                version=chunk.version,
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                score=round(chunk.score, 4),
            )
            for chunk in chunks
        ]
        response.trace = ExecutionTrace(
            timings_ms=dict(trace.timings_ms),
            documents=documents,
            estimated_local_cost_usd=0.0,
            estimated_output_tokens=len(response.answer.split()),
            improvement_suggestions=_improvement_suggestions(
                response=response,
                top1_score=top1_score,
                evidence_min_score=self._evidence_min_score,
            ),
        )
        log_structured(
            logger,
            "rag_trace",
            request_id=response.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            timings_ms=trace.timings_ms,
            provider=response.generation.provider,
            model=response.generation.model,
            prompt_version=response.generation.prompt_version,
            documents=[document.model_dump() for document in documents],
            retries=retries,
            fallback=response.generation.status == "degraded",
        )
        return response


def _metadata(
    result: ProviderResult,
    *,
    status: Literal["generated", "no_evidence"],
) -> GenerationMetadata:
    """Monta o rastro público da geração."""

    return GenerationMetadata(
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        status=status,
        attempts=result.attempts,
    )


def _source(chunk: RetrievedChunk) -> SourceReference:
    """Converte um trecho autorizado na fonte pública da API."""

    return SourceReference(
        document_id=chunk.document_id,
        title=chunk.title,
        version=chunk.version,
        chunk_id=chunk.chunk_id,
        section=chunk.section,
        score=round(chunk.score, 4),
    )


def _improvement_suggestions(
    *,
    response: AskResponse,
    top1_score: float,
    evidence_min_score: float,
) -> list[str]:
    """Indica ações técnicas objetivas a partir do resultado desta execução."""

    suggestions: list[str] = []
    if response.generation.status == "no_evidence":
        suggestions.append(
            "Expandir a base de conhecimento para este assunto ou revisar os sinônimos."
        )
    if top1_score and top1_score < evidence_min_score:
        suggestions.append(
            "Revisar chunking, metadados e termos da consulta: o Top-1 ficou abaixo do limiar."
        )
    if response.generation.status == "degraded":
        suggestions.append(
            "Investigar disponibilidade e saída estruturada do modelo antes de promover mudanças."
        )
    if response.latency_ms > 2_000:
        suggestions.append(
            "Avaliar latência de embedding, retrieval e geração antes de alterar o modelo."
        )
    if not suggestions:
        suggestions.append(
            "Monitorar feedback e métricas do golden dataset antes da próxima alteração."
        )
    return suggestions


def _elapsed_ms(started_at: float) -> int:
    """Calcula a latência sem permitir valor negativo."""

    return max(0, round((perf_counter() - started_at) * 1_000))
