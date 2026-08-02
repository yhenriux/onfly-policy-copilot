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
from app.generation.provider import GenerationProvider, ProviderResult
from app.guardrails.input_guardrail import ensure_safe_question
from app.guardrails.output_guardrail import keep_safe_document_chunks
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
    ) -> list[RetrievedChunk]: ...


class AskHandler(Protocol):
    """Operação assíncrona usada pela rota HTTP de perguntas."""

    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse: ...


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
        embedding_started = perf_counter()
        query_embeddings = await self._provider.embed([request.question])
        self._record_latency("ollama_embedding", embedding_started)
        if not query_embeddings:
            raise ValueError("O provedor não devolveu o vetor da pergunta")
        retrieval_started = perf_counter()
        chunks = await asyncio.to_thread(
            self._retriever.search,
            request.question,
            query_embeddings[0],
            tenant_id=context.tenant_id,
            limit=self._retrieval_limit,
        )
        self._record_latency("retrieval", retrieval_started)
        if any(chunk.tenant_id != context.tenant_id for chunk in chunks):
            raise TenantIsolationError("O serviço recebeu dados de outro tenant")
        chunks = keep_safe_document_chunks(chunks)
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
            return AskResponse(
                answer="Não encontrei evidências suficientes nas políticas autorizadas.",
                sources=[],
                confidence="low",
                request_id=current_trace().request_id,
                latency_ms=_elapsed_ms(started_at),
                generation=_metadata(result, status="no_evidence"),
            )
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
            answer=(
                "Não foi possível gerar a resposta agora. "
                "Consulte a fonte mais relevante indicada abaixo."
            ),
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
        documents = [
            ExecutionDocument(
                document_id=chunk.document_id,
                version=chunk.version,
                chunk_id=chunk.chunk_id,
                score=round(chunk.score, 4),
            )
            for chunk in chunks
        ]
        response.trace = ExecutionTrace(timings_ms=dict(trace.timings_ms), documents=documents)
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


def _elapsed_ms(started_at: float) -> int:
    """Calcula a latência sem permitir valor negativo."""

    return max(0, round((perf_counter() - started_at) * 1_000))
