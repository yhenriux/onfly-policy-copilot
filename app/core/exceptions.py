"""Erros conhecidos que a aplicação consegue tratar."""


class OllamaUnavailableError(RuntimeError):
    """Indica que o Ollama local não conseguiu concluir uma chamada."""

    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


class RetrievalUnavailableError(RuntimeError):
    """Indica que o armazenamento vetorial não conseguiu fazer a busca."""


class DocumentVersionConflictError(ValueError):
    """Indica que a mesma versão recebeu dois conteúdos diferentes."""


class InvalidGenerationOutputError(ValueError):
    """Indica que a geração citou dados fora das evidências autorizadas."""


class AuthenticationError(ValueError):
    """Indica credenciais ou token demonstrativo inválidos."""


class TenantIsolationError(RuntimeError):
    """Indica que uma busca tentou atravessar a fronteira entre empresas."""


class PromptInjectionError(ValueError):
    """Indica uma tentativa conhecida de substituir instruções do sistema."""
