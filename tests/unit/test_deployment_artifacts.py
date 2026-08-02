"""Testes simples que protegem os contratos dos artefatos de deploy."""

from pathlib import Path


def test_compose_connects_api_qdrant_and_host_ollama() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "QDRANT_MODE: server" in compose
    assert "QDRANT_URL: http://qdrant:6333" in compose
    assert "OLLAMA_BASE_URL: http://host.docker.internal:11434" in compose
    assert "qdrant_data:/qdrant/storage" in compose


def test_dockerfile_uses_locked_dependencies_and_release_labels() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "uv sync --frozen --no-dev" in dockerfile
    assert 'org.opencontainers.image.version="${APP_VERSION}"' in dockerfile
    assert 'com.onfly.prompt.version="${PROMPT_VERSION}"' in dockerfile


def test_ci_contains_all_required_gates() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    for command in (
        "ruff format --check",
        "ruff check",
        "mypy",
        "pytest",
        "pytest tests/security",
        "scripts.check_regression",
        "docker build",
    ):
        assert command in workflow
