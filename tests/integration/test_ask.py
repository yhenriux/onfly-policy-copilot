"""Testes integrados do contrato HTTP de perguntas e respostas."""

import httpx

from app.core.config import Settings
from app.core.exceptions import OllamaUnavailableError
from app.domain.schemas import (
    AskRequest,
    AskResponse,
    AuthenticatedContext,
    GenerationMetadata,
    SourceReference,
)
from app.main import create_app


class _SuccessfulAskHandler:
    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        assert context.tenant_id == "aurora_tecnologia"
        return AskResponse(
            answer="O reembolso deve ser solicitado em até 10 dias úteis.",
            sources=[
                SourceReference(
                    document_id="politica_viagens_aurora_v1",
                    title="Política corporativa de viagens — Aurora Tecnologia",
                    version="v1",
                    chunk_id="chunk_004_demo",
                    section="Reembolso",
                    score=0.88,
                )
            ],
            confidence="high",
            request_id="req_test",
            latency_ms=12,
            generation=GenerationMetadata(
                provider="ollama",
                model="llama3.2:1b",
                prompt_version="policy_answer_v1",
                status="generated",
                attempts=1,
            ),
        )


class _UnavailableAskHandler:
    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        raise OllamaUnavailableError("connection refused")


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/v1/auth/login",
        json={"username": "aurora.demo", "password": "Aurora#2026"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_ask_returns_grounded_json() -> None:
    application = create_app(Settings(app_env="test"), ask_handler=_SuccessfulAskHandler())
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _login(client)
        response = await client.post(
            "/v1/ask",
            json={"question": "Em quanto tempo devo solicitar o reembolso?"},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("O reembolso")
    assert payload["sources"][0]["document_id"] == "politica_viagens_aurora_v1"
    assert payload["sources"][0]["version"] == "v1"
    assert payload["confidence"] == "high"
    assert payload["generation"]["prompt_version"] == "policy_answer_v1"


async def test_ask_rejects_invalid_input() -> None:
    application = create_app(Settings(app_env="test"), ask_handler=_SuccessfulAskHandler())
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _login(client)
        response = await client.post(
            "/v1/ask",
            json={"question": "x"},
            headers=headers,
        )

    assert response.status_code == 422


async def test_ask_returns_503_when_ollama_is_unavailable() -> None:
    application = create_app(Settings(app_env="test"), ask_handler=_UnavailableAskHandler())
    transport = httpx.ASGITransport(app=application)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _login(client)
        response = await client.post(
            "/v1/ask",
            json={"question": "Qual é o limite de alimentação?"},
            headers=headers,
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "O modelo local está temporariamente indisponível."}


async def test_ask_requires_authentication_and_rejects_body_tenant() -> None:
    application = create_app(Settings(app_env="test"), ask_handler=_SuccessfulAskHandler())
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.post("/v1/ask", json={"question": "Qual é a regra?"})
        headers = await _login(client)
        forged = await client.post(
            "/v1/ask",
            json={"question": "Qual é a regra?", "tenant_id": "brisa_sistemas"},
            headers=headers,
        )
    assert unauthorized.status_code == 401
    assert forged.status_code == 422
