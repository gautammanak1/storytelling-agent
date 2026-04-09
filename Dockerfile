FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY agents_shared /app/agents_shared

COPY agents/storytelling-agent/pyproject.toml /app/agents/storytelling-agent/pyproject.toml
COPY agents/storytelling-agent/uv.lock /app/agents/storytelling-agent/uv.lock

WORKDIR /app/agents/storytelling-agent
RUN uv venv --python 3.11 && uv sync --frozen --no-dev

ENV PATH="/app/agents/storytelling-agent/.venv/bin:$PATH"

COPY agents/storytelling-agent/ /app/agents/storytelling-agent/

EXPOSE 8030 8080

WORKDIR /app/agents/storytelling-agent

RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER 10001

CMD ["python", "agent.py"]
