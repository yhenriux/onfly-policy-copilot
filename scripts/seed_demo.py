"""Carrega todas as versões sintéticas na coleção local do Qdrant."""

import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.generation.ollama_provider import OllamaProvider
from app.ingestion.chunker import ChunkingConfig, chunk_by_section
from app.ingestion.loaders import load_catalog, load_manifest
from app.ingestion.normalizer import normalize_document
from app.ingestion.pipeline import ingest_document
from app.knowledge_graph.extractor import extract_document_graph
from app.knowledge_graph.neo4j_repository import Neo4jKnowledgeGraph
from app.retrieval.factory import build_vector_store


async def seed_demo() -> list[str]:
    """Carrega manifestos em ordem e informa o resultado de cada versão."""

    project_root = Path(__file__).resolve().parents[1]
    manifest_paths = sorted((project_root / "data" / "tenants").glob("*/metadata*.json"))
    catalog_paths = sorted((project_root / "data" / "tenants").glob("*/knowledge/catalog.json"))
    if not manifest_paths and not catalog_paths:
        raise FileNotFoundError("Nenhum manifesto de política foi encontrado")
    settings = get_settings()
    provider = OllamaProvider(
        base_url=str(settings.ollama_base_url),
        generation_model=settings.ollama_generation_model,
        embedding_model=settings.ollama_embedding_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    vector_store = build_vector_store(settings)
    graph_store = (
        Neo4jKnowledgeGraph(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
            settings.neo4j_database,
        )
        if settings.knowledge_graph_enabled
        else None
    )
    chunking_config = ChunkingConfig(
        max_chars=settings.chunk_max_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )

    try:
        messages: list[str] = []
        documents = [load_manifest(path) for path in manifest_paths]
        for catalog_path in catalog_paths:
            documents.extend(load_catalog(catalog_path))
        for document in documents:
            result = await ingest_document(
                document,
                provider=provider,
                vector_store=vector_store,
                chunking_config=chunking_config,
            )
            if graph_store is not None:
                normalized = normalize_document(document)
                await graph_store.ensure_constraints()
                await graph_store.upsert_document(
                    extract_document_graph(chunk_by_section(normalized, chunking_config))
                )
            messages.append(
                f"{result.tenant_id}:{result.version}: {result.status} "
                f"({result.chunks_indexed} trechos)"
            )
        return messages
    finally:
        await provider.close()
        vector_store.close()
        if graph_store is not None:
            await graph_store.close()


if __name__ == "__main__":
    for message in asyncio.run(seed_demo()):
        print(message)
