-- =============================================================================
-- Signal (Market) page — city-scope indexes
-- Target : zipdata-prod  ·  schema signal  ·  PostgreSQL 15
-- Author : zip-external (feat-optimize) · 2026-09-23
-- Status : PROPOSED — to be run by the DB / data-pipeline owner, not the app.
-- =============================================================================
--
-- WHY
--   ZipData scopes Signals charts by city first (city wins over zip), but
--   signal.listing_fact and signal.market_event have no index leading on city
--   (and market_event has none on zip_code either). Every city-scoped chart is
--   a parallel seq scan of ~477k / ~490k rows that discards 99.7% of them.
--
--   Measured 2026-09-23 (EXPLAIN ANALYZE, warm buffers, Menlo Park / 94025):
--     city scope : 70–570 ms per chart query (Seq Scan, ~10.5k buffers)
--     zip  scope : 4–25 ms  per chart query (existing ix_lf_closed / ix_lf_list)
--   Under the page's concurrent burst the DB saturates at ~4 concurrent
--   queries (8-way: median 471 ms, p90 950 ms), so cutting per-query work is
--   what unblocks the page.
--
--   The listing_fact indexes mirror the existing zip ones:
--     ix_lf_closed (zip_code, property_type, close_date) WHERE Closed
--     ix_lf_list   (zip_code, property_type, list_date)
--   market_event mirrors ix_me_scope (county, property_type, month, kind),
--   with kind before month because every query filters on kind by equality.
--
-- QUERIES SERVED (core/categories/signal/market/repository.py)
--   ix_lf_city_closed : home-price-trend, value-per-sqft, homes-sold,
--                       speed-to-sell, dom-breakdown, listings(status=sold)
--   ix_lf_city_list   : fresh-supply, available-inventory, price-distribution,
--                       listings(status=active|pending|new)
--   ix_me_city_scope  : price-drop-pressure, price-cuts            (city scope)
--   ix_me_zip_scope   : price-drop-pressure, price-cuts            (zip scope)
--
-- SAFETY
--   * CREATE INDEX CONCURRENTLY does not block the loader's INSERT/UPDATE.
--     It cannot run inside a transaction block → run with psql autocommit
--     (the default), one statement at a time. Do NOT wrap in BEGIN/COMMIT.
--   * The loader upserts incrementally and occasionally reloads via
--     TRUNCATE + INSERT (pg_stat counters: listing_fact ins=992k/live=477k,
--     market_event ins=1.8M/live=490k, never dropped). TRUNCATE keeps
--     indexes, so these persist across loads. Expect slightly slower full
--     reloads of market_event (2 more indexes to maintain).
--   * Estimated size: ~10–25 MB each. Build time: seconds to ~1 min each.
--   * If a CONCURRENTLY build fails it leaves an INVALID index behind —
--     check with the verification query below, DROP it, and re-run.
--
-- HOW TO RUN
--   psql "$PROD_DSN" -v ON_ERROR_STOP=1 -f sql/2026-09-23_signal_city_indexes.sql
-- =============================================================================

SET statement_timeout = 0;          -- index builds must not hit the app's 30s cap
SET lock_timeout = '10s';           -- never queue behind a long lock on a busy table

-- ── signal.listing_fact ──────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lf_city_closed
    ON signal.listing_fact (city, property_type, close_date)
    WHERE standard_status = 'Closed';

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lf_city_list
    ON signal.listing_fact (city, property_type, list_date);

-- ── signal.market_event ──────────────────────────────────────────────────────
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_me_city_scope
    ON signal.market_event (city, property_type, kind, month);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_me_zip_scope
    ON signal.market_event (zip_code, property_type, kind, month);

-- Refresh planner statistics (last autoanalyze was 2026-08-19).
ANALYZE signal.listing_fact;
ANALYZE signal.market_event;


-- =============================================================================
-- VERIFY (read-only) — run after the above
-- =============================================================================
-- 1) All four indexes exist and are VALID:
--   SELECT c.relname, i.indisvalid, pg_size_pretty(pg_relation_size(c.oid))
--   FROM   pg_index i JOIN pg_class c ON c.oid = i.indexrelid
--   WHERE  c.relname IN ('ix_lf_city_closed','ix_lf_city_list',
--                        'ix_me_city_scope','ix_me_zip_scope');
--
-- 2) City charts now use them (expect Index/Bitmap scan, not Seq Scan):
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT date_trunc('month', close_date)::date, count(*)
--   FROM   signal.listing_fact
--   WHERE  standard_status = 'Closed' AND property_type = 'SF' AND city = 'Menlo Park'
--   GROUP  BY 1;
--
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT month, count(*) FROM signal.market_event
--   WHERE  city = 'Menlo Park' AND property_type = 'SF' GROUP BY month;


-- =============================================================================
-- ROLLBACK — only if needed
-- =============================================================================
--   DROP INDEX CONCURRENTLY IF EXISTS signal.ix_lf_city_closed;
--   DROP INDEX CONCURRENTLY IF EXISTS signal.ix_lf_city_list;
--   DROP INDEX CONCURRENTLY IF EXISTS signal.ix_me_city_scope;
--   DROP INDEX CONCURRENTLY IF EXISTS signal.ix_me_zip_scope;
