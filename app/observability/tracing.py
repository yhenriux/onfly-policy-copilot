"""Mantém o rastro da requisição atual sem misturar usuários concorrentes."""

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class RequestTrace:
    """Dados técnicos suficientes para reconstruir uma execução."""

    request_id: str
    timings_ms: dict[str, float] = field(default_factory=dict)


_current_trace: ContextVar[RequestTrace | None] = ContextVar("request_trace", default=None)


def start_trace(request_id: str | None = None) -> Token[RequestTrace | None]:
    """Inicia um rastro e devolve o token usado para encerrá-lo."""

    safe_id = request_id.strip()[:100] if request_id and request_id.strip() else None
    return _current_trace.set(RequestTrace(request_id=safe_id or f"req_{uuid4().hex}"))


def finish_trace(token: Token[RequestTrace | None]) -> None:
    """Restaura o contexto anterior ao terminar a requisição."""

    _current_trace.reset(token)


def current_trace() -> RequestTrace:
    """Devolve o rastro atual ou cria um para chamadas fora da API, como testes."""

    trace = _current_trace.get()
    if trace is None:
        trace = RequestTrace(request_id=f"req_{uuid4().hex}")
        _current_trace.set(trace)
    return trace


def record_timing(component: str, milliseconds: float) -> None:
    """Registra quanto tempo um componente levou, sempre em milissegundos."""

    current_trace().timings_ms[component] = round(max(0.0, milliseconds), 3)
