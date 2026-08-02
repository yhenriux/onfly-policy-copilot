"""Testes integrados da disponibilidade e da documentação da API."""

import httpx

from app.core.config import Settings
from app.main import create_app


async def test_health_reports_api_availability() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(app_env="test")))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Onfly Policy Copilot"}


async def test_health_is_documented_in_openapi() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(app_env="test")))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
