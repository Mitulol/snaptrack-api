# ADR 0001 — Tuning the API after the first load test

- **Status:** accepted
- **Date:** 2026-09-07
- **Context:** Phase 2 (performance & load testing)

## Context

The first k6 run (`loadtest/k6/script.js`, auth + photo CRUD mix) against the
Phase 0/1 stack, at 200 VUs / 0.1 s think time:

| Metric | Baseline |
| --- | --- |
| Throughput | **88 req/s** |
| `http_req_duration` p95 | **1.43 s** |
| Error rate | **0.32 %** (34 failed, 111 interrupted iterations) |
| `api` container CPU | **~208 %** (2 cores, pinned) |
| Host | 12 vCPU — **10 idle** |

Two things stood out:

1. **The API was pinned at 2 cores.** `WEB_CONCURRENCY=2` → 2 uvicorn workers,
   each maxing one core, while 10 host cores sat idle. Throughput was flat from
   50 → 200 VUs; extra load just queued.
2. **`POST /photos` was `async def` but did blocking work** — `PIL` decode +
   `verify()`, `file.write_bytes()`, and two synchronous SQLAlchemy commits —
   directly on the event loop. Every upload stalled its worker's loop for other
   requests (including `/healthz`).

## Decision

| Change | From | To | Why |
| --- | --- | --- | --- |
| `WEB_CONCURRENCY` (uvicorn workers) | 2 | **6** | Use the idle cores; leave ~6 for Postgres + Celery + k6. |
| `POST /photos` handler | `async def`, blocking calls inline | **`def`** (runs in the threadpool) | CPU/IO work no longer blocks the event loop; other requests on the worker stay responsive during an upload. |
| Caption on upload | second `PATCH`-style call (extra commit + cache delete) | set in the initial `INSERT` | One transaction per upload instead of two. |
| SQLAlchemy pool (`DB_POOL_SIZE` / `MAX_OVERFLOW`) | 10 / 20 per worker | **5 / 5** (api), **2 / 4** (celery) | 6 workers × 30 would blow past Postgres' 100-connection default. New budget: api ≤ 60 + celery ≤ 24. |
| Postgres `max_connections` | 100 (default) | **200** | Headroom for the pools above + migrations + `psql`. |
| `PHOTO_CACHE_TTL_SECONDS` | 60 | **300** | Reads dominate and every write path invalidates the key explicitly, so a longer TTL raises hit rate with no staleness risk. |
| `CELERY_CONCURRENCY` | 2 | **4** | Higher upload throughput ⇒ more thumbnail jobs; keep queue age low. |

## Results

Re-running the **identical** 200 VU / 0.1 s test after the changes:

| Metric | Baseline | Tuned | Δ |
| --- | --- | --- | --- |
| Throughput | 88 req/s | **207 req/s** | **+135 %** |
| Error rate | 0.32 % | **0.00 %** | 0 failed / 22 654 |
| Interrupted iterations | 111 | **0** | — |
| `http_req_duration` p95 | 1.43 s | 1.30 s | −9 % (still saturated at this load) |
| `api` CPU | ~208 % | ~570 % | now using ~6 cores |

At the **reference load** (50 VUs / 0.3 s, ~135–143 req/s) the tuned stack
meets every SLO threshold: p95 ~270 ms, reads ~215 ms, uploads ~350 ms,
0 % errors (`loadtest/results/summary.html`).

## Consequences

- 200 VUs still pushes p95 well over SLO — that load is simply past single-node
  capacity (~160 req/s). The fix is horizontal scaling, not more tuning
  (see `docs/perf_slo.md`).
- 6 workers × ~90 MB ≈ 540 MB RSS for `api` (was ~220 MB). Fine on this host;
  worth noting for smaller deploy targets — `WEB_CONCURRENCY` is env-tunable.
- The sync `def` upload handler relies on Starlette's threadpool (default 40
  threads). If uploads ever dominate traffic, that pool size becomes the next
  knob.
