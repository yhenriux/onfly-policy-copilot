"""Ponto de entrada da API criada com FastAPI."""

import json
import logging
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal, TypedDict
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.auth import MockAuthService
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AuthenticationError,
    OllamaUnavailableError,
    PromptInjectionError,
    RetrievalUnavailableError,
    TenantIsolationError,
)
from app.core.logging import log_structured
from app.domain.schemas import (
    AskRequest,
    AskResponse,
    AuthenticatedContext,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    IngestionAcceptedResponse,
    IngestionStatusResponse,
    LoginRequest,
    TelemetryRequest,
    TokenResponse,
)
from app.feedback.store import InMemoryFeedbackStore
from app.generation.langchain_ollama_provider import LangChainOllamaProvider
from app.generation.ollama_provider import OllamaProvider
from app.generation.service import AskHandler, AskService
from app.guardrails.tenant_guardrail import TenantGuardedRetriever
from app.knowledge_graph.neo4j_repository import Neo4jKnowledgeGraph
from app.messaging.rabbitmq import JobPublisher, RabbitMQPublisher
from app.messaging.redis_store import JobStatusStore, RedisJobStatusStore
from app.messaging.schemas import IngestionJob, IngestionJobStatus
from app.observability.health import LocalReadinessChecker, ReadinessChecker
from app.observability.langsmith import configure_langsmith, trace_user_event
from app.observability.metrics import operational_metrics
from app.observability.tracing import current_trace, finish_trace, start_trace
from app.orchestration.rag_graph import LangGraphAskHandler
from app.retrieval.contextual import ContextualRetriever
from app.retrieval.factory import build_vector_store
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import LocalCrossEncoderReranker

logger = logging.getLogger(__name__)


class HealthResponse(TypedDict):
    """Resposta pública que confirma se a API está disponível."""

    status: Literal["ok"]
    service: str


def _build_ask_service(settings: Settings) -> AskHandler:
    """Monta o RAG local, que busca trechos antes de gerar a resposta."""

    provider_class = (
        LangChainOllamaProvider if settings.llm_integration == "langchain" else OllamaProvider
    )
    provider = provider_class(
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
    contextual = ContextualRetriever(
        hybrid,
        LocalCrossEncoderReranker(settings.cross_encoder_model),
        rerank_top_n=settings.rerank_top_n,
        max_context_characters=settings.max_context_characters,
        redundancy_threshold=settings.context_redundancy_threshold,
    )
    retriever = TenantGuardedRetriever(contextual)
    service = AskService(
        provider=provider,
        retriever=retriever,
        retrieval_limit=settings.context_top_k,
        evidence_min_score=settings.evidence_min_score,
        max_evidence_chunks=settings.generation_max_evidence_chunks,
    )
    return LangGraphAskHandler(service) if settings.workflow_engine == "langgraph" else service


def create_app(
    settings: Settings | None = None,
    ask_handler: AskHandler | None = None,
    auth_service: MockAuthService | None = None,
    readiness_checker: ReadinessChecker | None = None,
    feedback_store: InMemoryFeedbackStore | None = None,
    job_publisher: JobPublisher | None = None,
    job_status_store: JobStatusStore | None = None,
) -> FastAPI:
    """Monta a API com as configurações informadas para a execução."""

    runtime_settings = settings or get_settings()
    configure_langsmith(runtime_settings)
    runtime_auth = auth_service or MockAuthService(
        runtime_settings.auth_users_path,
        secret=runtime_settings.auth_token_secret.get_secret_value(),
        ttl_seconds=runtime_settings.auth_token_ttl_seconds,
    )
    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description="API for secure, traceable access to corporate travel policies.",
    )
    runtime_readiness = readiness_checker or LocalReadinessChecker(
        ollama_base_url=str(runtime_settings.ollama_base_url),
        qdrant_mode=runtime_settings.qdrant_mode,
        qdrant_path=runtime_settings.qdrant_path,
        qdrant_url=str(runtime_settings.qdrant_url),
        qdrant_api_key=(
            runtime_settings.qdrant_api_key.get_secret_value()
            if runtime_settings.qdrant_api_key is not None
            else None
        ),
        collection=runtime_settings.qdrant_collection,
    )
    runtime_feedback = feedback_store or InMemoryFeedbackStore()
    runtime_publisher = job_publisher or RabbitMQPublisher(
        runtime_settings.rabbitmq_url,
        runtime_settings.rabbitmq_exchange,
        runtime_settings.rabbitmq_queue,
        runtime_settings.rabbitmq_dead_letter_queue,
    )
    runtime_job_store = job_status_store or RedisJobStatusStore(
        runtime_settings.redis_url, runtime_settings.redis_job_ttl_seconds
    )
    runtime_graph = (
        Neo4jKnowledgeGraph(
            runtime_settings.neo4j_uri,
            runtime_settings.neo4j_username,
            runtime_settings.neo4j_password.get_secret_value(),
            runtime_settings.neo4j_database,
        )
        if runtime_settings.knowledge_graph_enabled
        else None
    )

    @application.on_event("shutdown")
    async def close_runtime_clients() -> None:
        """Fecha clientes externos criados pela API durante testes e shutdown."""

        if runtime_graph is not None:
            await runtime_graph.close()

    web_root = runtime_settings.web_root
    application.mount("/static", StaticFiles(directory=web_root / "static"), name="static")

    @application.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Any:
        """Liga identificação, logs e métricas a toda requisição."""

        token = start_trace(request.headers.get("X-Request-ID"))
        trace = current_trace()
        started_at = perf_counter()
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        operational_metrics.increment("requests_total")
        try:
            response = await call_next(request)
            response_status = response.status_code
            if response.status_code >= 400:
                operational_metrics.increment("errors_total")
            response.headers["X-Request-ID"] = trace.request_id
            return response
        except Exception:
            operational_metrics.increment("errors_total")
            raise
        finally:
            total_ms = (perf_counter() - started_at) * 1_000
            operational_metrics.observe_latency("http_total", total_ms)
            log_structured(
                logger,
                "http_request",
                request_id=trace.request_id,
                method=request.method,
                path=request.url.path,
                status_code=response_status,
                latency_ms=round(total_ms, 3),
            )
            finish_trace(token)

    @application.get("/health", tags=["operations"])
    def health() -> HealthResponse:
        """Confirma que o processo da API está disponível."""

        return {"status": "ok", "service": runtime_settings.app_name}

    @application.get("/ready", tags=["operations"])
    async def ready() -> JSONResponse:
        """Confirma se Ollama e Qdrant podem atender uma pergunta agora."""

        dependencies = await runtime_readiness.check()
        is_ready = all(dependencies.values())
        return JSONResponse(
            status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ready" if is_ready else "not_ready", "dependencies": dependencies},
        )

    @application.get("/metrics", tags=["operations"])
    def metrics() -> dict[str, Any]:
        """Expõe contadores e latências agregadas deste processo."""

        return operational_metrics.snapshot()

    @application.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        """Entrega a interface demonstrativa junto com a API."""

        return FileResponse(web_root / "index.html")

    def authenticated_context(
        authorization: Annotated[str | None, Header()] = None,
    ) -> AuthenticatedContext:
        """Extrai o contexto somente de um token Bearer assinado."""

        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Autenticação obrigatória.",
            )
        try:
            return runtime_auth.authenticate(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado.",
            ) from error

    @application.post("/v1/auth/login", response_model=TokenResponse, tags=["authentication"])
    def login(request: LoginRequest) -> TokenResponse:
        """Autentica uma credencial totalmente sintética para demonstração."""

        try:
            token, context = runtime_auth.login(request.username, request.password)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas.",
            ) from error
        return TokenResponse(
            access_token=token,
            expires_in=runtime_auth.ttl_seconds,
            context=context,
        )

    @application.post("/v1/telemetry", status_code=status.HTTP_204_NO_CONTENT, tags=["operations"])
    def telemetry(
        request: TelemetryRequest,
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
    ) -> None:
        """Registra uma interação da interface sem guardar o conteúdo da conversa."""

        operational_metrics.increment(f"user_event_{request.event}_total")
        trace_user_event(request.event)
        log_structured(
            logger,
            "user_interaction",
            request_id=current_trace().request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            interaction=request.event,
        )

    @application.post(
        "/v1/ingestion",
        response_model=IngestionAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["ingestion"],
    )
    async def ingestion(
        file: Annotated[UploadFile, File(description="Arquivo Markdown da política")],
        document_id: Annotated[str, Form(min_length=1, max_length=100)],
        title: Annotated[str, Form(min_length=3, max_length=200)],
        version: Annotated[str, Form(pattern=r"^v[1-9][0-9]*$")],
        valid_from: Annotated[date, Form()],
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
        valid_until: Annotated[date | None, Form()] = None,
    ) -> IngestionAcceptedResponse:
        """Persiste o upload e enfileira a ingestão sem bloquear pela geração de embeddings."""

        if file.filename is None or not file.filename.lower().endswith(".md"):
            raise HTTPException(status_code=400, detail="O arquivo deve possuir extensão .md.")
        if valid_until is not None and valid_until < valid_from:
            raise HTTPException(
                status_code=400, detail="valid_until não pode ser anterior a valid_from."
            )

        job_id = uuid4()
        job_directory = runtime_settings.ingestion_storage_path / str(job_id)
        job_directory.mkdir(parents=True, exist_ok=False)
        document_path = job_directory / "policy.md"
        manifest_path = job_directory / "metadata.json"
        try:
            content = await file.read(runtime_settings.ingestion_max_file_bytes + 1)
            if len(content) > runtime_settings.ingestion_max_file_bytes:
                raise HTTPException(
                    status_code=413, detail="O arquivo excede o tamanho máximo permitido."
                )
            if not content.strip():
                raise HTTPException(status_code=400, detail="O arquivo não pode estar vazio.")
            document_path.write_bytes(content)
            manifest_path.write_text(
                json.dumps(
                    {
                        "tenant_id": context.tenant_id,
                        "document_id": document_id,
                        "title": title,
                        "version": version,
                        "valid_from": valid_from.isoformat(),
                        "valid_until": valid_until.isoformat() if valid_until else None,
                        "file": document_path.name,
                    }
                ),
                encoding="utf-8",
            )
            job = IngestionJob(
                job_id=job_id,
                request_id=current_trace().request_id,
                tenant_id=context.tenant_id,
                document_id=document_id,
                version=version,
                manifest_path=str(manifest_path),
            )
            await runtime_job_store.set(
                IngestionJobStatus(
                    job_id=job.job_id,
                    request_id=job.request_id,
                    tenant_id=job.tenant_id,
                    document_id=job.document_id,
                    version=job.version,
                    status="queued",
                )
            )
            await runtime_publisher.publish(job)
        except HTTPException:
            _remove_job_directory(job_directory)
            raise
        except Exception as error:
            _remove_job_directory(job_directory)
            raise HTTPException(
                status_code=503, detail="Não foi possível enfileirar a ingestão."
            ) from error
        return IngestionAcceptedResponse(job_id=str(job_id), status="queued")

    @application.get(
        "/v1/ingestion/{job_id}",
        response_model=IngestionStatusResponse,
        tags=["ingestion"],
    )
    async def ingestion_status(
        job_id: str,
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
    ) -> IngestionStatusResponse:
        """Consulta o job sem permitir acesso ao estado de outro tenant."""

        try:
            job_status = await runtime_job_store.get(job_id)
        except Exception as error:
            raise HTTPException(
                status_code=503, detail="Status de ingestão indisponível."
            ) from error
        if job_status is None or job_status.tenant_id != context.tenant_id:
            raise HTTPException(status_code=404, detail="Job de ingestão não encontrado.")
        return IngestionStatusResponse(
            job_id=str(job_status.job_id),
            status=job_status.status,
            document_id=job_status.document_id,
            version=job_status.version,
            chunks_indexed=job_status.chunks_indexed,
            detail=job_status.detail,
        )

    @application.get("/v1/knowledge-graph/rules", tags=["knowledge-graph"])
    async def knowledge_graph_rules(
        topic: str,
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
    ) -> list[dict[str, Any]]:
        """Consulta regras explícitas do tenant sem substituir a busca textual do RAG."""

        if runtime_graph is None:
            raise HTTPException(status_code=404, detail="Grafo de conhecimento desabilitado.")
        try:
            return await runtime_graph.search_rules(context.tenant_id, topic)
        except Exception as error:
            raise HTTPException(
                status_code=503, detail="Grafo de conhecimento indisponível."
            ) from error

    @application.post(
        "/v1/ask",
        response_model=AskResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
        tags=["policy-copilot"],
    )
    async def ask(
        request: AskRequest,
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
    ) -> AskResponse:
        """Responde usando trechos recuperados das políticas autorizadas."""

        nonlocal ask_handler
        if ask_handler is None:
            ask_handler = _build_ask_service(runtime_settings)

        try:
            response = await ask_handler.ask(request, context)
            runtime_feedback.register_request(response.request_id, context.tenant_id)
            return response
        except PromptInjectionError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A pergunta contém uma instrução não permitida.",
            ) from error
        except TenantIsolationError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso a dados de outro tenant bloqueado.",
            ) from error
        except OllamaUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="O modelo local está temporariamente indisponível.",
            ) from error
        except RetrievalUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A recuperação de políticas está temporariamente indisponível.",
            ) from error

    @application.post(
        "/v1/feedback",
        response_model=FeedbackResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["policy-copilot"],
    )
    def feedback(
        request: FeedbackRequest,
        context: Annotated[AuthenticatedContext, Depends(authenticated_context)],
    ) -> FeedbackResponse:
        """Registra uma avaliação somente para uma resposta do tenant atual."""

        response = runtime_feedback.add(request, context)
        if response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A requisição avaliada não pertence a esta sessão.",
            )
        operational_metrics.increment(f"user_event_feedback_{request.rating}_total")
        trace_user_event(f"feedback_{request.rating}")
        return response

    return application


def _remove_job_directory(path: Path) -> None:
    """Remove arquivos de um upload que não chegou a ser publicado."""

    if path.exists():
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


app = create_app()
