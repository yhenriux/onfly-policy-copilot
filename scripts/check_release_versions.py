"""Confirma que aplicação, prompt e manifesto identificam o mesmo release."""

import json
from pathlib import Path

from app.core.config import Settings
from app.generation.prompts import PROMPT_VERSION


def main() -> None:
    """Falha quando uma versão foi alterada sem atualizar o manifesto."""

    release = json.loads(Path("release.json").read_text(encoding="utf-8"))
    settings = Settings()
    failures: list[str] = []
    if release["application_version"] != settings.app_version:
        failures.append("A versão da aplicação não corresponde ao release.json")
    if release["prompt_version"] != PROMPT_VERSION:
        failures.append("A versão do prompt não corresponde ao release.json")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"Release {settings.app_version} validado com prompt {PROMPT_VERSION} "
        f"e índice {release['index_schema_version']}."
    )


if __name__ == "__main__":
    main()
