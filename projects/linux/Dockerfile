FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends curl sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project
COPY . .

# Python deps
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install \
        fastapi uvicorn websockets httpx aiohttp pydantic \
        google-genai anthropic openai \
        aiosqlite python-dotenv edge-tts \
        pytest pytest-asyncio

ENV PATH="/app/.venv/bin:$PATH"
ENV TURBO=/app

# Data directory
RUN mkdir -p /app/data

EXPOSE 9742

CMD ["python", "-m", "python_ws.server"]
