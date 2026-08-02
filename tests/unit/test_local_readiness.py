"""Testes da prontidão do Qdrant embutido durante consultas concorrentes."""

from pathlib import Path
from typing import Any

import pytest

import app.observability.health as health_module
from app.observability.health import LocalReadinessChecker


class _ReadyClient:
    def __init__(self, **kwargs: Any) -> None:
        pass

    def collection_exists(self, collection: str) -> bool:
        return True

    def close(self) -> None:
        pass


class _LockedClient:
    def __init__(self, **kwargs: Any) -> None:
        raise RuntimeError("pasta bloqueada pelo cliente ativo")


def test_local_readiness_reuses_last_success_during_file_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = LocalReadinessChecker(
        ollama_base_url="http://localhost:11434",
        qdrant_path=Path(".local/qdrant"),
        collection="policies",
    )
    monkeypatch.setattr(health_module, "QdrantClient", _ReadyClient)
    assert checker._qdrant_ready() is True

    monkeypatch.setattr(health_module, "QdrantClient", _LockedClient)
    assert checker._qdrant_ready() is True


def test_server_readiness_does_not_hide_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = LocalReadinessChecker(
        ollama_base_url="http://localhost:11434",
        qdrant_mode="server",
        qdrant_path=Path(".local/qdrant"),
        qdrant_url="http://qdrant:6333",
        collection="policies",
    )
    monkeypatch.setattr(health_module, "QdrantClient", _LockedClient)

    assert checker._qdrant_ready() is False
