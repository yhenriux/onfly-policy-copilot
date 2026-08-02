"""Divisão de documentos em trechos que preservam o sentido do texto."""

import re
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


def _natural_units(text: str) -> list[str]:
    """Separa parágrafos e, quando necessário, frases completas."""

    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        units.extend(
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", paragraph)
            if sentence.strip()
        )
    return units


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Corta apenas uma frase excepcionalmente longa, preferindo espaços."""

    parts: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        boundary = remaining.rfind(" ", max_chars // 2, max_chars + 1)
        boundary = boundary if boundary > 0 else max_chars
        parts.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def _split_with_overlap(text: str, config: ChunkingConfig) -> list[str]:
    """Agrupa frases completas e reaproveita contexto do trecho anterior."""

    if len(text) <= config.max_chars:
        return [text]

    units = [
        piece for unit in _natural_units(text) for piece in _hard_split(unit, config.max_chars)
    ]
    chunks: list[str] = []
    current: list[str] = []
    for unit in units:
        candidate = " ".join([*current, unit])
        if current and len(candidate) > config.max_chars:
            chunks.append(" ".join(current))
            overlap: list[str] = []
            overlap_size = 0
            for previous in reversed(current):
                added = len(previous) + (1 if overlap else 0)
                if overlap_size + added > config.overlap_chars:
                    break
                overlap.insert(0, previous)
                overlap_size += added
            current = overlap
        current.append(unit)
    if current:
        final_chunk = " ".join(current)
        if not chunks or final_chunk != chunks[-1]:
            chunks.append(final_chunk)
    return chunks


def chunk_by_section(
    document: NormalizedDocument,
    config: ChunkingConfig | None = None,
) -> list[DocumentChunk]:
    """Divide por seção e aplica sobreposição quando o texto é longo."""

    runtime_config = config or ChunkingConfig()
    sections: list[tuple[str, list[str]]] = []
    heading_path: list[str] = []
    current_title = "Visão geral"
    current_lines: list[str] = []

    for line in document.text.splitlines():
        heading = re.match(r"^(#{2,4})\s+(.+)$", line)
        if heading:
            if any(item.strip() for item in current_lines):
                sections.append((current_title, current_lines))
            level = len(heading.group(1)) - 2
            heading_path = heading_path[:level]
            heading_path.append(heading.group(2).strip())
            current_title = " > ".join(heading_path)
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
