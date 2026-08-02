"""Comando para carregar um manifesto de documento na base de pesquisa."""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.generation.ollama_provider import OllamaProvider
from app.ingestion.chunker import ChunkingConfig
from app.ingestion.loaders import load_manifest
from app.ingestion.pipeline import ingest_document
from app.retrieval.factory import build_vector_store


async def ingest_manifest(manifest_path: Path) -> str:
    """Carrega um manifesto e devolve um resumo simples do resultado."""

    settings = get_settings()
    provider = OllamaProvider(
        base_url=str(settings.ollama_base_url),
        generation_model=settings.ollama_generation_model,
        embedding_model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    vector_store = build_vector_store(settings)
    try:
        result = await ingest_document(
            load_manifest(manifest_path),
            provider=provider,
            vector_store=vector_store,
            chunking_config=ChunkingConfig(
                max_chars=settings.chunk_max_chars,
                overlap_chars=settings.chunk_overlap_chars,
            ),
        )
        return (
            f"{result.tenant_id}:{result.version}: {result.status} "
            f"({result.chunks_indexed} trechos)"
        )
    finally:
        await provider.close()
        vector_store.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carrega uma política pelo manifesto JSON")
    parser.add_argument("manifest", type=Path, help="Caminho do arquivo metadata*.json")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    print(asyncio.run(ingest_manifest(arguments.manifest)))
