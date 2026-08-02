"""Testes do mascaramento antes de registrar dados em logs."""

from app.core.logging import mask_sensitive_data


def test_mask_sensitive_fields_and_personal_data() -> None:
    event = {
        "password": "secret",
        "authorization": "Bearer token",
        "question": "Meu CPF é 123.456.789-00",
        "message": "Contato pessoa@example.com ou CPF 12345678900",
        "tenant_id": "aurora_tecnologia",
    }
    masked = mask_sensitive_data(event)
    rendered = str(masked)
    assert "secret" not in rendered
    assert "Bearer token" not in rendered
    assert "123.456.789-00" not in rendered
    assert "12345678900" not in rendered
    assert "pessoa@example.com" not in rendered
    assert masked["tenant_id"] == "aurora_tecnologia"
