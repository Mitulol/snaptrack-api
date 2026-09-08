# SnapTrack API

[![lint-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml)
[![contract-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/contract-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/contract-test.yml)
[![postman-smoke](https://github.com/Mitulol/snaptrack-api/actions/workflows/postman-smoke.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/postman-smoke.yml)
[![integration-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/integration-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/integration-test.yml)
[![loadtest](https://github.com/Mitulol/snaptrack-api/actions/workflows/loadtest.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/loadtest.yml)
[![sdk-gen](https://github.com/Mitulol/snaptrack-api/actions/workflows/sdk-gen.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/sdk-gen.yml)

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
| Load testing       | k6 (Docker), Prometheus remote-write for live Grafana panels  |
| Packaging          | Docker Compose; single image runs both `api` and `worker`     |
| Canary             | Traefik v3 weighted split (compose `--profile canary`)        |
| SDK                | `openapi-python-client` (typed, generated on release)         |
| CI                 | GitHub Actions — flake8, pytest vs. real Postgres/Redis, spec drift, contract, smoke, load, SDK build |

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
pytest                               # 112 tests, ~50s on SQLite + fakeredis
pytest integration_tests/            # 8 more, real Postgres + Redis via pytest-docker
flake8 app tests scripts integration_tests
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
  `openapi/openapi.json` + a versioned copy per release.
  `scripts/export_openapi.py --check` fails CI if the committed spec drifts from
  the code; `oasdiff breaking` fails CI on any breaking change since `v1.0.0`.
- **Schemathesis** (`.github/workflows/contract-test.yml`) runs nightly and on
  PRs that touch the API. It brings up the Compose stack, seeds an admin user +
  a photo + a flag, fuzzes all 16 operations (examples + coverage + fuzzing +
  stateful phases), and posts the summary to the workflow summary. Config and
  rationale for the two disabled checks are in `schemathesis.toml`.
- **Postman/Newman** (`.github/workflows/postman-smoke.yml`) runs a curated
  smoke suite (`postman/smoke.postman_collection.json`: auth flow, photo CRUD
  happy path, and 4xx cases — 28 assertions) against the freshly-built stack on
  every push to `main`. `postman/snaptrack.postman_collection.json` is the full
  collection generated from the spec.

## Moderation feature (Phase 3, `v1.1.0`)

Photo flagging + a moderator review queue, built **test-first**
(`tests/test_moderation_service.py` was written and failing before the service
existed). Full design: [`docs/moderation-feature.md`](docs/moderation-feature.md).

- `POST /photos/{id}/flag` — the photo **owner** raises a flag (`reason` enum + note)
- `GET /moderation/queue` — **admin** only; unresolved flags, newest first
- `POST /moderation/{flag_id}/decision` — **admin** only; `dismiss` (keep) or
  `action` (delete the photo). An `action` cascade-deletes the photo's flags but
  the `moderation_actions` audit row — plain integer refs, no FK — survives.
- **RBAC**, asserted both ways: non-owner flagging → 404, non-admin moderating → 403.
- **OpenAPI diff** `v1.0.0 → v1.1.0` ([`docs/openapi-diff-v1.1.0.md`](docs/openapi-diff-v1.1.0.md)):
  `oasdiff` reports **no breaking changes** (3 added endpoints) — a correct minor bump.
  CI (`contract-test.yml`) fails on any breaking change vs. the released spec.
- **Integration suite** (`integration_tests/`, `pytest-docker`): the real app
  against a throwaway Postgres 16 + Redis 7 — real FK cascade, the audit row
  outliving it, real Redis cache invalidation, and an Alembic
  `downgrade→upgrade` round-trip + "migrations match the ORM" check.

### Decision notifications (Phase 4)

A moderation decision writes the affected reporter(s) a message via a
**transactional outbox**: `moderation_service.decide` creates `notifications`
rows *in the same transaction* as the resolution, then — only after that commit
— enqueues one `notifications.deliver` Celery task per row. Delivery is
pluggable (`NOTIFICATION_BACKEND`): `console` logs it (default / CI),
`file` drops an RFC-822 `.eml`. A retryable failure leaves the row `failed`
with the error recorded; the task retries with backoff, then gives up.
Photo/flag refs on the row are plain integers, so an `action` decision (which
deletes both) doesn't strand the notification.

## Canary release (Phase 4)

`docker compose --profile canary up -d --build` (or `make canary`) adds
**Traefik v3** in front of two API builds — `api` (stable, 90 %) and `api-next`
(canary, 10 %) — with a weighted load-balancer service in
[`deploy/traefik/dynamic.yml`](deploy/traefik/dynamic.yml) that re-weights live.
Traefik's Prometheus metrics feed the **`SnapTrack API — Canary`** Grafana
dashboard (per-backend traffic share, error rate, p95).

Full write-up with real numbers: [`docs/canary-report.md`](docs/canary-report.md).
A 50-VU / 120-s k6 run *through the split*: **9.9986 %** of 35.5 k requests hit
the canary, **0** × 5xx on either backend, canary p50/p95 within ~2 ms of
stable → promoted and tagged `v1.1.0`. (Both builds are the same commit, so this
canary validated the rollout mechanism + that the additive changes don't
regress the hot path — not an A/B of two app versions.)

## Python SDK (Phase 4)

[`sdk/`](sdk/) is a typed client (`httpx` + `attrs`, `py.typed`) **generated**
from `openapi/openapi.json` with `openapi-python-client`.
`.github/workflows/sdk-gen.yml` regenerates it, builds an sdist + wheel, and
uploads them to the GitHub Release on publish; on PRs touching the spec it
dry-runs the generate + build + import and fails if `sdk/` is stale.

## Load testing (Phase 2)

## Load testing (Phase 2)

`loadtest/k6/script.js` drives an auth + photo-CRUD mix (40 % cached read,
25 % list, 15 % upload, 12 % patch, 8 % thumbnail-status) through k6 in Docker.
Its k6 `thresholds` **are** the SLO in [`docs/perf_slo.md`](docs/perf_slo.md), so
`./loadtest/run.sh` exits non-zero on a regression.

```bash
docker compose up -d && ./loadtest/run.sh           # 50 VUs, SLO enforced
PROM_RW=1 ./loadtest/run.sh                          # + live in Grafana's "Load test (k6)" row
VUS=200 SLEEP_MAX=0.1 ./loadtest/run.sh              # saturation test
```

`loadtest.yml` runs a light **smoke** load (correctness only — CI runners are
~2 vCPU) nightly and on PRs; the real SLO numbers are measured on a real box and
committed to `loadtest/results/summary.html`.

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
| `POST`   | `/photos/{id}/flag`           | 201     | 400, 401, 404, 409, 422     |
| `GET`    | `/moderation/queue`           | 200     | 401, 403, 422               |
| `POST`   | `/moderation/{flag_id}/decision` | 200  | 400, 401, 403, 404, 409, 422 |
| `GET`    | `/healthz` · `/readyz`        | 200     | `/readyz` → 503 when degraded |
| `GET`    | `/metrics`                    | 200     | —                           |

All photo routes also return `405` (with a correct `Allow` header) for
unsupported methods.

## Results — real numbers

Measured on this machine (Windows + WSL2, Docker Desktop, 12 vCPU / 15 GB).

| Metric                                    | Value                                              |
| ----------------------------------------- | -------------------------------------------------- |
| Tests                                     | 112 unit/integration (`pytest`) + 8 pytest-docker (real PG/Redis) |
| Line + branch coverage                    | **100.0%** (`coverage`, branch on; CI gate 90%)    |
| Lint                                      | flake8 clean (`app` + `tests` + `scripts` + `integration_tests`) |
| Contract test                             | Schemathesis: **0 failures** across 16 operations, ~1050 generated cases (CI) |
| Smoke suite                               | Newman: **35/35 assertions**, 24 requests          |
| CI                                        | 6 workflows green — lint-test, contract-test, postman-smoke, integration-test, loadtest, sdk-gen |
| **Load test @ reference load** (50 VUs, ~135 req/s) | **p95 269 ms**, error rate **0.00 %**, checks 100 % — [report](loadtest/results/summary.html) |
| Load test — cached read / list / upload p95 | 213 ms / 240 ms / 348 ms                          |
| Load test — saturation (200 VUs)          | ~207 req/s ceiling, p95 1.3 s, 0 % errors          |
| **Canary** (50 VUs through Traefik split) | canary got **9.9986 %** of 35.5 k reqs, **0** × 5xx, p95 Δ ≈ −2 ms vs stable — [report](docs/canary-report.md) |
| Thumbnail latency (320×240 PNG, local)    | source→`ready` in ~1–2 s end to end                |
| `GET /photos/{id}` cache hit, 1 client    | p50 ≈ 3.1 ms, p90 ≈ 3.9 ms (n=500)                 |

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

### What the load test found (Phase 2)

The first k6 run (200 VUs) topped out at **88 req/s** with p95 **1.4 s** and
0.32 % errors, while `api` sat pinned at 2 CPU cores and 10 host cores idle.
Findings + fixes (full write-up: [ADR 0001](docs/adr/0001-load-test-tuning.md)):

| Finding | Fix | Effect |
| --- | --- | --- |
| `WEB_CONCURRENCY=2` — API pinned at 2 cores | → 6 uvicorn workers | throughput 88 → **207 req/s** (+135 %) |
| `POST /photos` was `async def` but did blocking Pillow + DB work on the event loop | → sync `def` (runs in threadpool) | uploads no longer stall other requests on the worker |
| Captioned upload did 2 transactions | set caption in the initial INSERT | 1 commit per upload |
| Pool `10+20`/worker × 6 would exceed PG's 100 conns | pool `5+5` (api) / `2+4` (celery); PG `max_connections=200` | no connection exhaustion |
| `PHOTO_CACHE_TTL_SECONDS=60` | → 300 (writes invalidate explicitly) | higher hit rate under load |

After tuning, the identical 200 VU test: **207 req/s, 0 errors, 0 interrupted
iterations**. At the reference load the stack meets every SLO threshold.

### What broke while building Phases 3–4

- **SQLite silently ignored `ON DELETE CASCADE`** in tests — it needs
  `PRAGMA foreign_keys=ON` per connection. The `action`-decision test only
  passed once a `connect` event listener set it, which also made the whole
  suite's referential behaviour match Postgres.
- **Schemathesis re-found the Phase 1 gap** on the two new POST routes:
  malformed JSON body → `400` (Starlette) was undocumented. Added the shared
  `JSON_BODY` responses fragment.
- **`pytest-docker` can't live under `tests/`** — that package's `conftest.py`
  pins env + imports `app` at module load. Integration tests are a separate
  top-level `integration_tests/` package with lazy `app` imports.
- **Canary latency numbers are bucket-interpolated.** Traefik's default
  duration histogram buckets are `0.1 / 0.3 / 1.2 / 5.0 s`, so per-backend
  quantiles from Prometheus are coarse; k6's client-side p95 is the exact
  figure. The canary's *distribution* comparison (≥ 98 % of requests < 100 ms
  on both) is the real signal.

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
- [x] **Phase 2** — k6 load test + `loadtest.yml`, documented SLO, tuning ADR (88 → 207 req/s), committed HTML report, live k6 panels in Grafana
- [x] **Phase 3** — photo flag & moderation feature built test-first, RBAC, OpenAPI `v1.1.0` diff (oasdiff, non-breaking), `pytest-docker` integration suite + `integration-test.yml`
- [x] **Phase 4** — moderation-decision notifications (outbox + Celery), Traefik 90/10 canary + report, tagged `v1.1.0`, generated Python SDK + `sdk-gen.yml`

## Repository layout

```
app/
  api/            routers (auth, photos, moderation, health) + deps + responses + middleware
  core/           security (bcrypt, JWT)
  models/         SQLAlchemy 2.0 typed models (User/Photo/Thumbnail/Flag/ModerationAction/Notification)
  schemas/        Pydantic request/response models (incl. ErrorResponse)
  services/       photo + image + moderation + notification domain logic (no framework coupling)
  workers/        Celery app + thumbnail task + notification-delivery task
  alembic/        migrations (0001 initial, 0002 moderation, 0003 notifications)
  cache.py        Redis cache-aside helper (degrades gracefully)
  storage.py      local blob storage (shared volume)
deploy/traefik/   canary reverse-proxy config (static + weighted dynamic)
observability/    prometheus.yml + Grafana provisioning + RED / Canary dashboard JSON
openapi/          committed OpenAPI 3.1 spec (stable + v1.0.0 + v1.1.0)
postman/          smoke collection, spec-generated collection, environment, fixtures
loadtest/         k6 script + thresholds (== SLO), run.sh, committed results/
integration_tests/  pytest-docker suite — real Postgres + Redis
sdk/              generated typed Python client (openapi-python-client)
docs/             feature design, perf_slo.md, openapi diff, canary report, adr/
tests/            pytest suite (unit + integration), 100% covered
scripts/          smoke.sh (e2e), export_openapi.py (spec + drift check)
```

## Author

Mitul Goel — [github.com/Mitulol](https://github.com/Mitulol) ·
[linkedin.com/in/mitul-goel](https://linkedin.com/in/mitul-goel)

## License

MIT — see [LICENSE](LICENSE).
