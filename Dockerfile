# Build: install dependencies with uv and bake the embedding model into the image,
# so containers start without downloading anything.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
ENV FASTEMBED_CACHE_PATH=/app/models
RUN .venv/bin/python -c "from reqagent.llm import LocalEmbeddings; LocalEmbeddings().embed_query('warm up')"

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --from=build --chown=app:app /app/models /app/models
ENV PATH=/app/.venv/bin:$PATH \
    FASTEMBED_CACHE_PATH=/app/models \
    HF_HUB_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False \
    PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "reqagent.api:app", "--host", "0.0.0.0", "--port", "8000"]
