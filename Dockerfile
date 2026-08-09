# A versão do uv fica fixa para tornar a instalação repetível.
FROM ghcr.io/astral-sh/uv:0.8.15 AS uv_source
FROM python:3.12.11-slim-bookworm AS runtime

ARG APP_VERSION=1.0.0
ARG PROMPT_VERSION=policy_answer_v2

LABEL org.opencontainers.image.title="Onfly Policy Copilot" \
      org.opencontainers.image.version="${APP_VERSION}" \
      com.onfly.prompt.version="${PROMPT_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY --from=uv_source /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY data ./data
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
