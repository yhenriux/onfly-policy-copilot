"""Testes da leitura de disponibilidade das dependências locais."""

from pathlib import Path

from app.observability.health import LocalReadinessChecker


def test_local_qdrant_lock_is_ready_when_expected_collection_is_persisted(
    tmp_path: Path,
) -> None:
    """Evita falso alerta quando a própria API mantém o Qdrant local aberto."""

    collection = "politicas"
    qdrant_path = tmp_path / "qdrant"
    (qdrant_path / "collection" / collection).mkdir(parents=True)
    (qdrant_path / "meta.json").write_text("{}", encoding="utf-8")
    checker = LocalReadinessChecker(
        ollama_base_url="http://localhost:11434",
        qdrant_path=qdrant_path,
        collection=collection,
    )

    assert checker._local_collection_is_persisted() is True
