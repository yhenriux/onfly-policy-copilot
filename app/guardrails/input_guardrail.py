"""Bloqueio de tentativas conhecidas de substituir as instruções da aplicação."""

import re
import unicodedata

from app.core.exceptions import PromptInjectionError

_INJECTION_PATTERNS = (
    r"ignore (as |todas as |the )?(regras|instrucoes|instructions)",
    r"desconsidere (as )?(regras|instrucoes)",
    r"revele (o |seu |as )?(prompt|instrucoes internas)",
    r"system prompt",
    r"voce agora e",
    r"you are now",
    r"mostre a politica (da|de outra)",
)


def normalize_security_text(text: str) -> str:
    """Remove acentos e diferenças de caixa para comparar padrões."""

    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def ensure_safe_question(question: str) -> None:
    """Interrompe a pergunta quando encontra uma instrução de ataque conhecida."""

    normalized = normalize_security_text(question)
    if any(re.search(pattern, normalized) for pattern in _INJECTION_PATTERNS):
        raise PromptInjectionError(
            "A pergunta contém uma tentativa de alterar as regras do sistema"
        )
