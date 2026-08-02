"""Divisão de documentos em trechos que preservam as seções originais."""

from dataclasses import dataclass
from hashlib import sha256

from app.domain.models import DocumentChunk, NormalizedDocument


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Limites usados para dividir seções longas com sobreposição."""

    max_chars: int = 800
    overlap_chars: int = 120

    def __post_init__(self) -> None:
        if self.max_chars < 1:
            raise ValueError("max_chars deve ser maior que zero")
        if self.overlap_chars < 0:
            raise ValueError("overlap_chars não pode ser negativo")
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars deve ser menor que max_chars")


def _split_with_overlap(text: str, config: ChunkingConfig) -> list[str]:
    """Divide texto longo e repete o final anterior para manter contexto."""

    if len(text) <= config.max_chars:
        return [text]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + config.max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + config.max_chars // 2, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(text):
            break
        start = max(end - config.overlap_chars, start + 1)
    return parts


def chunk_by_section(
    document: NormalizedDocument,
    config: ChunkingConfig | None = None,
) -> list[DocumentChunk]:
    """Divide por seção e aplica sobreposição quando o texto é longo."""

    runtime_config = config or ChunkingConfig()
    sections: list[tuple[str, list[str]]] = []
    current_title = "Introdução"
    current_lines: list[str] = []

    for line in document.text.splitlines():
        if line.startswith("## "):
            if any(item.strip() for item in current_lines):
                sections.append((current_title, current_lines))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(line)

    if any(item.strip() for item in current_lines):
        sections.append((current_title, current_lines))

    chunks: list[DocumentChunk] = []
    position = 0
    for section, lines in sections:
        section_text = "\n".join(lines).strip()
        for text in _split_with_overlap(section_text, runtime_config):
            position += 1
            chunk_hash = sha256(f"{section}:{text}".encode()).hexdigest()
            chunks.append(
                DocumentChunk(
                    tenant_id=document.tenant_id,
                    document_id=document.document_id,
                    title=document.title,
                    version=document.version,
                    valid_from=document.valid_from,
                    valid_until=document.valid_until,
                    source=document.source,
                    chunk_id=f"chunk_{position:03d}_{chunk_hash[:16]}",
                    position=position,
                    section=section,
                    text=text,
                    document_hash=document.document_hash,
                    chunk_hash=chunk_hash,
                )
            )

    if not chunks:
        raise ValueError(f"O documento não possui conteúdo indexável: {document.source}")
    return chunks
