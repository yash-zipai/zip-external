# Signals page — performance optimization log

Branch: `feat-optimize` · Started: 2026-09-23 · Scope: `core/categories/signal/**`, `core/cache.py`, `signal` schema

The client reported that the **Signals page loads very slowly** (usually tested with
Portola Valley and Menlo Park). This document records every change made to fix it.
For each change it gives the problem, the fix, the approach chosen, and why that
approach was picked over the alternatives.

Ground rule: **no writes to the production database** (`zipdata-prod`) from this work.
Any DB change is delivered as a reviewed `.sql` file under `sql/`, and the DB owner runs it.

---

## 0. Baseline — how the page loads and where the time goes

### Who calls us
The Signals page is built by **ZipData** (Django BFF). The main caller is
`zipdata/services/client_signals_market.py::_fetch_feed_payloads`:

- **20 GETs per watched area**: 18 market charts plus `rate/history` and `rate/current`,
  8 at a time. The "Today's Numbers" rail sends 3 more at the same moment.
- **Up to 4 areas in parallel** (`MAX_MARKET_AREAS = 4`). That is up to about 90 requests,
  about 32 of them in flight at once.
- The feed and rail use a **5 s read timeout**. On timeout the card falls back to local
  data or renders empty, so the client sees "slow" and "blank" cards together.
- **City scope wins over zip.** ZipData always sends `city=` when it knows the city.
- The feed only displays the **trailing 13 months** of each chart (`MONTHLY_CHART_POINTS = 13`).

### Measurements (2026-09-23, read-only)

**Database side.** Each chart query run on its own with `EXPLAIN (ANALYZE, BUFFERS)`, warm buffers:

| Scope | Typical chart query | Plan |
|---|---|---|
| `city=Menlo Park` | 70–570 ms | Parallel **Seq Scan** of `listing_fact` (477k rows) or `market_event` (490k), discarding 99.7% of rows |
| `zip=94025` | 4–25 ms | Index scan (`ix_lf_closed`, `ix_lf_list`) |
| `available-inventory`, any scope | ~300 ms | CPU-bound: every month since 2020 × every listing in the area |
| `rate/current`, `rate/history` | 1–8 ms | Tiny table, never the problem |

**DB saturation.** The feed's real queries for both client cities (36 queries) were run at
concurrency 1, 4 and 8. Eight is production's maximum: 4 uvicorn workers × pool of 2.

| Concurrency | Median per query | p90 | Wall time for 36 queries |
|---|---|---|---|
| 1 | 124 ms | 180 ms | 4.8 s |
| 4 | 232 ms | 560 ms | 2.5 s |
| 8 | 471 ms | 950 ms | 2.5 s |

Throughput stops improving at about 4 concurrent queries, and beyond that each query just gets
slower. The RDS instance is CPU-bound, so **adding connections cannot help; only doing less
work per query can.**

**App side.** The ZipData burst was replayed against the real app in-process, with the real
pool, read-only:
- Cold, 1 area: the slowest request took 12 s, and **10.7 s of that was waiting for a pool
  connection**. Across requests, 85–90% of the time was queueing.
- Warm (cache hit): all 23 requests finished in 20 ms. **The slowness is entirely the
  cold (cache-miss) path.**
- Caveat: the replay ran from a laptop with ~266 ms RTT to RDS, which inflates absolute times.
  The wait-versus-query ratio and the DB-side numbers above do not depend on it.

### Root causes (ranked)
1. **No `city` index** on `signal.listing_fact` or `signal.market_event`, and no `zip_code` index
   on `market_event`. Every city chart is a full table scan.
2. **The DB CPU saturates** under the page's concurrent burst.
3. **Pool queueing.** The pool is 1 connection plus 1 overflow per schema per worker, so
   requests wait behind each other.
4. **Duplicate and redundant work:**
   - The feed and rail request the same 3 endpoints at the same moment.
   - `home-price-trend`, `value-per-sqft` and `homes-sold` scan the same rows.
   - No chart bounds its date range. The data goes back to 1916, but the page shows 13 months.
5. **The cache helps only repeat visits.** It is per worker (×4) with a 15-minute TTL, and every
   new area is cold.
6. **Pointless requests.** 9 of the 20 feed requests go to endpoints that don't exist here and get 404s.

---

## Fix 1 — Coalesce concurrent cache misses; repair the session-kwarg cache key ✅

**Files:** `core/cache.py` (`cached` decorator)

### Problem
- **(a) Duplicate queries.** When several identical requests missed the cache at the same moment,
  each one ran its own DB query. On the Signals page the feed and rail both request
  `available-inventory`, `price-drop-pressure` and `rate/current` at once, so each area ran
  13 queries instead of 10. After a TTL expiry, every concurrent visitor also re-ran the query
  together (a stampede).
- **(b) Caches that never hit.** The key builder skipped the session only when it was the first
  *positional* argument. Most non-signal routes call `Service.method(session=db, ...)`, so
  `str(session)` ended up in the key. It contains the object's memory address, which is unique
  per request. **Those caches never hit**, and every request just added an entry. Affected:
  healthcare, crime, cost_of_living, employer, analytics, mls. Signal routes pass the session
  positionally and were not affected.

### Solution
- **Single-flight.** The first caller for a key registers an `asyncio.Future`, runs the query
  and publishes the result or exception. Concurrent callers for the same key await that future
  instead of querying.
- **Session excluded from the key** whether it is passed positionally or as `session=`.

### Approach and why
- **Why in-process single-flight:**
  - It sits in the one decorator every service already uses, so there are zero call-site changes.
  - uvicorn runs one event loop per worker, so an in-memory dict of futures is correct
    and needs no locks.
  - The follower uses `asyncio.shield`, so a follower's client disconnecting cannot cancel
    the leader's query.
  - If the *leader* is cancelled, followers recompute with their own session instead of failing.
  - Errors are shared with the followers but **not cached**, so the next request retries.
- **Alternatives rejected:**
  - *`asyncio.Lock` per key:* same effect but more bookkeeping, and waiters would re-check the
    cache after the lock instead of receiving the value directly.
  - *Redis cache or distributed lock:* coalesces across workers too, but adds new infrastructure.
    This quick fix gets most of the benefit; a shared cache is tracked separately.
  - *Fix it in ZipData by not requesting duplicates:* the rail and feed are separate components
    and it's another team's repo. It's also only a partial fix, since stampedes after TTL
    expiry would remain.
- **Behaviour change to note:** fixing (b) means the affected non-signal endpoints now really
  cache for their configured TTL (mostly 15 min), which is what their cache definitions intended.

### Verification
An offline async test with no DB:
- 5 concurrent identical calls → 1 execution.
- The `session=` kwarg is excluded from the key.
- An exception reaches all waiters, is not cached, and the next call retries.
- Leader cancelled → the follower recomputes.
- Follower cancelled → the leader is unaffected.
- The app still imports.

---

## Fix 2 — City (and zip) indexes for the signal tables 📝 SQL ready, pending DBA

**Files:** `sql/2026-09-23_signal_city_indexes.sql` (not applied by us)

### Problem
Root cause #1: city-scoped charts scan the full table, and ZipData always prefers city.
`market_event` has only a county-leading index, so it scans for zip too.

### Solution
Four indexes that mirror the existing zip/county ones:

| Index | Columns | Serves |
|---|---|---|
| `ix_lf_city_closed` | `listing_fact (city, property_type, close_date) WHERE standard_status='Closed'` | price trend, $/sqft, homes sold, speed to sell, DOM, sold listings |
| `ix_lf_city_list` | `listing_fact (city, property_type, list_date)` | fresh supply, inventory, price bands, active/new listings |
| `ix_me_city_scope` | `market_event (city, property_type, kind, month)` | price-drop pressure, price cuts (city) |
| `ix_me_zip_scope` | `market_event (zip_code, property_type, kind, month)` | price-drop pressure, price cuts (zip) |

### Approach and why
- **Why mirror the existing indexes:** the same query shapes already run in 4–25 ms by zip
  through `ix_lf_closed` / `ix_lf_list`. That is proven, predictable plan behaviour.
- **Why `CONCURRENTLY`:** the loader keeps writing (incremental upserts). A plain
  `CREATE INDEX` would block those writes for the whole build.
- **Why a SQL file and not an app migration:** the `signal` tables are owned by `postgres` and
  are loaded by an external pipeline that isn't in this repo. This service is read-only against
  `signal`, and production DB changes need owner sign-off.
- **Checked:** the indexes survive loads. The loader upserts and occasionally reloads with
  `TRUNCATE` + `INSERT`; `pg_stat` counters show the table has never been dropped. `TRUNCATE`
  keeps indexes.
- **Alternatives rejected:**
  - *Rewrite ZipData to scope by zip:* wrong semantics. City is a jurisdiction and spans
    several zips (Menlo Park is 94025, 94026 and 94027).
  - *Expression index or a mapping table from city to zips:* more complex, with no benefit
    over a plain btree on `city`.
  - *Materialized per-month stats table:* bigger design change; see the open items at the end.

### Verification (after the DBA runs it)
Run the read-only checks at the bottom of the SQL file: all indexes valid, and the city chart
plans use Index or Bitmap scans instead of a Seq Scan.

---
## Fix 3 — Rewrite `available-inventory` as a running sum ✅

**Files:** `core/categories/signal/market/repository.py::available_inventory`

### Problem
The query built one row per month since 2020 (~81 months) and **joined it to every listing in
the area**. It then tested each (month, listing) pair against the active and in-contract
conditions, so the work grew as months × listings. Even by zip, with an index, it cost ~250 ms,
and for a county it cost 3.4 s. It was the slowest single chart, and the rail and feed both
request it.

### Solution
The query now uses events instead of the cross product:
- A listing is **active** at month-end `E` when `list_date ≤ E < COALESCE(pending_date, close_date)`.
  It is **in contract** when `pending_date ≤ E < close_date`.
- Each listing emits `+1` in the month its interval opens and `-1` in the month it closes.
  The close month is clamped to be no earlier than the open month, so bad data (pending before
  list) nets to 0, exactly as the original interval test did.
- The month series from 2020 onward is `UNION`ed in with zero deltas, so every month still appears.
  A **running `sum() OVER (ORDER BY month)`** then gives the count at each month-end.
- Deltas from before 2020 are still included in the running total, so listings that opened
  before 2020 and are still active are counted.
- `EXISTS (SELECT 1 FROM f)` keeps the original behaviour of returning **no rows** for an area
  with no listings, which the inner join used to do implicitly.

### Approach and why
- **Why the running sum:** each listing is read once and the work grows with listings plus
  months, not listings × months. It gives **the same response contract with no API change**,
  so ZipData is unaffected.
- **Alternatives rejected:**
  - *Only return the last 13 months:* shrinks the months side of the product but keeps the
    cross product, and changes the payload. Date bounding is handled separately (Fix 5) and
    composes with this fix.
  - *Precompute monthly inventory in a table:* fastest to read, but needs a writer job in the
    loader pipeline, which we don't own. That is kept as a future option.
  - *`LATERAL` per month with index range counts:* still ~81 index probes per request, and more
    complex SQL.

### Verification
**Correctness.** The old SQL (from `git HEAD`) and the new SQL were run side by side, read-only,
against production data: 7 scopes (Menlo Park, Portola Valley, Palo Alto, 94025, 94028,
San Mateo county, and a nonexistent city) × SF/CONDO/TOWNHOUSE. **All 21 results match row for
row**, including the empty-area cases.

**Speed.** DB-side execution time from `EXPLAIN ANALYZE`, best of 3:

| Scope | Old | New | Speed-up |
|---|---|---|---|
| city=Menlo Park, SF | 313 ms | 80 ms | 3.9× |
| city=Portola Valley, SF | 131 ms | 71 ms | 1.8× |
| zip=94025, SF | 254 ms | 16 ms | 15.5× |
| county=San Mateo, SF | 3,359 ms | 161 ms | 20.9× |

The remaining ~70–80 ms for cities is the sequential scan. With Fix 2's `ix_lf_city_list` in
place, city scope should match the zip figure (~16 ms).

---
## Fix 4 — One closed-sales query shared by three charts ✅

**Files:** `core/categories/signal/market/repository.py` (`closed_monthly` replaces
`home_price_trend`, `value_per_sqft` and `homes_sold`), `core/categories/signal/market/service.py`
(`_closed_monthly`), `core/cache.py` (`market_closed_monthly_cache`)

### Problem
`home-price-trend`, `value-per-sqft` and `homes-sold` each scanned the **same rows**: the area's
closed sales for one property type.
- `homes-sold` is literally the `sample_size` column of `home-price-trend`.
- `value-per-sqft` is the same set restricted to `living_sqft > 0`.

The feed requests price SF, price CONDO, $/sqft SF, $/sqft CONDO and homes-sold SF, which meant
**5 scans per area where 2 are enough**. By city, each one was a full table scan.

### Solution
- **One repository query, `closed_monthly`**, returns per month:
  - `median_sale_price` and `sample_size` (all closed sales)
  - `median_ppsf` and `ppsf_sample_size`, computed with `FILTER (WHERE living_sqft > 0)`
- **A service-level cached helper `_closed_monthly`** has its own TTL cache. Through Fix 1's
  coalescing, the three endpoints requested together for one area and type cost **one** scan.
- **The endpoints keep their exact response models** and map from the shared rows.
  `value-per-sqft` drops months where `ppsf_sample_size = 0`, reproducing the old `WHERE`, and
  uses `ppsf_sample_size` as its `sample_size`, as before.

### Approach and why
- **Why share one query, not change the API:** combining at the query and cache layer gives the
  saving **without an API change**. ZipData keeps calling three endpoints and gets identical JSON.
- **Why one cache entry per (area, level, ptype):** this is the same granularity as the endpoint
  caches, so no new invalidation concerns.
- **Alternatives rejected:**
  - *A new combined endpoint returning all three series:* also cuts HTTP round-trips, but needs
    a coordinated ZipData change. It can come later; this fix is independent of it.
  - *Leave the queries separate and rely on the indexes:* indexes make each scan cheaper, but
    running 3 queries where 1 is enough still triples DB work under the concurrent burst. The
    two fixes stack.
  - *Merge SF and CONDO into one query too:* possible, but `ptype` is part of every endpoint's
    cache key. Mixing types would couple unrelated cache entries for a smaller gain.

### Verification
**Correctness, end to end.** A snapshot harness ran **all 135 signal requests** (every chart ×
SF/CONDO × 6 scopes, the drill-downs and rates) through the real app for both `git HEAD` and the
working tree, read-only.
- **All chart, rate, price-cut and breakdown responses are identical.**
- The only differences were 8 `/market/listings/` responses. They contain the same rows in a
  different order, and HEAD compared with itself shows the same 8 differences, so this is
  existing nondeterminism, fixed below.

**DB-side execution** (`EXPLAIN ANALYZE`, SF, best of 3):

| Scope | Old: 3 queries | New: 1 query | Change |
|---|---|---|---|
| city=Menlo Park | 340 ms | 107 ms | 3.2× less |
| city=Portola Valley | 331 ms | 104 ms | 3.2× less |
| zip=94025 | 23 ms | 11 ms | 2.1× less |

---

## Fix 4b — Deterministic order for drill-down lists ✅

**Files:** `core/categories/signal/market/repository.py` (`listings`, `price_cuts`)

### Problem
- **`listings`** sorted only by a date (`COALESCE(new-listing date, close_date, list_date)`).
  Many listings share a date, and parallel sequential scans return rows in varying order. The
  same request could therefore return tied rows in a different order each time. With
  `LIMIT 100`, it could return a **different set** of rows at the cut-off.
- **`price_cuts`** could tie on `(event_date, cut_amount)`.

### Solution
Add the primary key as the final sort key: `f.listing_key_numeric` for listings and
`me.src_event_id` for price cuts.

### Approach and why
- **Why the primary key:** it is the smallest possible change. It only orders rows that were
  previously tied, so it is still a valid version of the old ordering. The drill-down now shows
  the same rows in the same order on every load.
- **Alternatives rejected:**
  - *Sort by more business columns (price, etc.):* changes the intended order semantics and is
    still not guaranteed unique.
  - *Leave it:* the lists would stay unstable even once index plans changed the scan order.

---
## Fix 5 — Bound trend charts to a trailing window (`months`, default 24) ✅

**Files:** `core/categories/signal/market/routes.py` (`months_param`, `DEFAULT_TREND_MONTHS = 24`,
`MAX_TREND_MONTHS = 600`), `service.py`, `repository.py` (`_window_start`, bounds in
`closed_monthly`, `price_drop_pressure`, `fresh_supply`, `available_inventory`, `speed_to_sell`)

### Problem
Every trend chart returned the area's **entire history**. Menlo Park SF has closed sales back to
2012, which meant 174–337 monthly points per chart. The only consumer, ZipData's Signals feed,
plots the **last 13** (`MONTHLY_CHART_POINTS = 13`, window ending at the current month).
- The DB aggregated and sorted everything for the medians (`percentile_cont`).
- The API serialised it all, and ZipData parsed it and threw most of it away.
- Only 556 of Menlo Park's 3,754 SF closed sales fall in the last 24 months.

### Solution
- **New optional query parameter `months`** on the 7 trend endpoints (`home-price-trend`,
  `value-per-sqft`, `price-drop-pressure`, `homes-sold`, `available-inventory`, `fresh-supply`,
  `speed-to-sell`). It sets how many trailing months to return, including the current one.
  The **default is 24**, the range is 1–600, and `months=600` returns full history.
- **The window start is computed in Python** (`_window_start`) and bound as a plain `date`:
  - `close_date >= :start` for closed-sales charts and speed to sell
  - `list_date >= :start` for fresh supply
  - `month >= :start` for price-drop pressure
- **`available-inventory`** still reads every listing, because a listing opened before the window
  can be active inside it and the running sum needs its delta. Only the emitted months are
  bounded, never earlier than the original 2020-01 floor.
- **Drill-downs** (`listings`, `price-cuts`, `dom-breakdown`, `price-distribution`) are unchanged.
  They already take `year`/`month` filters or report current state.

### Approach and why
- **Why a default window, not opt-in:**
  - The speed-up only matters if the real caller gets it. An opt-in parameter would need a
    ZipData release first, but the default helps immediately.
  - **We checked every consumer before changing the default:**
    - ZipData's feed uses 13 months ending at the current month, which is inside 24.
    - The frontend's direct `fetchMarketChart` is never called.
    - zipai-rag doesn't call these endpoints.
    - Nothing else in the repos does.
- **Why 24 months:** it covers the 13 the feed plots, with room for year-over-year comparisons.
  Anyone who needs full history can still ask for it with `months=600`.
- **Why the bound is computed in Python:** it becomes a plain `date` parameter, so the planner
  can use it as the range bound on the `(…, close_date)` / `(…, list_date)` index columns.
  With Fix 2's indexes, city queries become an index range scan over ~24 months instead of all
  history.
- **Alternatives rejected:**
  - *Trim in Python after querying:* saves payload but none of the DB work.
  - *Make ZipData send `months=13`:* also good, and it can still do that. It isn't required, and
    it needs a coordinated release.
  - *Hard-code 13 months:* ties the API to one screen's layout. A parameter with a sensible
    default keeps it general.

### Verification
- **`months=600` equals HEAD.** Every trend endpoint across all 6 scopes × SF/CONDO gave
  byte-identical JSON. So the change is purely a window filter and no calculation changed.
- **The default (24) equals HEAD cut to `month >= 2024-10-01`.** All **72** trend responses match.
  Points returned fell from **8,642 to 1,326**, and the trend payload from **726 KB to 117 KB**
  (6.2× smaller).
- **The Fix 4b tie-breaker** explains every `/listings` difference against HEAD. Each is either
  the same rows in a now-fixed order, or a swap at the `LIMIT 100` cut-off between rows whose
  true sort key ties exactly with the cut-off row's key (checked against the DB).
- **DB time per area for the whole feed**, from `EXPLAIN ANALYZE` with Fixes 3, 4 and 5 combined:

| Scope | Old: 9 queries | New: 6 queries | Change |
|---|---|---|---|
| city=Menlo Park | 1,205 ms | 554 ms | 2.2× less |
| city=Portola Valley | 998 ms | 540 ms | 1.8× less |
| zip=94025 (indexed today) | 422 ms | 83 ms | 5.1× less |
| zip=94028 (indexed today) | 148 ms | 67 ms | 2.2× less |

  What remains for cities (~550 ms) is 6 sequential scans. With Fix 2's indexes, city scope is
  expected to land where zip is today (~70–85 ms per area).

---
## Fix 6 — Longer cache lifetime for trend charts (15 min → 1 h) ✅

**Files:** `core/cache.py` (`MARKET_TREND_TTL = 3600` for the 7 trend-chart caches and
`market_closed_monthly_cache`)

### Problem
The slow part of the page is entirely the cold (cache-miss) path. Each trend cache expired every
15 minutes, per area, per ptype, per worker (×4). But the `signal` data only changes when the
external MLS loader runs. `signal.load_state` shows incremental loads, the last on 2026-09-08,
at most about daily. So the 15-minute expiry forced a cold, slow page load every 15 minutes with
**no freshness benefit**.

### Solution
- The 7 trend-chart caches, plus the shared closed-sales cache, now last **1 hour**.
- The drill-downs keep their shorter lifetimes (`listings` / `price-cuts` 5 min, bands and
  buckets 15 min). They are per-click, lighter, and closer to "live" in the UI.

### Approach and why
- **Why 1 hour:** it cuts cold loads per area and worker by 4×. Worst-case staleness after a
  loader run is 1 hour, which is negligible against a loader that runs at most daily.
- **Alternatives rejected:**
  - *Much longer lifetime (6–24 h):* bigger hit rate, but a fresh load would then show up
    hours late. That's too much for a daily feed without an invalidation signal.
  - *Invalidate on `signal.load_state.last_source_ts` change:* the correct long-term design,
    allowing a long lifetime with minutes of staleness. It needs a background poller per worker
    or a loader hook. It's listed under open items as the upgrade path.
  - *Shared Redis cache:* removes the ×4 per-worker cold starts, but is new infrastructure.
    Also listed under open items.

---
## End-to-end result so far (Fixes 1, 3, 4, 4b, 5, 6 — before Fix 2's indexes)

ZipData's real Signals burst was replayed against the real app, in-process, read-only, with a
cold cache. HEAD and the working tree ran back to back:

| Scenario | Before (HEAD) | After | DB queries issued |
|---|---|---|---|
| 1 area (Menlo Park), 8 in flight | 15.3 s wall · slowest 12.4 s | **10.4 s** · slowest **7.3 s** | 13 → **8** |
| 2 areas (Menlo Park + Portola Valley) | 33.5 s wall · slowest 26.2 s | **16.1 s** · slowest **11.7 s** | 26 → **14** |

Absolute numbers come from a laptop at ~266 ms RTT to RDS, where each query pays 3–4 round trips
(checkout ping, BEGIN, prepare, execute). In production, next to RDS, that overhead is ~1 ms.
What carries over is the **~40% fewer queries** and the **2–5× less DB time per query**.
Fix 2 (indexes) is the remaining big step for city scope.

---

## Post-deploy measurements (2026-09-23 — indexes applied, code deployed)

Indexes from Fix 2 were applied by the DBA and are all **valid**. `ANALYZE` was run on both
tables. The code (PR #60) is deployed to `54.173.204.147:8001`, confirmed by `months` appearing
in the OpenAPI spec.

### Database (read-only, `EXPLAIN ANALYZE`)
No sequential scans remain. Every feed query uses `ix_lf_city_*`, `ix_me_city_scope`,
`ix_me_zip_scope` or the existing zip indexes.

**Feed DB time per area:**

| Scope | Original (old code, no indexes) | Now | Change |
|---|---|---|---|
| city=Menlo Park | 1,205 ms (9 queries) | **22.6 ms** (6 queries) | ~53× less |
| city=Portola Valley | 998 ms | **6.2 ms** | ~160× less |
| zip=94025 | 422 ms | **21.7 ms** | ~19× less |

**Under load.** The same 36-query workload (both client cities) as the baseline saturation test:

| Concurrency | Before: median / p90 | Now: median / p90 | Total DB time |
|---|---|---|---|
| 8 (prod max) | 471 ms / 950 ms | **1.7 ms / 10.6 ms** | 20,066 ms → **188 ms** |

The CPU saturation behind the pool queueing is gone.

### Deployed server (GET only, from a client ~220 ms RTT away)
- **Server-side cache-miss cost per chart:** each endpoint requested sequentially, cold then warm,
  on a keep-alive connection. The difference is the server's own work for a miss.
  - **10–35 ms** typically.
  - An occasional 115–236 ms, most likely a worker opening a fresh DB connection.
  - Warm requests cost only the network hop.
- **Full Signals burst** (2 areas, 46 requests, ZipData's pattern, cold via unused `months`):
  - Page wall time: **1.7–3.5 s** from the test client.
  - Median request: ~600 ms, of which ~220 ms is network.
  - **0 requests over ZipData's 5 s timeout.**
- **About the tail.** The multi-second tail in the burst comes from the test client's
  long-haul link (46 parallel connections at ~220 ms RTT). The warm burst, with no DB work,
  shows the same tail. ZipData calls this API from AWS, so it should see server time plus
  a few ms.
- **Before, for comparison:** ZipData had logged `rate/history` at >8 s cold, and feed cards were
  hitting the 5 s timeout. Locally, the old code's cold burst for 1 area took 15.3 s.

---

## Open items — recommended, not done in this repo

### A. Apply Fix 2's indexes (DBA / pipeline owner)
This is the largest remaining win for city scope. After applying, re-run the read-only checks
in the SQL file, and ideally repeat the burst replay.

### B. ZipData changes (other repo — `Jainam23/ZipData`)
1. **Stop requesting 9 charts that don't exist here.** These are `buyer-leverage`,
   `price-reductions`, `where-value-lives`, `buyer-demand`, `sales-by-price-range`,
   `activity-pulse`, `listing-churn`, `price-momentum` and `neighborhood-scorecard`
   (`client_signals_market._FEED_FETCHES`). If `ZIPAI_SIGNALS_URL` points at this service,
   they are guaranteed 404s that tie up ZipData's per-area thread pool (8 threads) and can never render.
   *First confirm which host `ZIPAI_SIGNALS_URL` points to in production.*
2. **Optionally send `months=13`.** Our default of 24 already covers it, but asking for
   exactly what's plotted makes the contract explicit.
3. **Share one fetch between the rail and the feed** for `rate/current`, `price-drop-pressure`
   and `available-inventory`. Fix 1 already coalesces these server-side within a worker, but
   they are still extra HTTP calls, and they can land on different workers.

### C. Connection pool — deliberately *not* changed
Today the pool is `pool_size=1, max_overflow=1` per schema per worker. Raising it was
considered and rejected for now:
- **The DB is CPU-bound.** Throughput plateaus at ~4 concurrent queries, and more connections
  just make each query slower.
- **Connections are scarce.** `max_connections = 100` on RDS. `zipai-external` already holds
  ~44 idle connections (11 schemas × 4 workers), and zipai-rag holds ~13.

Revisit after Fix 2. With cheap queries, a signal-only pool of 2 + 2 may help the burst without
adding CPU pressure. It should be measured, not guessed.

### D. Longer-term (bigger designs)
- **Cache invalidation on load.** Poll `signal.load_state.last_source_ts` every few minutes
  per worker and clear the market caches when it changes. That allows lifetimes of hours with
  only minutes of staleness.
- **Shared cache (Redis).** Removes the ×4 per-worker cold starts, and coalesces across workers.
- **Pre-warm watched areas** after each load, for example the client's cities, so the first
  visitor never hits the cold path.
- **Precomputed monthly aggregates** in the loader pipeline. `signal.market_stats_monthly`
  already exists with 612 rows and could be evaluated for this. Charts then become key lookups.

---

## Other issues noticed during this work (out of scope, not changed)
- **`listings` / `price-cuts` accept `only_public` but never apply it.** There is no
  `internet_list` filter in the SQL, even though routes pass `ONLY_PUBLIC_DEFAULT = True`.
  ZipData re-gates rows in its BFF (`gate_listing_rows`), so this is mitigated there, but
  the API itself does not honour the flag.
- **Signal data freshness.** The last load was 2026-09-08, 15 days before this work. If
  daily loads are expected, the loader may have stalled.
- **The Vector log shipper was crash-looping** (exit 78) on an invalid `docker_logs` config.
  `include`, `read_from` and `ignore_older_secs` are `file`-source options. While it was down,
  analytics events were not forwarded to `/v1/internal/vector/events`. Fixed in
  `vector/vector.yml` (use `include_containers`); needs redeploy and validation on the server.
- **Implausible dates in the data.** `list_date` spans 1916–2027. Future-dated rows could
  show up in trend charts.

---

## Status summary

| # | Change | Status | Effect |
|---|---|---|---|
| 1 | Coalesce concurrent cache misses; fix `session=` cache key | ✅ Done | −3 duplicate queries per area; stampede protection; non-signal caches now actually hit |
| 2 | City / zip indexes on `listing_fact`, `market_event` | 📝 SQL ready, pending DBA | City charts from 70–570 ms to ~zip speed (4–25 ms) |
| 3 | `available-inventory` running-sum rewrite | ✅ Done | 2–21× faster; identical output |
| 4 | Shared closed-sales query for 3 charts | ✅ Done | 5 → 2 scans per area; 3.2× less DB time for those charts |
| 4b | Deterministic tie-break for drill-down lists | ✅ Done | Stable order and `LIMIT` set |
| 5 | Trailing window `months` (default 24) on trend charts | ✅ Done | 6.5× fewer points, 6.2× smaller payload; index-range friendly |
| 6 | Trend cache lifetime 15 min → 1 h | ✅ Done | 4× fewer cold loads |
| A–D | DBA, ZipData, pool, long-term items | Recommended | See open items |
