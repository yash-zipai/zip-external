# =============================================================================
# ZipAI External Data API — Production Dockerfile
# Multi-stage build for minimal image size and attack surface.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build — install Python dependencies into a virtual environment
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build-time system dependencies (gcc needed for some C-extension wheels)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual environment for clean separation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (layer caching optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime — lean production image
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# Metadata labels (OCI standard)
LABEL maintainer="ZipAI Engineering <engineering@zipai.com>" \
      org.opencontainers.image.title="ZipAI External Data API" \
      org.opencontainers.image.description="FastAPI microservice serving external data for ZipAI" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/zipai/zip-external"

# Runtime system dependencies (libpq for asyncpg, curl for health checks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy application source
COPY --chown=appuser:appuser . .

# Remove files not needed at runtime
RUN rm -rf .git .github .gitignore .env __pycache__ **/__pycache__ \
           *.md Dockerfile docker-compose*.yml .dockerignore

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8001

# Health check — hits the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Production entry point:
# - 4 Uvicorn workers (tune via UVICORN_WORKERS env var at runtime)
# - Binds 0.0.0.0 so traffic can reach the container
# - Proxy headers enabled for reverse-proxy deployments (ALB, Nginx, etc.)
# - Access log enabled for observability
CMD ["sh", "-c", \
     "uvicorn main:app \
        --host 0.0.0.0 \
        --port 8001 \
        --workers ${UVICORN_WORKERS:-4} \
        --proxy-headers \
        --forwarded-allow-ips='*' \
        --access-log \
        --log-level ${LOG_LEVEL:-info}"]
