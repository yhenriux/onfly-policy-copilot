"""Persistência leve do estado dos jobs de ingestão."""

import json
from typing import Protocol

from redis.asyncio import Redis

from app.messaging.schemas import IngestionJobStatus


class JobStatusStore(Protocol):
    async def set(self, status: IngestionJobStatus) -> None: ...

    async def get(self, job_id: str) -> IngestionJobStatus | None: ...


class RedisJobStatusStore:
    """Armazena cada estado com TTL para não acumular jobs indefinidamente."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._redis: Redis = Redis.from_url(url, decode_responses=True)
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"onfly:ingestion:job:{job_id}"

    async def set(self, status: IngestionJobStatus) -> None:
        await self._redis.set(
            self._key(str(status.job_id)),
            status.model_dump_json(),
            ex=self._ttl_seconds,
        )

    async def get(self, job_id: str) -> IngestionJobStatus | None:
        raw = await self._redis.get(self._key(job_id))
        return IngestionJobStatus.model_validate(json.loads(raw)) if raw else None

    async def close(self) -> None:
        await self._redis.aclose()
