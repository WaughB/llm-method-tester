# Stage 1: build the dashboard
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: runtime — Python 3.12 + uv, serving API + built dashboard
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    LLM_BENCH_CACHE_DIR=/data

# dependency layer first so code edits don't bust the cache
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY corpus ./corpus
RUN uv sync --frozen --no-dev

COPY --from=frontend /build/dist ./frontend/dist

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/meta', timeout=3)"]

CMD ["uv", "run", "--no-sync", "llm-bench", "serve", "--host", "0.0.0.0", "--port", "8000"]
