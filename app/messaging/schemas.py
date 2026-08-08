"""Contratos versionados usados na fila de ingestão."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class IngestionJob(BaseModel):
    """Mensagem que identifica um documento persistido no storage compartilhado."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    job_id: UUID = Field(default_factory=uuid4)
    request_id: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    document_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    manifest_path: str = Field(min_length=1, max_length=1_000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attempt: int = Field(default=0, ge=0, le=10)


class IngestionJobStatus(BaseModel):
    """Estado consultável de um job, armazenado no Redis."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    request_id: str
    tenant_id: str
    document_id: str
    version: str
    status: Literal["queued", "processing", "completed", "skipped", "failed", "dead_lettered"]
    chunks_indexed: int = 0
    detail: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
