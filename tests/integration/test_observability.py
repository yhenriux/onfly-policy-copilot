"""Testes dos endpoints e do identificador de observabilidade."""

import httpx

from app.core.config import Settings
from app.main import create_app
from app.observability.metrics import operational_metrics


class _Readiness:
    def __init__(self, *, ollama: bool, qdrant: bool) -> None:
        self._result = {"ollama": ollama, "qdrant": qdrant}

    async def check(self) -> dict[str, bool]:
        return self._result


async def test_request_id_is_reused_and_metrics_count_requests() -> None:
    operational_metrics.reset()
    app = create_app(
        Settings(app_env="test"), readiness_checker=_Readiness(ollama=True, qdrant=True)
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health", headers={"X-Request-ID": "req_external_123"})
        metrics = await client.get("/metrics")

    assert health.headers["X-Request-ID"] == "req_external_123"
    assert metrics.json()["counters"]["requests_total"] >= 2
    assert metrics.json()["latencies"]["http_total"]["count"] >= 1


async def test_readiness_reports_each_dependency() -> None:
    app = create_app(
        Settings(app_env="test"), readiness_checker=_Readiness(ollama=True, qdrant=False)
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"ollama": True, "qdrant": False},
    }


async def test_readiness_is_successful_when_dependencies_are_available() -> None:
    app = create_app(
        Settings(app_env="test"), readiness_checker=_Readiness(ollama=True, qdrant=True)
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
