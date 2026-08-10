"""Implementação do provedor local usando a API HTTP do Ollama."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.exceptions import OllamaUnavailableError
from app.domain.models import RetrievedChunk
from app.domain.schemas import GenerationOutput
from app.generation.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.generation.provider import ProviderResult

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
SleepFunction = Callable[[float], Awaitable[None]]


class _EmbedResponse(BaseModel):
    embeddings: list[list[float]]


class _ChatMessage(BaseModel):
    content: str


class _ChatResponse(BaseModel):
    message: _ChatMessage


class OllamaProvider:
    """Adapta o Ollama ao contrato comum com timeout e novas tentativas."""

    def __init__(
        self,
        *,
        base_url: str,
        generation_model: str,
        embedding_model: str,
        timeout_seconds: float,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.25,
        client: httpx.AsyncClient | None = None,
        sleep: SleepFunction = asyncio.sleep,
    ) -> None:
        self._generation_model = generation_model
        self._embedding_model = embedding_model
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    @property
    def provider_name(self) -> str:
        """Identifica a implementação usada nesta execução."""

        return "ollama"

    @property
    def generation_model(self) -> str:
        """Identifica o modelo local responsável pela resposta."""

        return self._generation_model

    @property
    def prompt_version(self) -> str:
        """Identifica as instruções usadas na geração."""

        return PROMPT_VERSION

    async def _request(
        self,
        path: str,
        body: dict[str, Any],
        response_model: type[ResponseModel],
        *,
        operation: str,
    ) -> tuple[ResponseModel, int]:
        """Repete falhas transitórias com espera progressiva entre tentativas."""

        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, self._retry_attempts + 1):
            attempts_used = attempt
            try:
                response = await self._client.post(path, json=body)
                response.raise_for_status()
                return response_model.model_validate(response.json()), attempt
            except (httpx.HTTPError, ValidationError, ValueError) as error:
                last_error = error
                if not _is_transient(error) or attempt == self._retry_attempts:
                    break
                await self._sleep(self._retry_backoff_seconds * (2 ** (attempt - 1)))
        raise OllamaUnavailableError(
            f"Ollama {operation} request failed after {attempts_used} attempts",
            attempts=attempts_used,
        ) from last_error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Gera um vetor numérico de significado para cada texto."""

        payload, _ = await self._request(
            "/api/embed",
            {"model": self._embedding_model, "input": texts},
            _EmbedResponse,
            operation="embedding",
        )
        if len(payload.embeddings) != len(texts):
            raise OllamaUnavailableError("Ollama returned an unexpected embedding count")
        return payload.embeddings

    async def generate(
        self,
        question: str,
        chunks: list[RetrievedChunk],
    ) -> ProviderResult:
        """Gera e valida uma resposta JSON baseada somente nas evidências."""

        chat, attempts = await self._request(
            "/api/chat",
            {
                "model": self._generation_model,
                "stream": False,
                "format": GenerationOutput.model_json_schema(),
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(question, chunks)},
                ],
            },
            _ChatResponse,
            operation="generation",
        )
        try:
            output = GenerationOutput.model_validate_json(chat.message.content)
        except (ValidationError, ValueError) as error:
            raise OllamaUnavailableError(
                "Ollama returned invalid structured output", attempts=attempts
            ) from error
        if output.evidence_found and output.confidence == "low":
            # Uma fonte citada indica suporte parcial; low fica reservado para ausência de suporte.
            output = output.model_copy(update={"confidence": "medium"})
        return ProviderResult(
            output=output,
            provider=self.provider_name,
            model=self.generation_model,
            prompt_version=self.prompt_version,
            attempts=attempts,
        )

    async def close(self) -> None:
        """Fecha as conexões HTTP usadas pelo cliente."""

        await self._client.aclose()


def _is_transient(error: Exception) -> bool:
    """Distingue falhas que podem melhorar em uma nova tentativa."""

    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return isinstance(
        error, (httpx.TimeoutException, httpx.NetworkError, ValidationError, ValueError)
    )
