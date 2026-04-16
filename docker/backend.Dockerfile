# Multi-stage Dockerfile for FastAPI backend (ARM64 compatible)

# --- Stage 1: Dependencies ---
FROM python:3.11-slim AS deps

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim AS runtime

ARG INSTALL_CRAWLER=false
ARG INSTALL_CLI_ADVISOR=false

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ /app/backend/
COPY modules/ /app/modules/

# Optional: Install Playwright for SEO crawler
RUN if [ "$INSTALL_CRAWLER" = "true" ]; then \
        apt-get update && \
        pip install --no-cache-dir playwright && \
        playwright install --with-deps chromium && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# Optional: Install Node.js + Claude CLI for SEO advisor (CLI provider)
# No claude-agent-sdk — the adapter calls the CLI via subprocess directly,
# avoiding the starlette version conflict between mcp and FastAPI.
RUN if [ "$INSTALL_CLI_ADVISOR" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends curl ca-certificates && \
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
        apt-get install -y --no-install-recommends nodejs && \
        npm install -g @anthropic-ai/claude-code && \
        apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# Create uploads directory and non-root user
RUN mkdir -p /app/uploads/images && \
    useradd --create-home appuser && \
    chown -R appuser:appuser /app/uploads
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
