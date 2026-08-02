"""Configuração opcional do LangSmith, desativada por padrão."""

import os

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
