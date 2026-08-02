"""Testes da autenticação demonstrativa e da assinatura do token."""

import json
from pathlib import Path

import pytest

from app.core.auth import MockAuthService, hash_password
from app.core.exceptions import AuthenticationError


def _users_file(tmp_path: Path) -> Path:
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "demo.user",
                        "user_id": "user_1",
                        "tenant_id": "tenant_a",
                        "roles": ["traveler"],
                        "salt": "test-salt",
                        "password_hash": hash_password("Safe#Password1", "test-salt"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_login_produces_signed_user_and_tenant_context(tmp_path: Path) -> None:
    service = MockAuthService(_users_file(tmp_path), secret="test-secret", ttl_seconds=3600)
    token, context = service.login("demo.user", "Safe#Password1")
    authenticated = service.authenticate(token)
    assert authenticated == context
    assert authenticated.tenant_id == "tenant_a"
    assert authenticated.user_id == "user_1"


def test_auth_rejects_wrong_password_and_tampered_token(tmp_path: Path) -> None:
    service = MockAuthService(_users_file(tmp_path), secret="test-secret", ttl_seconds=3600)
    with pytest.raises(AuthenticationError, match="Credenciais inválidas"):
        service.login("demo.user", "Wrong#Password")
    token, _ = service.login("demo.user", "Safe#Password1")
    with pytest.raises(AuthenticationError, match="Token inválido"):
        service.authenticate(token + "alterado")


def test_auth_rejects_expired_token(tmp_path: Path) -> None:
    current_time = [1_000.0]
    service = MockAuthService(
        _users_file(tmp_path),
        secret="test-secret",
        ttl_seconds=60,
        clock=lambda: current_time[0],
    )
    token, _ = service.login("demo.user", "Safe#Password1")
    current_time[0] = 1_061.0
    with pytest.raises(AuthenticationError, match="Token expirado"):
        service.authenticate(token)
