# zip-external — ZipAI External Data API

FastAPI service that serves read-mostly data (healthcare, crime, lifestyle, schools,
cost of living, jobs, MLS market signals, mortgage rates, admin/analytics dashboards)
from a shared PostgreSQL RDS (`zipdata-prod`). It uses one Postgres schema per domain
and raw SQL through async SQLAlchemy and asyncpg. There is no ORM and there are no models.

- **Main consumer:** ZipData (Django BFF, sibling repo `../ZipData`). Clients live in
  `backend/zipdata_proj/zipdata/services/zipai/*_client.py`. The path contract is in
  `backend/zipdata_proj/zipdata/tests/fixtures/zipai/path_table.json`. The Signals page
  calls `zipdata/services/client_signals_market.py`.
- **Sibling:** `../ZipAI` (zipai-rag, :8000). `core/config.py` was copied from it, which is
  why it has Bedrock/RAG/chunking settings that this service never reads.
- **Runtime:** Docker, uvicorn with 4 workers on **:8001**. It deploys through a GH Action on
  push to `main` (SSH to EC2, `git reset --hard origin/main`, `pip install`,
  `systemctl restart fastapi`). The `vector` container ships JSON logs to
  `POST /v1/internal/vector/events`.

## Commands

```bash
.venv/bin/python main.py --reload --port 8001   # local dev (main.py defaults to :8000; ZipData expects :8001)
docker compose up -d --build                     # api + vector
curl localhost:8001/health                       # liveness; Swagger at /docs
.venv/bin/python -c "from main import app; import json; print(json.dumps(sorted(app.openapi()['paths'])))"  # list routes
```

No tests, linter, or type-checker are configured. Importing `main` does not connect to the
DB, because engines are created lazily. The OpenAPI dump above is the fastest way to check
routing. FastAPI ≥0.141 nests included routers as `_IncludedRouter`, so iterate
`app.openapi()`, not `app.routes`.

## Layout and request flow

```
main.py                     create_app(): /health + include_router(<domain>, prefix="/v1") ×14
core/config.py              Settings (pydantic-settings, .env). Only database_url, db_echo, app_env, service_name are used
core/schema_manager.py      get_schema_session("<schema>") → FastAPI dependency; one engine per schema per worker
core/cache.py               every TTLCache instance + @cached decorator
core/pagination.py          pagination_params(default_limit, max_limit) dependency, PaginationMeta.build, Page[T]
core/categories/<domain>/   routes.py → service.py → repository.py, schemas.py (Pydantic v2)
docs/signal-optimization.md Signals perf log (Problem / Solution / Approach-and-why / Verification per fix)
sql/                        reviewed DDL for the DB owner to run (the app never runs DDL)
vector/vector.yml           Vector log shipper config (docker_logs → filter .event_type → HTTP sink)
```

- **routes.py:** `APIRouter`, query validation, `Depends(get_schema_session("x"))`. No SQL here.
- **service.py:** a class with `@staticmethod @cached(<cache>) async def ...(session, ...)`.
  It maps repo dicts to response models.
- **repository.py:** `text("""...""")` with bound params and returns `list[dict]` or `(rows, total)`.
  The only f-string interpolation allowed is a whitelisted token, such as the market
  `_AREA_COLUMNS` or the healthcare `VALID_CATEGORIES`.
- **Sessions:** `pool_size=1, max_overflow=1`, `statement_timeout=30s`, and
  `search_path=<schema>,public`. The comments say "keep LOW", and that is deliberate:
  RDS max_connections=100, 12 schemas × 4 workers already hold about 44 idle connections
  (measured 2026-09-23), and the DB is CPU-bound. Don't raise these without measuring.
- **`@cached`:** the key skips the session (first positional arg or `session=` kwarg), and
  concurrent misses for the same key share one query. The cache is in-memory **per worker**,
  so there are 4 separate cold caches.

## Endpoint index (71 routes)

| Domain (dir) | Final paths (under `/v1`) | Schema session | Tables | Caches (`core/cache.py`) |
|---|---|---|---|---|
| healthcare | `/healthcare/zipcode/{zip}/top-places`, `…/breakdown`, `/healthcare/index-scores`, `/healthcare/places/pins/` | `healthcare` | `healthcare_provider`, `_reviews`, `_images` | `top_places`, `breakdown`, `index_scores`, `map_pins` |
| crime | `/crime/zipcode/{zip}/index-scores`, `…/breakdown`, `…/insights?months` | `crime` | `crime_history`, `v_zip_summary` | `crime_*` |
| lifestyle | `/zipcode/{zip}/top-places/`, `/zipcode/{zip}/location-indices/`, `…/location-indices/lifestyle/breakdown/`, `/map/v1/lifestyle/places/pins/` | `lifestyle` | `lifestyle_place`, `lifestyle_image` | `lifestyle_*` |
| schools | `/api/zipcode/{zip}/schools/`, `/api/zipcode/{zip}/colleges-universities/`, `/api/zipcode/{zip}/location-indices/education/breakdown/`, `/api/place/{canonical_place_id}/details/`, `/api/map/v1/places/pins/` | `schools` | `schools_details` | `schools_*` |
| cost_of_living | `/v1/cost-of-living/zipcode/{zip}/index-scores`, `…/breakdown` (**served at `/v1/v1/…`**) | `cost_of_living` | `col_snapshot`, `col_housing`, `col_income`, `col_monthly_costs`, `col_trend` | `col_*` |
| employer ("Jobs") | `/zipcode/{zip}/breakdown`, `/zipcode/{zip}/index-scores` | `employer` | `zip_snapshots`, `zip_industry_employer_stats` | `jobs_*` |
| signal/market | `/market/{home-price-trend,value-per-sqft,price-drop-pressure,price-cuts,buyer-leverage,price-reductions,fresh-supply,homes-sold,available-inventory,price-distribution,speed-to-sell,dom-breakdown,listings}/`. Scope with exactly one of `county`/`city`/`zip`, plus `ptype` (default SF) and `months` (default 24). Price trend, $/sqft, homes sold, buyer-leverage and price-reductions share one cached closed-sales query (`closed_monthly`). ZipData still requests 7 market charts that don't exist here and get 404s | `signal` | `listing_fact`, `market_event` | `market_*` (trend TTL 1 h) |
| signal/rate | `/rate/current/`, `/rate/history/?months` | `signal` | `mortgage_rate` | `rate_*` |
| seller_agent | `/agent/me`, `/agent/listings/`, `/agent/invites/summary`, `/agent/invites/`, `/agent/clients/`, `/agent/partners/`, `/agent/invited-by` (identity is passed as query params: `agent_key`, `invited_by_id`, `user_id`) | `public` | `zipdata_idxlisting`, `zipdata_temporaryaccount` (Django) | `agent_*` |
| mls (DQ) | `/mls/dq/{status,source-target,status-breakdown,checks}`, `/mls/dq/checks/{check_name}/listings` | `mls` | `admin.dq_check_result`, `admin.dq_action_queue`, `zipdata_idxlisting` | none |
| analytics | **POST** `/internal/vector/events`; `/analytics/{house/{id}/views,usage,overview,trending-zipcodes,activity-heatmap,user-journey-funnel,session-quality,search-to-house-view-rate}` | `analytics` | `analytics.user_events` (INSERT + reads) | `analytics_*` |
| data_audit | `/data-audit/{ingestion-activity,freshness,record-counts,coverage,coverage-gaps,data-quality,new-listings,new-listings/summary}` | `analytics` (all queries schema-qualified) | cross-schema: every domain table, `crime.stg_crime_raw`, `public.zipdata_idxlisting` | `audit_*` |
| audit | **POST** `/audit/conversation-logs` | `ai` | `ai.usp_AiConversationLog(...)` → `ai."AiConversationLogs"` | none |
| ai_admin | `/ai-admin/{overview,top-questions,intent-distribution,questions-over-time,top-unanswered}` | `rag` | `rag.query_analytics` | `ai_*` |

Only two endpoints write, and both commit inside the repository: `POST /audit/conversation-logs`
and `POST /internal/vector/events`. Every other endpoint is a GET.

## Upstream loaders (outside this repo)

This service never loads domain data. Tables are filled by jobs that live elsewhere:

- **`signal.mortgage_rate`** (unique on `rate_date`; columns `rate_30yr`, `rate_15yr`
  in percent, `source`, `loaded_at`): an AWS Lambda downloads Freddie Mac's PMMS
  `historicalweeklydata.xlsx` (no API key) and upserts it with pg8000. `{}` refreshes the
  last 12 weeks, and `{"full": true}` backfills from 1971. It is meant to run on EventBridge
  `cron(0 17 ? * FRI *)`. Its source code is only in AWS, not in any repo. `loaded_at` is
  set on insert only, so it shows when each week first arrived, not the last run.
  The code comments here that say "loaded from FRED" are out of date.
- **`signal.listing_fact` / `signal.market_event`**: an external MLS loader. Its last run
  is recorded in `signal.load_state`.

## Gotchas

- **Odd paths are live contracts.** `/v1/v1/cost-of-living/...`, `/v1/api/...`,
  `/v1/map/v1/lifestyle/...` and the prefix-less jobs routes are what ZipData calls
  (see `path_table.json`). Never rename or "fix" a path, or change a response shape,
  without updating ZipData. Some route docstrings are stale: cost_of_living lists
  "legacy" routes that don't exist, and lifestyle suggests a `/api` prefix.
- **Production DB is read-only for dev work.** Don't run INSERT/UPDATE/DELETE, DDL,
  VACUUM or ANALYZE against `zipdata-prod` without asking. Deliver DB changes as a dated
  `sql/YYYY-MM-DD_*.sql` for the owner. Read-only SELECT and EXPLAIN are fine.
- **Signals performance work** happens on branch `feat-optimize`. Log each fix in
  `docs/signal-optimization.md` using the same four-part format. The city indexes in
  `sql/2026-09-23_signal_city_indexes.sql` are pending the DBA.
- **Market `only_public`** is passed through but never applied in SQL. ZipData gates the
  rows instead.
- **No auth anywhere.** This includes the internal Vector endpoint and the seller-agent
  routes (see the `TODO (auth)` in `seller_agent/routes.py`).
- **Adding a domain:** create `core/categories/<name>/{routes,service,repository,schemas}.py`,
  add its caches to `core/cache.py`, and `include_router(..., prefix="/v1")` in `main.py`.
  `schema_manager` needs no change, but each new schema adds up to 2 connections per worker.
- **Repo hygiene:** `.env` (with real DB credentials), `venv/` (a Windows venv) and
  `__pycache__/` are tracked despite `.gitignore`. Use `.venv/` locally.
