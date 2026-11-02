# Build stage: resolve dependencies from uv.lock and install the app into /app/.venv.
FROM python:3.13.14-slim AS builder

RUN pip3 install --no-cache-dir uv==0.10.6

# Bytecode is compiled at build time; copy mode because the venv is moved to another stage;
# the base image's Python is used, uv must not download its own.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, in a separate layer: it is rebuilt only when uv.lock changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

# The app itself, installed as a regular (non-editable) package so src/ is not needed at runtime.
COPY src ./src
RUN uv sync --locked --no-dev --no-editable


# Runtime stage: only the venv, no uv, no sources, non-root user.
FROM python:3.13.14-slim

# git: the Agent's Working copies are clones of the test repo (ADR 0005); the Claude Code it
# runs is the binary bundled in the SDK wheel, nothing else to install for it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# /app is owned by the app user so that a local SQLite DATABASE_URL can create its file there.
# /app/var/workspace is PITCREW_WORK_DIR's default, a mounted volume when the Agent runs.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/var/workspace \
    && chown -R app:app /app

COPY --from=builder /app/.venv /app/.venv
# Team configs, read from PITCREW_CONFIG_DIR (default `config`, relative to /app).
COPY config /app/config
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
WORKDIR /app

EXPOSE 8000

# Secrets come from environment variables only; neither .env nor service.env is inside the image.
CMD ["uvicorn", "pitcrew.main:app", "--host", "0.0.0.0", "--port", "8000"]
