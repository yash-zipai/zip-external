# ZipAI External Data API

A high-performance, asynchronous **FastAPI** microservice that serves external data across multiple domain categories — healthcare, crime, lifestyle, schools, cost of living, and employer/jobs — for the ZipAI platform.

Built on **async SQLAlchemy + asyncpg** with per-schema connection pooling against a shared PostgreSQL (AWS RDS) database.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start — Docker (Recommended)](#quick-start--docker-recommended)
- [Local Development (Without Docker)](#local-development-without-docker)
- [Configuration Reference](#configuration-reference)
- [API Endpoints](#api-endpoints)
- [Docker Commands Reference](#docker-commands-reference)
- [Production Deployment](#production-deployment)
- [CI/CD](#cicd)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Clients                               │
│              (Mobile App / Web Dashboard / SDK)               │
└──────────────────────┬───────────────────────────────────────┘
                       │  HTTPS
                       ▼
              ┌────────────────┐
              │  ALB / Nginx   │
              │  (Reverse Proxy)│
              └────────┬───────┘
                       │  :8000
                       ▼
        ┌──────────────────────────────┐
        │   ZipAI External Data API    │
        │   (FastAPI + Uvicorn)        │
        │                              │
        │  ┌─────────┐ ┌───────────┐  │
        │  │ /v1/     │ │ Schema    │  │
        │  │ health   │ │ Manager   │──┼──▶  PostgreSQL (AWS RDS)
        │  │ care     │ │ (per-     │  │     └─ healthcare schema
        │  │ crime    │ │  schema   │  │     └─ crime schema
        │  │ lifestyle│ │  conn     │  │     └─ lifestyle schema
        │  │ schools  │ │  pool)    │  │     └─ schools schema
        │  │ cost_of  │ │           │  │     └─ cost_of_living schema
        │  │ _living  │ └───────────┘  │     └─ employer schema
        │  │ employer │                │
        │  │ audit    │ ┌───────────┐  │
        │  └─────────┘ │ TTL Cache │  │
        │              │ (in-memory)│  │
        │              └───────────┘  │
        └──────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  AWS Bedrock   │
              │  (Embeddings   │
              │   & LLM)       │
              └────────────────┘
```

---

## Tech Stack

| Layer         | Technology                                                  |
|---------------|-------------------------------------------------------------|
| Framework     | [FastAPI](https://fastapi.tiangolo.com/) ≥ 0.110           |
| Server        | [Uvicorn](https://www.uvicorn.org/) (ASGI, multi-worker)   |
| ORM           | [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) (async)     |
| DB Driver     | [asyncpg](https://magicstack.github.io/asyncpg/)           |
| Validation    | [Pydantic v2](https://docs.pydantic.dev/)                  |
| Caching       | [cachetools](https://cachetools.readthedocs.io/) TTL Cache  |
| AI / ML       | AWS Bedrock (Titan Embeddings, Claude LLM)                  |
| Containerisation | Docker + Docker Compose                                  |
| Database      | PostgreSQL 15+ (AWS RDS)                                   |

---

## Prerequisites

| Requirement         | Version     | Purpose                       |
|---------------------|-------------|-------------------------------|
| Docker              | ≥ 24.0      | Container runtime             |
| Docker Compose      | ≥ 2.20      | Service orchestration         |
| Python (optional)   | ≥ 3.13      | Local dev without Docker      |
| AWS Credentials     | —           | Bedrock model access          |
| PostgreSQL (RDS)    | ≥ 15        | External database             |

> **Note:** The API connects to an **external** PostgreSQL database (AWS RDS). No local database container is required.

---

## Quick Start — Docker (Recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/zip-external.git
cd zip-external
```

### 2. Configure Environment

```bash
# Create your .env from the template
cp .env.example .env

# Edit with your actual credentials
# ⚠️  At minimum, set DATABASE_URL and AWS credentials
nano .env   # or vim, code, etc.
```

> **⚠️ IMPORTANT:** Never commit the `.env` file. It is already in `.gitignore`.

### 3. Build & Start

```bash
# Build the image and start in detached mode
docker compose up -d --build
```

### 4. Verify

```bash
# Check the container is healthy
docker compose ps

# Hit the health endpoint
curl http://localhost:8001/health
# Expected: {"status":"ok","service":"zipai-rag","env":"production"}

# View live logs
docker compose logs -f api
```

### 5. Stop

```bash
# Stop the service (preserves the image)
docker compose down
```

---

## Local Development (Without Docker)

For rapid iteration with auto-reload:

### 1. Create Virtual Environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your DATABASE_URL and other settings
# Set APP_ENV=development for debug mode
```

### 4. Run the Development Server

```bash
# Option A: via main.py with auto-reload
python main.py --reload

# Option B: via Uvicorn directly
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### 5. Access the API

| URL                                    | Description               |
|----------------------------------------|---------------------------|
| `http://localhost:8001/health`         | Health check              |
| `http://localhost:8001/docs`           | Swagger UI (interactive)  |
| `http://localhost:8001/redoc`          | ReDoc (read-only docs)    |

---

## Configuration Reference

All configuration is loaded from environment variables (or `.env` file). See [`.env.example`](.env.example) for the full template.

### Core Settings

| Variable             | Default        | Description                                   |
|----------------------|----------------|-----------------------------------------------|
| `APP_ENV`            | `development`  | Runtime environment (`development` / `staging` / `production`) |
| `LOG_LEVEL`          | `debug`        | Logging level (`debug` / `info` / `warning` / `error`)        |
| `SERVICE_NAME`       | `zipai-rag`    | Service identifier for logs                   |

### Database

| Variable             | Required | Description                                   |
|----------------------|----------|-----------------------------------------------|
| `DATABASE_URL`       | ✅       | Async PostgreSQL DSN (`postgresql+asyncpg://...`) |
| `DB_SCHEMA`          | No       | PostgreSQL schema (default: `healthcare`)     |
| `DB_ECHO`            | No       | Enable SQL logging (default: `false`)         |

### AWS & Bedrock

| Variable                    | Default                              | Description                    |
|-----------------------------|--------------------------------------|--------------------------------|
| `AWS_REGION`                | `us-east-1`                          | AWS region                     |
| `AWS_ACCESS_KEY_ID`         | —                                    | IAM access key                 |
| `AWS_SECRET_ACCESS_KEY`     | —                                    | IAM secret key                 |
| `BEDROCK_EMBED_MODEL_ID`    | `amazon.titan-embed-text-v2:0`       | Embedding model                |
| `BEDROCK_LLM_MODEL_ID`     | `anthropic.claude-3-5-sonnet-...`    | LLM model                     |
| `BEDROCK_MAX_CONCURRENCY`   | `10`                                 | Max concurrent Bedrock calls   |

### Docker Runtime

| Variable           | Default | Description                              |
|--------------------|---------|------------------------------------------|
| `API_PORT`         | `8001`  | Host port mapped to the container        |
| `UVICORN_WORKERS`  | `4`     | Number of Uvicorn worker processes       |

---

## API Endpoints

All domain endpoints are prefixed with `/v1`.

| Method | Path                          | Domain          | Description               |
|--------|-------------------------------|-----------------|---------------------------|
| `GET`  | `/health`                     | Meta            | Liveness probe            |
| `GET`  | `/v1/healthcare/...`          | Healthcare      | Healthcare data endpoints |
| `GET`  | `/v1/crime/...`               | Crime           | Crime statistics          |
| `GET`  | `/v1/lifestyle/...`           | Lifestyle       | Lifestyle metrics         |
| `GET`  | `/v1/schools/...`             | Schools         | School & education data   |
| `GET`  | `/v1/cost-of-living/...`      | Cost of Living  | Cost of living indices    |
| `GET`  | `/v1/employer/...`            | Employer/Jobs   | Employment data           |
| `GET`  | `/v1/audit/...`               | Audit           | Audit log endpoints       |

> **Full interactive docs** available at `/docs` (Swagger UI) when the server is running.

---

## Docker Commands Reference

### Build & Run

```bash
# Build the image (no cache)
docker compose build --no-cache

# Start in foreground (Ctrl+C to stop)
docker compose up

# Start in background
docker compose up -d

# Rebuild and start
docker compose up -d --build
```

### Monitoring

```bash
# Container status & health
docker compose ps

# Stream logs
docker compose logs -f api

# Last 100 log lines
docker compose logs --tail=100 api

# Resource usage
docker stats zipai-external-api
```

### Maintenance

```bash
# Stop containers
docker compose down

# Stop and remove volumes
docker compose down -v

# Restart the service
docker compose restart api

# Execute a shell in the running container
docker compose exec api sh

# Run a one-off command
docker compose run --rm api python -c "from core.config import get_settings; print(get_settings().model_dump())"
```

### Image Management

```bash
# List images
docker images | grep zipai

# Remove dangling images
docker image prune -f

# Full cleanup (⚠️ removes all unused resources)
docker system prune -af
```

---

## Production Deployment

### Security Hardening (Built-In)

The Docker setup includes these production-grade security measures:

- ✅ **Multi-stage build** — build tools are excluded from the runtime image
- ✅ **Non-root user** — container runs as `appuser` (UID 1001)
- ✅ **Read-only filesystem** — `read_only: true` with `/tmp` tmpfs for ephemeral writes
- ✅ **No privilege escalation** — `no-new-privileges:true`
- ✅ **Resource limits** — CPU and memory caps prevent runaway consumption
- ✅ **Log rotation** — `json-file` driver with 10 MB / 5 files rotation
- ✅ **Health checks** — built into both the Dockerfile and Compose file
- ✅ **Secrets via env_file** — credentials never baked into the image

### Scaling Workers

Adjust `UVICORN_WORKERS` based on available CPU cores:

```bash
# Rule of thumb: 2 × CPU cores + 1
UVICORN_WORKERS=9  # for a 4-core machine
```

### Behind a Reverse Proxy (Nginx / ALB)

The Uvicorn configuration includes `--proxy-headers` and `--forwarded-allow-ips='*'` to correctly read `X-Forwarded-For` and `X-Forwarded-Proto` headers from upstream load balancers.

---

## CI/CD

The project includes a GitHub Actions workflow at [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) that:

1. Triggers on pushes to `main`
2. SSHs into the EC2 instance
3. Pulls the latest code
4. Installs dependencies
5. Restarts the FastAPI service

**Required GitHub Secrets:**

| Secret          | Description                     |
|-----------------|---------------------------------|
| `EC2_HOST`      | EC2 public IP or hostname       |
| `EC2_USERNAME`  | SSH username (e.g. `ec2-user`)  |
| `EC2_SSH_KEY`   | Private SSH key for the EC2     |

---

## Project Structure

```
zip-external/
├── .dockerignore             # Files excluded from Docker build context
├── .env.example              # Environment variable template
├── .github/
│   └── workflows/
│       └── deploy.yml        # GitHub Actions CD pipeline
├── .gitignore
├── Dockerfile                # Multi-stage production build
├── docker-compose.yml        # Service orchestration
├── main.py                   # FastAPI application entry point
├── requirements.txt          # Python dependencies
├── README.md                 # ← You are here
└── core/
    ├── __init__.py
    ├── cache.py              # In-memory TTL cache utilities
    ├── config.py             # Pydantic Settings (env validation)
    ├── pagination.py         # Reusable pagination helpers
    ├── schema_manager.py     # Per-schema async engine registry
    └── categories/
        ├── __init__.py
        ├── audit/            # Audit logging endpoints
        ├── cost_of_living/   # Cost of living data
        ├── crime/            # Crime statistics
        ├── employer/         # Employment / jobs data
        ├── healthcare/       # Healthcare provider data
        ├── lifestyle/        # Lifestyle metrics
        └── schools/          # School & education data
```

Each category module follows the same layered pattern:

```
category/
├── routes.py       # FastAPI router (HTTP layer)
├── service.py      # Business logic
├── repository.py   # Database queries (SQLAlchemy)
└── schemas.py      # Pydantic request/response models
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs for startup errors
docker compose logs api

# Validate your .env file is present and has required vars
docker compose config
```

### Database connection refused

- Ensure `DATABASE_URL` in `.env` is correct and reachable from the container
- If running on a corporate network, verify the RDS security group allows inbound from your IP
- Test connectivity:
  ```bash
  docker compose exec api python -c "
  from core.config import get_settings
  print(get_settings().database_url[:50] + '...')
  "
  ```

### Health check failing

```bash
# Manual health check from inside the container
docker compose exec api curl -v http://localhost:8001/health
```

### Port already in use

```bash
# Change the host port via API_PORT
API_PORT=8002 docker compose up -d
```

---

## License

Proprietary — ZipAI. All rights reserved.
