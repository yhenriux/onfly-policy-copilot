"""Testes da leitura e divisão básica de documentos Markdown."""

from datetime import date
from pathlib import Path

import pytest

from app.ingestion.chunker import ChunkingConfig, chunk_by_section
from app.ingestion.loaders import load_markdown
from app.ingestion.normalizer import normalize_document


def test_load_and_chunk_markdown_by_section(tmp_path: Path) -> None:
    policy = tmp_path / "policy.md"
    policy.write_text(
        "# Política\n\n## Alimentação\nLimite de R$ 120.\n\n## Reembolso\nPrazo de 10 dias.",
        encoding="utf-8",
    )
    loaded = load_markdown(
        policy,
        tenant_id="aurora_tecnologia",
        document_id="policy_v1",
        title="Política Aurora",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
    )

    document = normalize_document(loaded)
    chunks = chunk_by_section(document)

    assert [chunk.section for chunk in chunks] == ["Alimentação", "Reembolso"]
    assert all(chunk.tenant_id == "aurora_tecnologia" for chunk in chunks)
    assert all(chunk.chunk_id.startswith("chunk_") for chunk in chunks)
    assert all(chunk.document_hash == document.document_hash for chunk in chunks)
    assert all(chunk.chunk_hash for chunk in chunks)


def test_chunking_applies_configurable_overlap(tmp_path: Path) -> None:
    policy = tmp_path / "long.md"
    policy.write_text("# Política\n\n## Seção\n" + "palavra " * 80, encoding="utf-8")
    loaded = load_markdown(
        policy,
        tenant_id="aurora_tecnologia",
        document_id="long_v1",
        title="Política longa",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
    )

    chunks = chunk_by_section(
        normalize_document(loaded),
        ChunkingConfig(max_chars=120, overlap_chars=20),
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 120 for chunk in chunks)
    assert [chunk.position for chunk in chunks] == list(range(1, len(chunks) + 1))


def test_loader_rejects_empty_document(tmp_path: Path) -> None:
    policy = tmp_path / "empty.md"
    policy.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="documento está vazio"):
        load_markdown(
            policy,
            tenant_id="aurora_tecnologia",
            document_id="empty_v1",
            title="Empty",
            version="v1",
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 12, 31),
        )
