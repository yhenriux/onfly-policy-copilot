"""Persistência local dos metadados técnicos de cada resposta."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.domain.schemas import AskResponse


class ObservabilityStore:
    """Guarda métricas por resposta sem armazenar perguntas ou respostas."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS response_observations (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    sources_count INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    timings_json TEXT NOT NULL,
                    documents_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(response_observations)")
            }
            if "documents_json" not in columns:
                connection.execute(
                    "ALTER TABLE response_observations ADD COLUMN documents_json "
                    "TEXT NOT NULL DEFAULT '[]'"
                )

    def record(
        self,
        response: AskResponse,
        *,
        session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Registra uma resposta e seus dados técnicos agregáveis."""

        trace = response.trace
        if trace is None:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO response_observations
                (request_id, session_id, tenant_id, user_id, created_at, status,
                 confidence, latency_ms, sources_count, output_tokens, timings_json, documents_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.request_id,
                    session_id,
                    tenant_id,
                    user_id,
                    datetime.now(UTC).isoformat(),
                    response.generation.status,
                    response.confidence,
                    response.latency_ms,
                    len(response.sources),
                    trace.estimated_output_tokens,
                    _json_dumps(trace.timings_ms),
                    json.dumps(
                        [document.model_dump() for document in trace.documents],
                        separators=(",", ":"),
                    ),
                ),
            )

    def sessions(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Lista sessões com volume e latência média mais recente."""

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, tenant_id, user_id, COUNT(*) AS responses,
                       MIN(created_at) AS started_at, MAX(created_at) AS last_activity,
                       ROUND(AVG(latency_ms), 1) AS average_latency_ms
                FROM response_observations
                GROUP BY session_id, tenant_id, user_id
                ORDER BY last_activity DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def responses(self, *, session_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Lista respostas individuais, opcionalmente filtradas por sessão."""

        query = """
            SELECT request_id, session_id, tenant_id, user_id, created_at, status,
                   confidence, latency_ms, sources_count, output_tokens,
                   timings_json, documents_json
            FROM response_observations
        """
        parameters: tuple[Any, ...] = ()
        if session_id:
            query += " WHERE session_id = ?"
            parameters = (session_id,)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters += (limit,)
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                **dict(row),
                "timings_ms": _json_loads(row["timings_json"]),
                "documents": json.loads(row["documents_json"]),
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection


def _json_dumps(value: dict[str, float]) -> str:
    return json.dumps(value, separators=(",", ":"))


def _json_loads(value: str) -> dict[str, float]:
    decoded = json.loads(value)
    return {str(key): float(item) for key, item in decoded.items()}
