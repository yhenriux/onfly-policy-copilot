"""Leitura de documentos e dos metadados que descrevem cada política."""

import json
from datetime import date
from pathlib import Path

from app.domain.models import LoadedDocument
from app.domain.schemas import DocumentManifest


def load_markdown(
    path: Path,
    *,
    tenant_id: str,
    document_id: str,
    title: str,
    version: str,
    valid_from: date,
    valid_until: date | None,
) -> LoadedDocument:
    """Lê uma política Markdown em UTF-8 e preserva sua identificação."""

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"O documento está vazio: {path}")

    return LoadedDocument(
        tenant_id=tenant_id,
        document_id=document_id,
        title=title,
        version=version,
        valid_from=valid_from,
        valid_until=valid_until,
        source=path.as_posix(),
        text=text,
    )


def load_manifest(manifest_path: Path) -> LoadedDocument:
    """Lê um manifesto JSON e carrega o documento indicado por ele."""

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DocumentManifest.model_validate(raw_manifest)
    document_path = manifest_path.parent / manifest.file
    return load_markdown(
        document_path,
        tenant_id=manifest.tenant_id,
        document_id=manifest.document_id,
        title=manifest.title,
        version=manifest.version,
        valid_from=manifest.valid_from,
        valid_until=manifest.valid_until,
    )
