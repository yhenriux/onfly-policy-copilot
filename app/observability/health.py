"""Verifica se as dependências necessárias para responder estão prontas."""

import asyncio
from pathlib import Path
from typing import Protocol

import httpx
from qdrant_client import QdrantClient


class ReadinessChecker(Protocol):
    """Contrato pequeno para verificar Ollama e Qdrant."""

    async def check(self) -> dict[str, bool]:
        """Informa separadamente a disponibilidade de cada dependência externa."""
        ...


class LocalReadinessChecker:
    """Verifica as duas dependências usadas pela execução local."""

    def __init__(
        self,
        *,
        ollama_base_url: str,
        qdrant_mode: str = "local",
        qdrant_path: Path,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: str | None = None,
        collection: str,
    ) -> None:
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._qdrant_mode = qdrant_mode
        self._qdrant_path = qdrant_path
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._collection = collection
        self._local_qdrant_was_ready = False

    async def check(self) -> dict[str, bool]:
        """Devolve o estado separado para facilitar o diagnóstico."""

        return {
            "ollama": await self._ollama_ready(),
            "qdrant": await asyncio.to_thread(self._qdrant_ready),
        }

    async def _ollama_ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._ollama_base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            return False

    def _qdrant_ready(self) -> bool:
        try:
            client = (
                QdrantClient(url=self._qdrant_url, api_key=self._qdrant_api_key)
                if self._qdrant_mode == "server"
                else QdrantClient(path=str(self._qdrant_path))
            )
            try:
                ready = bool(client.collection_exists(self._collection))
                if self._qdrant_mode == "local" and ready:
                    self._local_qdrant_was_ready = True
                return ready
            finally:
                client.close()
        except Exception:
            # O Qdrant embutido bloqueia uma segunda abertura enquanto a API usa a pasta.
            # Nesse caso, a coleção persistida confirma que a instância ativa já a mantém aberta.
            return self._qdrant_mode == "local" and (
                self._local_qdrant_was_ready or self._local_collection_is_persisted()
            )

    def _local_collection_is_persisted(self) -> bool:
        """Confirma no disco que a coleção local esperada já foi criada."""

        return (
            (self._qdrant_path / "meta.json").is_file()
            and (self._qdrant_path / "collection" / self._collection).is_dir()
        )
