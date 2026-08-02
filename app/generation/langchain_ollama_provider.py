"""Adaptador LangChain para os modelos locais do Ollama."""

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.core.exceptions import OllamaUnavailableError
from app.domain.models import RetrievedChunk
from app.domain.schemas import GenerationOutput
from app.generation.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.generation.provider import ProviderResult


class LangChainOllamaProvider:
    """Mantém o contrato interno e delega modelos e embeddings ao LangChain."""

    def __init__(
        self,
        *,
        base_url: str,
        generation_model: str,
        embedding_model: str,
        timeout_seconds: float,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.25,
        chat_model: Any | None = None,
        embeddings: Any | None = None,
    ) -> None:
        self._generation_model = generation_model
        self._embedding_model = embedding_model
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._chat_model = chat_model or ChatOllama(
            model=generation_model,
            base_url=base_url,
            temperature=0,
            client_kwargs={"timeout": timeout_seconds},
        )
        self._embeddings = embeddings or OllamaEmbeddings(
            model=embedding_model,
            base_url=base_url,
            client_kwargs={"timeout": timeout_seconds},
        )
        self._structured_chat = self._chat_model.with_structured_output(GenerationOutput)

    @property
    def provider_name(self) -> str:
        """Identifica nos traces que a integração passou pelo LangChain."""
        return "langchain-ollama"

    @property
    def generation_model(self) -> str:
        """Expõe o modelo local usado para permitir auditoria da resposta."""
        return self._generation_model

    @property
    def prompt_version(self) -> str:
        """Relaciona cada resposta à versão das instruções enviadas ao modelo."""
        return PROMPT_VERSION

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Converte textos em vetores usando a interface padronizada do LangChain."""
        try:
            vectors = await self._embeddings.aembed_documents(texts)
            return [[float(value) for value in vector] for vector in vectors]
        except Exception as error:
            raise OllamaUnavailableError(
                "Falha ao gerar embeddings pelo LangChain", attempts=1
            ) from error

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> ProviderResult:
        """Gera saída estruturada somente com os trechos autorizados pelo retrieval."""
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_prompt(question, chunks)),
        ]
        last_error: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                output = await self._structured_chat.ainvoke(messages)
                validated = (
                    output
                    if isinstance(output, GenerationOutput)
                    else GenerationOutput.model_validate(output)
                )
                return ProviderResult(
                    output=validated,
                    provider=self.provider_name,
                    model=self.generation_model,
                    prompt_version=self.prompt_version,
                    attempts=attempt,
                )
            except Exception as error:
                last_error = error
                if attempt < self._retry_attempts:
                    await asyncio.sleep(self._retry_backoff_seconds * (2 ** (attempt - 1)))
        raise OllamaUnavailableError(
            "Falha ao gerar resposta pelo LangChain", attempts=self._retry_attempts
        ) from last_error

    async def close(self) -> None:
        """O cliente LangChain/Ollama não exige encerramento explícito."""
