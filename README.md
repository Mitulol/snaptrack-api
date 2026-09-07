# SnapTrack API

[![lint-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml)
[![contract-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/contract-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/contract-test.yml)
[![postman-smoke](https://github.com/Mitulol/snaptrack-api/actions/workflows/postman-smoke.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/postman-smoke.yml)

A photo-tracking HTTP API: users upload photos, SnapTrack stores per-photo
metadata, derives thumbnails on a background worker, and serves hot metadata
reads from a Redis cache-aside layer. Built with FastAPI + SQLAlchemy +
Celery, and packaged as a self-contained Docker Compose stack (API, Postgres,
Redis, worker, Prometheus, Grafana) that runs entirely on a laptop.

This repository is developed in phases; see [Roadmap](#roadmap) for status.

```
                       ┌───────────────┐        enqueue job         ┌────────────┐
   client ──HTTP──▶     │  FastAPI (api) │ ──────────────────────▶    │   Redis    │
                       │               │ ◀───── cache get/set ─────  │ (broker +  │
                       │  JWT auth     │                             │  cache +   │
                       │  ownership    │ ──── read/write ────┐       │  results)  │
                       │  /metrics     │                     │       └─────┬──────┘
                       └───────┬───────┘                     ▼             │ pull job
                          scrape│                      ┌───────────┐       ▼
                               ▼                       │ Postgres  │  ┌──────────────┐
                     ┌────────────┐  ┌─────────┐        │ (metadata)│  │ Celery worker│
                     │ Prometheus │─▶│ Grafana │        └───────────┘  │  Pillow      │
                     └────────────┘  │  (RED)  │  shared volume ───────┘  writes
                                     └─────────┘  (originals + thumbs)   thumb + status
```

## Why it is shaped this way

- **Thumbnails are async, not inline.** Image resizing is CPU-bound and
  variable; doing it in the request path would tie up a web worker and make
  upload latency depend on image size. Upload writes the original, creates a
  `thumbnail` row in state `pending`, and returns immediately. A Celery worker
  picks the job off Redis, resizes with Pillow, and moves the row through
  `processing → ready` (or `failed`). Clients poll `GET /photos/{id}/thumbnail`.
- **The worker fails fast on permanent errors.** A corrupt or missing source
  file will never succeed on retry, so those raise straight to `failed`.
  Unexpected errors get bounded exponential-backoff retries
  (`THUMBNAIL_TASK_MAX_RETRIES`, default 3) before landing in `failed`.
- **Cache-aside, and Redis is not on the critical path.** `GET /photos/{id}`
  checks Redis first and back-fills on a miss; writes (`PATCH`/`DELETE`) and the
  worker invalidate the key. Every cache call is wrapped so a Redis outage
  degrades to "always a cache miss" — the API stays up, just slower. `/readyz`
  reports Redis health separately so this is visible.
- **Ownership checks return 404, not 403.** Asking for a photo you don't own
  gets the same response as one that doesn't exist, so the API isn't an
  existence oracle for other users' photo IDs.
- **422 is left to request-model validation.** Business rejections (bad image
  bytes, ownership, conflicts) use their own status codes with a shared
  `ErrorResponse` model, so the 422 + `HTTPValidationError` contract FastAPI
  generates stays accurate. The committed OpenAPI spec lists every status code
  each operation actually returns — enforced by the nightly contract test.
- **Migrations, not `create_all`.** The stack runs `alembic upgrade head` on
  API start. The test suite uses `create_all` against SQLite for speed and runs
  the real Alembic migration against Postgres in CI.

## Tech stack

| Concern            | Choice                                                          |
| ------------------ | -------------------------------------------------------------- |
| API framework      | FastAPI 0.115 (OpenAPI 3.1, Pydantic v2)                       |
| ORM / migrations   | SQLAlchemy 2.0 (typed models) / Alembic                       |
| Datastore          | PostgreSQL 16                                                  |
| Async jobs         | Celery 5.4 with a Redis broker + result backend               |
| Cache              | Redis 7, cache-aside on photo-metadata reads                  |
| Auth               | JWT (HS256) bearer tokens, `bcrypt` password hashing          |
| Images             | Pillow 11                                                     |
| Metrics            | `prometheus-fastapi-instrumentator` → Prometheus 3 → Grafana 11 |
| Contract testing   | Schemathesis 4 (nightly, against the live Compose stack)      |
| Smoke testing      | Postman collection + Newman (post-deploy in CI)               |
| Packaging          | Docker Compose; single image runs both `api` and `worker`     |
| CI                 | GitHub Actions — flake8, pytest vs. real Postgres/Redis, spec drift |

## Running it locally

Requires Docker + Docker Compose. No cloud services.

```bash
docker compose up -d --build         # api :8000, prometheus :9090, grafana :3000
curl -s localhost:8000/readyz | jq   # {"status":"ok","checks":{...}}
open http://localhost:8000/docs      # interactive OpenAPI docs
open http://localhost:3000           # Grafana → "SnapTrack API — RED" (anon admin)

./scripts/smoke.sh                   # end-to-end: register→upload→thumbnail→cache→delete
make contract                        # Schemathesis against the running stack
make postman                         # Newman smoke suite against the running stack
docker compose down -v               # stop and wipe volumes
```

Postgres and Redis are not published to host ports (other local stacks already
hold 5432/6379); use `docker compose exec postgres psql -U snaptrack` for a shell.

### Local dev without Docker

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # point DATABASE_URL/REDIS_URL at your services
pytest                               # 70 tests, ~20s on SQLite + fakeredis
flake8 app tests scripts
python scripts/export_openapi.py     # regenerate openapi/ after changing routes
```

## Observability (Phase 1)

`/metrics` exposes request counts and latency histograms
(`prometheus-fastapi-instrumentator`). Prometheus scrapes the API every 5s;
Grafana is provisioned with the datasource and one dashboard,
**`observability/grafana/dashboards/snaptrack-red.json`**, laid out by the RED
method:

| Signal       | Panels                                                        |
| ------------ | ------------------------------------------------------------ |
| **Rate**     | total req/s; req/s by `{method, handler}`                    |
| **Errors**   | 5xx error-rate % (thresholded); 2xx/4xx/5xx per second      |
| **Duration** | p50/p90/p95/p99 (from `_highr_` buckets); p95 by endpoint; latency heatmap |

All queries use `$__rate_interval` and the templated Prometheus datasource, so
the JSON imports into any Grafana without editing.

## Contract & smoke testing (Phase 1)

- **OpenAPI 3.1 spec** is generated from the app and committed at
  `openapi/openapi.json` + `openapi/openapi-v1.0.0.json`.
  `scripts/export_openapi.py --check` fails CI if the committed spec drifts from
  the code.
- **Schemathesis** (`.github/workflows/contract-test.yml`) runs nightly and on
  PRs that touch the API. It brings up the Compose stack, seeds one photo,
  fuzzes all 13 operations (examples + coverage + fuzzing + stateful phases),
  and posts the summary to the workflow summary. Config and rationale for the
  two disabled checks are in `schemathesis.toml`.
- **Postman/Newman** (`.github/workflows/postman-smoke.yml`) runs a curated
  smoke suite (`postman/smoke.postman_collection.json`: auth flow, photo CRUD
  happy path, and 4xx cases — 28 assertions) against the freshly-built stack on
  every push to `main`. `postman/snaptrack.postman_collection.json` is the full
  collection generated from the spec.

## API surface

`ErrorResponse` (`{"detail": string}`) is the body for every deliberate 4xx/409.

| Method   | Path                          | Success | Documented errors           |
| -------- | ----------------------------- | ------- | --------------------------- |
| `POST`   | `/auth/register`              | 201     | 400, 409, 422               |
| `POST`   | `/auth/login`                 | 200     | 400, 401, 403, 422          |
| `GET`    | `/auth/me`                    | 200     | 401                         |
| `POST`   | `/photos`                     | 201     | 400, 401, 413, 422          |
| `GET`    | `/photos`                     | 200     | 401, 422                    |
| `GET`    | `/photos/{id}`                | 200     | 401, 404, 422               |
| `PATCH`  | `/photos/{id}`                | 200     | 400, 401, 404, 422          |
| `DELETE` | `/photos/{id}`                | 204     | 401, 404, 422               |
| `GET`    | `/photos/{id}/thumbnail`      | 200     | 401, 404, 422               |
| `GET`    | `/photos/{id}/thumbnail/file` | 200     | 401, 404, 409, 422          |
| `GET`    | `/photos/{id}/file`           | 200     | 401, 404, 422               |
| `GET`    | `/healthz` · `/readyz`        | 200     | `/readyz` → 503 when degraded |
| `GET`    | `/metrics`                    | 200     | —                           |

All photo routes also return `405` (with a correct `Allow` header) for
unsupported methods.

## Results — real numbers

Measured on this machine (Windows + WSL2, Docker Desktop). Load-tested p95 under
concurrency lands in Phase 2 — the latencies below are **single-client
baselines**.

| Metric                                    | Value                                              |
| ----------------------------------------- | -------------------------------------------------- |
| Tests                                     | 70 passing (`pytest`)                              |
| Line + branch coverage                    | **100.0%** (`coverage`, branch on; CI gate 90%)    |
| Lint                                      | flake8 clean (`app` + `tests` + `scripts`)         |
| Contract test                             | Schemathesis: **0 failures** across 13 operations, ~600–720 generated cases (2 non-blocking coverage warnings) |
| Smoke suite                               | Newman: **28/28 assertions**, 18 requests          |
| CI                                        | 3 workflows green — lint-test, contract-test, postman-smoke |
| Thumbnail latency (320×240 PNG, local)    | source→`ready` in ~1–2 s end to end                |
| RED, light single-client traffic          | rate ≈ 1.3 req/s, error-rate 0%, p95 ≈ 13 ms (Prometheus `_highr_` buckets) |
| `GET /photos/{id}` cache hit, 1 client    | p50 ≈ 3.1 ms, p90 ≈ 3.9 ms (n=500)                 |
| `GET /photos` list (DB), 1 client         | p50 ≈ 5.7 ms, p90 ≈ 7.8 ms (n=500)                 |
| `GET /healthz`, 1 client                  | p50 ≈ 1.9 ms, p90 ≈ 3.0 ms (n=500)                 |

### What the contract test found (Phase 1)

Schemathesis was run against the Phase 0 API and **found real gaps**, all now fixed:

1. **`POST /photos` returned `422` with a plain-string `detail`** for a bad
   image — violating FastAPI's own `HTTPValidationError` schema for 422. Moved
   business rejections off 422 to `400`/`404`/`409`/`413` with a shared
   `ErrorResponse` model.
2. **~14 undocumented status codes.** Protected routes returned 401/404/409 that
   the spec never listed. Added `responses={}` to every route + a router-level
   `405`.
3. **`GET /photos?offset=<huge int>` → `500`.** A 20-digit offset overflowed
   Postgres `bigint`. Bounded `offset` to `≤ 1_000_000` (→ 422).
4. **Incomplete `Allow` header on 405.** Starlette builds it from the single
   matched route; FastAPI registers one route per method. Added
   `AllowHeaderMiddleware` to recompute it as the union across the path.
5. **Malformed JSON body → `400`** (Starlette, not 422) was undocumented on the
   JSON-body routes. Now declared.

Two Schemathesis checks are disabled in `schemathesis.toml` with rationale:
`positive_data_acceptance` (Hypothesis doesn't honour `format: email` / binary
when generating "valid" data) and unknown-query-parameter rejection
(intentionally tolerated, per common REST convention).

### What broke while building Phase 0

- **`passlib[bcrypt]` import error** with bcrypt ≥ 4.1 (`__about__` removed).
  Dropped passlib; `app/core/security.py` calls `bcrypt` directly.
- **Alembic + in-memory SQLite in tests.** `engine_from_config` in `env.py`
  builds its own `NullPool` engine, so migrations hit a throwaway connection.
  Tests use `create_all` on SQLite; the real migration runs against Postgres in CI.
- **Host port 5432 already in use** by another local stack. Compose publishes
  only the API (8000), Prometheus (9090), Grafana (3000).

## Roadmap

- [x] **Phase 0** — CRUD + JWT + async thumbnails + Redis cache + Compose + CI
- [x] **Phase 1** — Prometheus + Grafana (RED), versioned OpenAPI 3.1, nightly Schemathesis contract tests, Postman/Newman smoke suite
- [ ] **Phase 2** — k6 load test, documented SLO, tuning ADR, committed HTML report
- [ ] **Phase 3** — photo flag & moderation feature, built test-first, with RBAC
- [ ] **Phase 4** — moderation-notify task, Traefik canary release, `v1.1.0` tag, generated Python SDK

## Repository layout

```
app/
  api/            routers + dependencies + responses + AllowHeader middleware
  core/           security (bcrypt, JWT)
  models/         SQLAlchemy 2.0 typed models
  schemas/        Pydantic request/response models (incl. ErrorResponse)
  services/       photo + image domain logic (no framework coupling)
  workers/        Celery app + thumbnail task
  alembic/        migrations
  cache.py        Redis cache-aside helper (degrades gracefully)
  storage.py      local blob storage (shared volume)
observability/    prometheus.yml + Grafana provisioning + RED dashboard JSON
openapi/          committed OpenAPI 3.1 spec (stable + versioned)
postman/          smoke collection, spec-generated collection, environment, fixtures
tests/            pytest suite (unit + integration), 100% covered
scripts/          smoke.sh (e2e), export_openapi.py (spec + drift check)
```

## Author

Mitul Goel — [github.com/Mitulol](https://github.com/Mitulol) ·
[linkedin.com/in/mitul-goel](https://linkedin.com/in/mitul-goel)

## License

MIT — see [LICENSE](LICENSE).
