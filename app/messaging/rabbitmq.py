"""Publicação de jobs de ingestão no RabbitMQ."""

import json
from typing import Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.messaging.schemas import IngestionJob


class JobPublisher(Protocol):
    async def publish(self, job: IngestionJob) -> None: ...


class RabbitMQPublisher:
    """Declara uma fila durável e publica mensagens persistentes."""

    def __init__(
        self, url: str, exchange_name: str, queue_name: str, dead_letter_queue: str
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._dead_letter_queue = dead_letter_queue
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def _channel_or_connect(self) -> aio_pika.abc.AbstractChannel:
        if self._channel is None or self._channel.is_closed:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            exchange = await self._channel.declare_exchange(
                self._exchange_name, ExchangeType.DIRECT, durable=True
            )
            await self._channel.declare_queue(self._dead_letter_queue, durable=True)
            queue = await self._channel.declare_queue(self._queue_name, durable=True)
            await queue.bind(exchange, routing_key=self._queue_name)
            dead_letter = await self._channel.get_queue(self._dead_letter_queue)
            await dead_letter.bind(exchange, routing_key=self._dead_letter_queue)
        return self._channel

    async def publish(self, job: IngestionJob) -> None:
        channel = await self._channel_or_connect()
        exchange = await channel.get_exchange(self._exchange_name)
        await exchange.publish(
            Message(
                body=json.dumps(job.model_dump(mode="json")).encode(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=str(job.job_id),
            ),
            routing_key=self._queue_name,
        )

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
