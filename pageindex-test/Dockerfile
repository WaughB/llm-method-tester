# Build context MUST be the repository root (the backend imports the root
# package as an editable path dependency):
#   docker build -f pageindex-test/Dockerfile .

# Stage 1: frontend
FROM node:22-alpine AS frontend
WORKDIR /build
COPY pageindex-test/frontend/package.json pageindex-test/frontend/package-lock.json* ./
RUN npm ci || npm install
COPY pageindex-test/frontend/ ./
RUN npm run build

# Stage 2: runtime
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# the root package (path dependency of the backend)
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY corpus ./corpus

# the backend
COPY pageindex-test/backend ./pageindex-test/backend
WORKDIR /app/pageindex-test/backend
RUN uv sync --frozen --no-dev

COPY --from=frontend /build/dist ./frontend/dist
ENV PIT_FRONTEND_DIST=/app/pageindex-test/backend/frontend/dist

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8100/api/meta', timeout=4)"]

CMD ["uv", "run", "--no-sync", "pageindex-test", "serve", "--host", "0.0.0.0", "--port", "8100"]
