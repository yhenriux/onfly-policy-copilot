"""Ponto de entrada da API criada com FastAPI."""

import logging
from time import perf_counter
from typing import Annotated, Any, Literal, TypedDict

from fastapi import Depends, FastAPI, Header, HTTPException, status
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
    LoginRequest,
    TokenResponse,
)
from app.feedback.store import InMemoryFeedbackStore
from app.generation.langchain_ollama_provider import LangChainOllamaProvider
from app.generation.ollama_provider import OllamaProvider
from app.generation.service import AskHandler, AskService
from app.guardrails.tenant_guardrail import TenantGuardedRetriever
from app.observability.health import LocalReadinessChecker, ReadinessChecker
from app.observability.langsmith import configure_langsmith
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
        return response

    return application


app = create_app()
