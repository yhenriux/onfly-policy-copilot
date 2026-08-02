"""Configuração opcional do LangSmith, desativada por padrão."""

import os

from langsmith import traceable

from app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    """Ativa tracing remoto somente com escolha explícita e chave configurada."""

    if not settings.langsmith_tracing:
        return
    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    if not api_key:
        raise ValueError("LANGSMITH_API_KEY é obrigatória quando LANGSMITH_TRACING=true")
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    # A demonstração rastreia etapas, duração e resultado, sem enviar o texto da
    # pergunta, da resposta ou das políticas para o serviço remoto.
    os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"


@traceable(name="onfly_policy_copilot_user_event", run_type="tool")
def trace_user_event(event: str) -> None:
    """Cria no LangSmith um evento de jornada que não contém conteúdo do usuário."""


@traceable(name="onfly_policy_copilot_quality_signal", run_type="chain")
def trace_quality_signal(
    *, status: str, confidence: str, source_count: int, top1_score: float
) -> None:
    """Registra um sinal de qualidade seguro para acompanhar tendências no LangSmith."""
