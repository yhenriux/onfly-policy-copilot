"""Testes das configurações validadas da aplicação."""

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings, get_settings


class _SettingsWithoutDotEnv(Settings):
    """Configuração de teste que ignora o arquivo `.env` local."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")


def test_settings_use_expected_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_PORT", raising=False)
    monkeypatch.delenv("OLLAMA_GENERATION_MODEL", raising=False)
    monkeypatch.delenv("RETRIEVAL_TOP_K", raising=False)
    monkeypatch.delenv("CONTEXT_TOP_K", raising=False)

    settings = _SettingsWithoutDotEnv()

    assert settings.app_port == 8000
    assert settings.ollama_generation_model == "llama3.2:3b"
    assert settings.retrieval_top_k == 10
    assert settings.context_top_k == 10


def test_settings_read_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "12.5")

    settings = _SettingsWithoutDotEnv()

    assert settings.app_env == "test"
    assert settings.app_port == 9000
    assert settings.ollama_timeout_seconds == 12.5


def test_settings_reject_context_larger_than_retrieval() -> None:
    with pytest.raises(ValidationError, match="context_top_k must not exceed retrieval_top_k"):
        _SettingsWithoutDotEnv(retrieval_top_k=3, context_top_k=4)


def test_settings_reject_overlap_larger_than_chunk() -> None:
    with pytest.raises(ValidationError, match="chunk_overlap_chars"):
        _SettingsWithoutDotEnv(chunk_max_chars=400, chunk_overlap_chars=400)


def test_settings_rejects_two_disabled_retrievers() -> None:
    with pytest.raises(ValidationError, match="Ao menos um peso"):
        _SettingsWithoutDotEnv(dense_weight=0, lexical_weight=0)


def test_settings_rejects_invalid_rerank_limits() -> None:
    with pytest.raises(ValidationError, match="rerank_top_n"):
        _SettingsWithoutDotEnv(retrieval_top_k=5, context_top_k=5, rerank_top_n=6)
    with pytest.raises(ValidationError, match="context_top_k"):
        _SettingsWithoutDotEnv(retrieval_top_k=10, context_top_k=6, rerank_top_n=5)


def test_qdrant_api_key_is_masked() -> None:
    settings = _SettingsWithoutDotEnv(qdrant_api_key=SecretStr("synthetic-test-key"))

    assert "synthetic-test-key" not in repr(settings)
    assert settings.qdrant_api_key is not None
    assert settings.qdrant_api_key.get_secret_value() == "synthetic-test-key"


def test_get_settings_reuses_process_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()

    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
