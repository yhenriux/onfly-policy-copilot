"""Contrato substituível para serviços de embeddings e geração."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol

from app.domain.models import RetrievedChunk
from app.domain.schemas import GenerationOutput


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Saída validada e informações que identificam como ela foi gerada."""

    output: GenerationOutput
    provider: str
    model: str
    prompt_version: str
    attempts: int


class GenerationProvider(Protocol):
    """Operações que qualquer provedor substituto precisa implementar."""

    @property
    def provider_name(self) -> str: ...

    @property
    def generation_model(self) -> str: ...

    @property
    def prompt_version(self) -> str: ...

    def embed(self, texts: list[str]) -> Awaitable[list[list[float]]]: ...

    def generate(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> Awaitable[ProviderResult]: ...
