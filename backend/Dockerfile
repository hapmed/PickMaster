FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /app/.venv /opt/venv
COPY app ./app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project || true
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
