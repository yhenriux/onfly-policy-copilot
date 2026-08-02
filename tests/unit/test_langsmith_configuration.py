"""Testes para garantir que LangSmith seja sempre uma escolha explícita."""

import os

import pytest

from app.core.config import Settings
from app.observability.langsmith import configure_langsmith


def test_langsmith_stays_disabled_without_explicit_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    configure_langsmith(Settings(langsmith_tracing=False))
    assert os.environ.get("LANGSMITH_TRACING") is None


def test_langsmith_requires_key_when_enabled() -> None:
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        configure_langsmith(Settings(langsmith_tracing=True))
