"""Limpeza e padronização do texto extraído."""

import re
import unicodedata
from hashlib import sha256

from app.domain.models import LoadedDocument, NormalizedDocument


def normalize_text(text: str) -> str:
    """Padroniza caracteres, espaços e linhas sem alterar o conteúdo."""

    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise ValueError("O texto normalizado ficou vazio")
    return normalized


def normalize_document(document: LoadedDocument) -> NormalizedDocument:
    """Limpa o texto e calcula uma assinatura para detectar mudanças."""

    text = normalize_text(document.text)
    document_hash = sha256(text.encode("utf-8")).hexdigest()
    return NormalizedDocument(
        tenant_id=document.tenant_id,
        document_id=document.document_id,
        title=document.title,
        version=document.version,
        valid_from=document.valid_from,
        valid_until=document.valid_until,
        source=document.source,
        text=text,
        document_hash=document_hash,
    )
