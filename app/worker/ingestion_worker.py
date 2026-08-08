"""Consumidor RabbitMQ que executa o pipeline de ingestão existente."""

import asyncio
import json
import logging
from pathlib import Path

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import get_settings
from app.generation.ollama_provider import OllamaProvider
from app.ingestion.chunker import ChunkingConfig, chunk_by_section
from app.ingestion.loaders import load_manifest
from app.ingestion.normalizer import normalize_document
from app.ingestion.pipeline import ingest_document
from app.knowledge_graph.extractor import extract_document_graph
from app.knowledge_graph.neo4j_repository import Neo4jKnowledgeGraph
from app.messaging.redis_store import RedisJobStatusStore
from app.messaging.schemas import IngestionJob, IngestionJobStatus
from app.retrieval.factory import build_vector_store

logger = logging.getLogger(__name__)


async def process_job(job: IngestionJob) -> IngestionJobStatus:
    """Executa uma mensagem e garante o fechamento dos clientes externos."""

    settings = get_settings()
    status_store = RedisJobStatusStore(settings.redis_url, settings.redis_job_ttl_seconds)
    processing = IngestionJobStatus(
        job_id=job.job_id,
        request_id=job.request_id,
        tenant_id=job.tenant_id,
        document_id=job.document_id,
        version=job.version,
        status="processing",
    )
    await status_store.set(processing)
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
    try:
        loaded = load_manifest(Path(job.manifest_path))
        if loaded.tenant_id != job.tenant_id:
            raise ValueError("O tenant do manifesto não corresponde ao tenant do job")
        result = await ingest_document(
            loaded,
            provider=provider,
            vector_store=vector_store,
            chunking_config=ChunkingConfig(
                max_chars=settings.chunk_max_chars,
                overlap_chars=settings.chunk_overlap_chars,
            ),
        )
        if graph_store is not None:
            normalized = normalize_document(loaded)
            chunks = chunk_by_section(
                normalized,
                ChunkingConfig(
                    max_chars=settings.chunk_max_chars,
                    overlap_chars=settings.chunk_overlap_chars,
                ),
            )
            await graph_store.ensure_constraints()
            await graph_store.upsert_document(extract_document_graph(chunks))
        completed = processing.model_copy(
            update={
                "status": "skipped" if result.status == "skipped" else "completed",
                "chunks_indexed": result.chunks_indexed,
            }
        )
        await status_store.set(completed)
        return completed
    except Exception as error:
        failed = processing.model_copy(update={"status": "failed", "detail": str(error)[:500]})
        await status_store.set(failed)
        raise
    finally:
        await provider.close()
        vector_store.close()
        if graph_store is not None:
            await graph_store.close()
        await status_store.close()


async def run() -> None:
    """Mantém o consumidor ativo até receber cancelamento do processo."""

    settings = get_settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=settings.rabbitmq_prefetch_count)
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange, ExchangeType.DIRECT, durable=True
    )
    queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)
    dead_letter = await channel.declare_queue(settings.rabbitmq_dead_letter_queue, durable=True)
    await queue.bind(exchange, routing_key=settings.rabbitmq_queue)
    await dead_letter.bind(exchange, routing_key=settings.rabbitmq_dead_letter_queue)

    async with queue.iterator() as messages:
        async for message in messages:
            forwarded = False
            try:
                job = IngestionJob.model_validate(json.loads(message.body))
                await process_job(job)
            except Exception:
                logger.exception("Falha ao processar job de ingestão")
                try:
                    job = IngestionJob.model_validate(json.loads(message.body))
                    destination = (
                        settings.rabbitmq_queue
                        if job.attempt < settings.rabbitmq_retry_attempts
                        else settings.rabbitmq_dead_letter_queue
                    )
                    if destination == settings.rabbitmq_queue:
                        await asyncio.sleep(settings.rabbitmq_retry_delay_seconds)
                    retry = job.model_copy(update={"attempt": job.attempt + 1})
                    await exchange.publish(
                        Message(
                            body=json.dumps(retry.model_dump(mode="json")).encode(),
                            content_type="application/json",
                            delivery_mode=DeliveryMode.PERSISTENT,
                            message_id=str(job.job_id),
                        ),
                        routing_key=destination,
                    )
                    forwarded = True
                except Exception:
                    logger.exception("Falha ao encaminhar job para retry ou DLQ")
            finally:
                if forwarded:
                    await message.ack()
                else:
                    await message.nack(requeue=True)


if __name__ == "__main__":
    asyncio.run(run())
