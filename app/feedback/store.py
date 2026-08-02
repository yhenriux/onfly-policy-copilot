"""Armazena feedback sem guardar perguntas, respostas ou credenciais."""

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from app.domain.schemas import AuthenticatedContext, FeedbackRequest, FeedbackResponse


@dataclass(frozen=True)
class FeedbackRecord:
    """Avaliação interna ligada à requisição e ao contexto autenticado."""

    feedback_id: str
    request_id: str
    rating: str
    tenant_id: str
    user_id: str


class InMemoryFeedbackStore:
    """Guarda avaliações somente enquanto a demonstração estiver ativa."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_tenants: dict[str, str] = {}
        self._records: list[FeedbackRecord] = []

    def register_request(self, request_id: str, tenant_id: str) -> None:
        """Liga uma resposta ao tenant que tinha permissão para recebê-la."""

        with self._lock:
            self._request_tenants[request_id] = tenant_id

    def add(
        self,
        request: FeedbackRequest,
        context: AuthenticatedContext,
    ) -> FeedbackResponse | None:
        """Aceita feedback somente para uma resposta do mesmo tenant."""

        with self._lock:
            if self._request_tenants.get(request.request_id) != context.tenant_id:
                return None
            record = FeedbackRecord(
                feedback_id=f"fb_{uuid4().hex}",
                request_id=request.request_id,
                rating=request.rating,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            self._records.append(record)
        return FeedbackResponse(
            feedback_id=record.feedback_id,
            request_id=record.request_id,
            status="received",
        )

    def records(self) -> list[FeedbackRecord]:
        """Devolve uma cópia para testes, sem permitir alteração interna."""

        with self._lock:
            return list(self._records)
