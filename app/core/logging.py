"""Mascaramento de dados que não devem aparecer em logs."""

import json
import logging
import re
from typing import Any

_SENSITIVE_KEYS = {
    "password",
    "access_token",
    "token",
    "authorization",
    "question",
    "email",
    "cpf",
    "credit_card",
}
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def mask_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    """Substitui credenciais, perguntas e dados pessoais por um marcador seguro."""

    if key is not None and key.casefold() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            item_key: mask_sensitive_data(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]
    if isinstance(value, str):
        masked = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
        return _CPF_PATTERN.sub("[REDACTED_CPF]", masked)
    return value


def log_structured(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Escreve JSON pesquisável depois de remover campos sensíveis."""

    payload = mask_sensitive_data({"event": event, **fields})
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
