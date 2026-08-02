"""Autenticação demonstrativa com usuários sintéticos e tokens assinados."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import AuthenticationError
from app.domain.schemas import AuthenticatedContext


class _MockUser(BaseModel):
    """Registro sintético armazenado sem senha em texto aberto."""

    model_config = ConfigDict(extra="forbid")

    username: str
    user_id: str
    tenant_id: str
    roles: list[str]
    salt: str
    password_hash: str


class _MockUsers(BaseModel):
    users: list[_MockUser]


class MockAuthService:
    """Valida logins locais e assina o contexto com HMAC-SHA256."""

    def __init__(
        self,
        users_path: Path,
        *,
        secret: str,
        ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        data = json.loads(users_path.read_text(encoding="utf-8"))
        self._users = {user.username: user for user in _MockUsers.model_validate(data).users}
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def login(self, username: str, password: str) -> tuple[str, AuthenticatedContext]:
        """Compara a senha por hash e devolve um token com prazo de validade."""

        user = self._users.get(username)
        if user is None or not hmac.compare_digest(
            user.password_hash,
            hash_password(password, user.salt),
        ):
            raise AuthenticationError("Credenciais inválidas")
        context = AuthenticatedContext(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            roles=user.roles,
        )
        return self._encode(context), context

    def authenticate(self, token: str) -> AuthenticatedContext:
        """Valida assinatura e expiração antes de confiar no contexto."""

        try:
            encoded_payload, encoded_signature = token.split(".", maxsplit=1)
            expected = hmac.new(self._secret, encoded_payload.encode(), hashlib.sha256).digest()
            signature = _decode_bytes(encoded_signature)
            if not hmac.compare_digest(signature, expected):
                raise AuthenticationError("Token inválido")
            payload = json.loads(_decode_bytes(encoded_payload))
            if int(payload["exp"]) < int(self._clock()):
                raise AuthenticationError("Token expirado")
            return AuthenticatedContext.model_validate(payload["context"])
        except AuthenticationError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise AuthenticationError("Token inválido") from error

    def _encode(self, context: AuthenticatedContext) -> str:
        payload: dict[str, Any] = {
            "exp": int(self._clock()) + self._ttl_seconds,
            "context": context.model_dump(),
        }
        encoded_payload = _encode_bytes(json.dumps(payload, separators=(",", ":")).encode())
        signature = hmac.new(self._secret, encoded_payload.encode(), hashlib.sha256).digest()
        return f"{encoded_payload}.{_encode_bytes(signature)}"


def hash_password(password: str, salt: str) -> str:
    """Cria um hash PBKDF2, uma comparação lenta contra tentativa de adivinhação."""

    result = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return result.hex()


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
