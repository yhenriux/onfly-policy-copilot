"""Testes integrados da interface e do feedback ligado à requisição."""

import httpx

from app.core.config import Settings
from app.domain.schemas import (
    AskRequest,
    AskResponse,
    AuthenticatedContext,
    GenerationMetadata,
)
from app.feedback.store import InMemoryFeedbackStore
from app.main import create_app


class _FrontendAskHandler:
    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        return AskResponse(
            answer="Resposta sintética para a interface.",
            sources=[],
            confidence="low",
            request_id="req_frontend_demo",
            latency_ms=15,
            generation=GenerationMetadata(
                provider="ollama",
                model="llama3.2:1b",
                prompt_version="policy_answer_v1",
                status="no_evidence",
                attempts=0,
            ),
        )


async def _login(client: httpx.AsyncClient, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_frontend_and_static_assets_are_served() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(app_env="test")))

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get("/")
        script = await client.get("/static/app.js")
        styles = await client.get("/static/styles.css")

    assert page.status_code == 200
    assert "Em qual empresa você trabalha?" in page.text
    assert "50" in page.text
    assert "regras conflitantes" not in page.text.lower()
    assert "tenant" not in page.text.lower()
    assert script.status_code == 200
    assert "textContent" in script.text
    assert styles.status_code == 200
    assert "--primary" in styles.text


async def test_feedback_is_linked_to_authenticated_request() -> None:
    store = InMemoryFeedbackStore()
    application = create_app(
        Settings(app_env="test"),
        ask_handler=_FrontendAskHandler(),
        feedback_store=store,
    )
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _login(client, "aurora.demo", "Aurora#2026")
        answer = await client.post(
            "/v1/ask",
            json={"question": "Qual é a regra de reembolso?"},
            headers=headers,
        )
        feedback = await client.post(
            "/v1/feedback",
            json={"request_id": answer.json()["request_id"], "rating": "positive"},
            headers=headers,
        )

    assert feedback.status_code == 201
    assert feedback.json()["request_id"] == "req_frontend_demo"
    assert store.records()[0].tenant_id == "aurora_tecnologia"
    assert store.records()[0].rating == "positive"


async def test_authenticated_interface_event_is_counted_without_conversation_content() -> None:
    from app.observability.metrics import operational_metrics

    operational_metrics.reset()
    application = create_app(Settings(app_env="test"))
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _login(client, "aurora.demo", "Aurora#2026")
        response = await client.post(
            "/v1/telemetry",
            json={"event": "quick_question_selected"},
            headers=headers,
        )
        metrics = await client.get("/metrics")

    assert response.status_code == 204
    assert metrics.json()["counters"]["user_event_quick_question_selected_total"] == 1


async def test_feedback_cannot_cross_tenants_or_use_unknown_request() -> None:
    store = InMemoryFeedbackStore()
    application = create_app(
        Settings(app_env="test"),
        ask_handler=_FrontendAskHandler(),
        feedback_store=store,
    )
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        aurora = await _login(client, "aurora.demo", "Aurora#2026")
        await client.post(
            "/v1/ask",
            json={"question": "Qual é a regra de reembolso?"},
            headers=aurora,
        )
        brisa = await _login(client, "brisa.demo", "Brisa#2026")
        crossed = await client.post(
            "/v1/feedback",
            json={"request_id": "req_frontend_demo", "rating": "negative"},
            headers=brisa,
        )
        unknown = await client.post(
            "/v1/feedback",
            json={"request_id": "req_unknown_demo", "rating": "negative"},
            headers=aurora,
        )

    assert crossed.status_code == 404
    assert unknown.status_code == 404
    assert store.records() == []
