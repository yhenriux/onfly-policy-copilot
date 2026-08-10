"""Configurações da aplicação lidas das variáveis de ambiente."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações validadas antes de iniciar a aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Onfly Policy Copilot"
    app_version: str = "1.0.0"
    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65_535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    web_root: Path = Path("app/web")
    auth_users_path: Path = Path("data/auth/mock_users.json")
    auth_token_secret: SecretStr = SecretStr("local-demo-secret-change-me")
    auth_token_ttl_seconds: int = Field(default=3_600, ge=60, le=86_400)

    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    ollama_generation_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "all-minilm"
    ollama_timeout_seconds: float = Field(default=60.0, gt=0)
    ollama_retry_attempts: int = Field(default=3, ge=1, le=10)
    ollama_retry_backoff_seconds: float = Field(default=0.25, ge=0, le=30)
    llm_integration: Literal["http", "langchain"] = "langchain"
    workflow_engine: Literal["service", "langgraph"] = "langgraph"

    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "onfly-policy-copilot"

    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://localhost:6333")
    qdrant_mode: Literal["local", "server"] = "local"
    qdrant_path: Path = Path(".local/qdrant")
    qdrant_collection: str = "onfly_policy_documents_phase3"
    qdrant_api_key: SecretStr | None = None

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "onfly.ingestion"
    rabbitmq_queue: str = "onfly.ingestion.jobs"
    rabbitmq_dead_letter_queue: str = "onfly.ingestion.dead-letter"
    rabbitmq_prefetch_count: int = Field(default=1, ge=1, le=100)
    rabbitmq_retry_attempts: int = Field(default=3, ge=1, le=10)
    rabbitmq_retry_delay_seconds: int = Field(default=5, ge=0, le=3_600)

    redis_url: str = "redis://localhost:6379/0"
    redis_job_ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    ingestion_storage_path: Path = Path(".local/ingestion")
    observability_db_path: Path = Path(".local/ingestion/observability.sqlite")
    ingestion_max_file_bytes: int = Field(default=10_000_000, ge=1_024, le=100_000_000)

    knowledge_graph_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("local-demo-password-change-me")
    neo4j_database: str = "neo4j"

    retrieval_top_k: int = Field(default=10, ge=1, le=100)
    context_top_k: int = Field(default=10, ge=1, le=50)
    rrf_k: int = Field(default=60, ge=1, le=1_000)
    dense_weight: float = Field(default=1.0, ge=0, le=10)
    lexical_weight: float = Field(default=1.0, ge=0, le=10)
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    rerank_top_n: int = Field(default=10, ge=1, le=100)
    max_context_characters: int = Field(default=5_000, ge=200, le=50_000)
    context_redundancy_threshold: float = Field(default=0.8, gt=0, le=1)
    evidence_min_score: float = Field(default=0.5, ge=0, le=1)
    generation_max_evidence_chunks: int = Field(default=3, ge=1, le=10)
    chunk_max_chars: int = Field(default=650, ge=200, le=4_000)
    chunk_overlap_chars: int = Field(default=100, ge=0, le=1_000)
    max_question_length: int = Field(default=2_000, ge=1, le=20_000)

    @model_validator(mode="after")
    def validate_retrieval_limits(self) -> Self:
        """Impede selecionar mais trechos do que a busca recuperou."""

        if self.context_top_k > self.retrieval_top_k:
            raise ValueError("context_top_k must not exceed retrieval_top_k")
        if self.rerank_top_n > self.retrieval_top_k:
            raise ValueError("rerank_top_n deve ser menor ou igual a retrieval_top_k")
        if self.context_top_k > self.rerank_top_n:
            raise ValueError("context_top_k deve ser menor ou igual a rerank_top_n")
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("chunk_overlap_chars deve ser menor que chunk_max_chars")
        if self.dense_weight + self.lexical_weight == 0:
            raise ValueError("Ao menos um peso da recuperação deve ser positivo")
        return self


@lru_cache
def get_settings() -> Settings:
    """Reutiliza a mesma configuração durante a execução do processo."""

    return Settings()
