"""Regras de validação para dados recebidos e devolvidos pela aplicação."""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AskRequest(BaseModel):
    """Pergunta enviada; usuário e empresa vêm somente da autenticação."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=2_000)


class LoginRequest(BaseModel):
    """Credenciais sintéticas usadas apenas na demonstração local."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class AuthenticatedContext(BaseModel):
    """Identidade confiável extraída de um token assinado."""

    user_id: str
    tenant_id: str
    roles: list[str]


class TokenResponse(BaseModel):
    """Token demonstrativo e contexto que o front-end poderá exibir."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)
    context: AuthenticatedContext


class SourceReference(BaseModel):
    """Fonte da política usada para produzir uma resposta rastreável."""

    document_id: str
    title: str
    version: str
    chunk_id: str
    section: str
    score: float = Field(ge=0)


class GenerationOutput(BaseModel):
    """Conteúdo estruturado que qualquer provedor de geração deve produzir."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    cited_source_positions: list[int] = Field(max_length=10)
    confidence: Literal["high", "medium", "low"]

    @model_validator(mode="after")
    def validate_source_positions(self) -> Self:
        """Impede posições inválidas no contexto numerado."""

        if any(position < 1 for position in self.cited_source_positions):
            raise ValueError("As posições das fontes começam em 1")
        return self

    @property
    def evidence_found(self) -> bool:
        """Considera que existe evidência quando ao menos uma fonte foi citada."""

        return bool(self.cited_source_positions)


class GenerationMetadata(BaseModel):
    """Rastro mínimo da geração devolvido junto com cada resposta."""

    provider: str
    model: str
    prompt_version: str
    status: Literal["generated", "degraded", "no_evidence"]
    attempts: int = Field(ge=0)


class ExecutionDocument(BaseModel):
    """Documento recuperado e sua pontuação nesta execução."""

    document_id: str
    version: str
    chunk_id: str
    score: float = Field(ge=0)


class ExecutionTrace(BaseModel):
    """Resumo técnico que ajuda a explicar tempo e fontes da resposta."""

    timings_ms: dict[str, float]
    documents: list[ExecutionDocument]


class AskResponse(BaseModel):
    """Resposta baseada nas fontes recuperadas pelo assistente."""

    answer: str
    sources: list[SourceReference]
    confidence: Literal["high", "medium", "low"]
    request_id: str
    latency_ms: int = Field(ge=0)
    generation: GenerationMetadata
    trace: ExecutionTrace | None = None


class ErrorResponse(BaseModel):
    """Formato estável de erro quando um serviço não está disponível."""

    detail: str


class FeedbackRequest(BaseModel):
    """Avaliação simples ligada a uma resposta já entregue."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(pattern=r"^req_[A-Za-z0-9_-]{3,100}$")
    rating: Literal["positive", "negative"]


class FeedbackResponse(BaseModel):
    """Confirma que o feedback foi recebido pela demonstração."""

    feedback_id: str
    request_id: str
    status: Literal["received"]


class TelemetryRequest(BaseModel):
    """Evento de uso sem pergunta, resposta, credencial ou outro dado sensível."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event: Literal[
        "login_completed",
        "logout_completed",
        "quick_question_selected",
        "question_submitted",
        "answer_displayed",
        "request_id_copied",
        "feedback_positive",
        "feedback_negative",
    ]


class DocumentManifest(BaseModel):
    """Metadados que identificam, versionam e localizam uma política."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(min_length=1, pattern=r"^[a-z0-9_\-]+$")
    document_id: str = Field(min_length=1, pattern=r"^[a-z0-9_\-]+$")
    title: str = Field(min_length=3)
    version: str = Field(pattern=r"^v[1-9][0-9]*$")
    valid_from: date
    valid_until: date | None = None
    file: str = Field(min_length=1, pattern=r"^[^\\/]+\.md$")

    @model_validator(mode="after")
    def validate_validity_period(self) -> Self:
        """Impede que a validade termine antes de começar."""

        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("valid_until não pode ser anterior a valid_from")
        return self


class KnowledgeDocumentEntry(BaseModel):
    """Identifica um documento curto dentro de um catálogo de conhecimento."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: str = Field(min_length=1, pattern=r"^[a-z0-9_\-]+$")
    title: str = Field(min_length=3)
    version: str = Field(pattern=r"^v[1-9][0-9]*$")
    valid_from: date
    valid_until: date | None = None
    file: str = Field(min_length=1, pattern=r"^[^\\/]+\.md$")

    @model_validator(mode="after")
    def validate_validity_period(self) -> Self:
        """Impede um período de validade invertido."""

        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("valid_until não pode ser anterior a valid_from")
        return self


class KnowledgeCatalog(BaseModel):
    """Agrupa documentos curtos pertencentes à mesma empresa fictícia."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(min_length=1, pattern=r"^[a-z0-9_\-]+$")
    documents: list[KnowledgeDocumentEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_entries(self) -> Self:
        """Evita IDs e arquivos repetidos no mesmo catálogo."""

        document_ids = [document.document_id for document in self.documents]
        files = [document.file for document in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("document_id repetido no catálogo")
        if len(files) != len(set(files)):
            raise ValueError("arquivo repetido no catálogo")
        return self
