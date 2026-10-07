FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    CHANNEL_BRAINS_HOME=/data

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY media ./media
COPY README.md ./
RUN uv sync --locked --no-dev

ENV CHANNEL_BRAINS_DEMO_VIDEO=/app/media/demo-walkthrough-review.mp4

RUN mkdir -p /data

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "channel-brains-mcp", "--transport", "http", "--host", "0.0.0.0"]
