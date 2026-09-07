# SnapTrack API

[![lint-test](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml/badge.svg)](https://github.com/Mitulol/snaptrack-api/actions/workflows/lint-test.yml)

A photo-tracking HTTP API: users upload photos, SnapTrack stores per-photo
metadata, derives thumbnails on a background worker, and serves hot metadata
reads from a Redis cache-aside layer. Built with FastAPI + SQLAlchemy +
Celery, and packaged as a self-contained Docker Compose stack (API, Postgres,
Redis, worker) that runs entirely on a laptop.

This repository is developed in phases; later phases add observability, load
testing, a moderation feature built test-first, and a canary release. See
[Roadmap](#roadmap) for status.

```
                       ┌───────────────┐        enqueue job         ┌────────────┐
   client ──HTTP──▶     │  FastAPI (api) │ ──────────────────────▶    │   Redis    │
                       │               │ ◀───── cache get/set ─────  │ (broker +  │
                       │  JWT auth     │                             │  cache +   │
                       │  ownership    │ ──── read/write ────┐       │  results)  │
                       └───────────────┘                     │       └─────┬──────┘
                              │                              ▼             │ pull job
                              │                        ┌───────────┐       ▼
                              └──── SELECT/INSERT ────▶ │ Postgres  │  ┌──────────────┐
                                                       │ (metadata)│  │ Celery worker│
                                                       └───────────┘  │  Pillow      │
                                        shared volume (originals + thumbs) ──┘  writes
                                                                        thumb + status
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
| Metrics            | `prometheus-fastapi-instrumentator` at `/metrics` (Phase 1+)  |
| Packaging          | Docker Compose; single image runs both `api` and `worker`     |
| CI                 | GitHub Actions — flake8 + pytest against real Postgres/Redis  |

## Running it locally

Requires Docker + Docker Compose. No cloud services.

```bash
docker compose up -d --build         # api on http://localhost:8000
curl -s localhost:8000/readyz | jq   # {"status":"ok","checks":{...}}
open http://localhost:8000/docs      # interactive OpenAPI docs

./scripts/smoke.sh                   # end-to-end: register→upload→thumbnail→cache→delete
docker compose down -v               # stop and wipe volumes
```

Internal services (Postgres, Redis) are not published to host ports to avoid
collisions with other local stacks; use `docker compose exec postgres psql -U
snaptrack` for a shell.

### Local dev without Docker

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # point DATABASE_URL/REDIS_URL at your services
pytest                               # 62 tests, ~18s on SQLite + fakeredis
flake8 app tests
```

## API surface (Phase 0)

| Method   | Path                          | Notes                                         |
| -------- | ----------------------------- | --------------------------------------------- |
| `POST`   | `/auth/register`              | 201; 409 on duplicate email                   |
| `POST`   | `/auth/login`                 | returns a bearer token                        |
| `GET`    | `/auth/me`                    | current user                                  |
| `POST`   | `/photos`                     | multipart upload; enqueues a thumbnail job    |
| `GET`    | `/photos`                     | caller's photos, `limit`/`offset` paginated   |
| `GET`    | `/photos/{id}`                | cache-aside read                              |
| `PATCH`  | `/photos/{id}`                | update caption (owner only); invalidates cache|
| `DELETE` | `/photos/{id}`                | owner only; deletes blobs + cache key         |
| `GET`    | `/photos/{id}/thumbnail`      | thumbnail status (`pending`/`ready`/`failed`) |
| `GET`    | `/photos/{id}/thumbnail/file` | thumbnail bytes; 409 until `ready`            |
| `GET`    | `/photos/{id}/file`           | original bytes                                |
| `GET`    | `/healthz` · `/readyz`        | liveness · readiness (DB + Redis)             |
| `GET`    | `/metrics`                    | Prometheus exposition                         |

## Results — real numbers

Measured on this machine (Windows + WSL2, Docker Desktop). These are **honest
Phase 0 numbers**; load-tested p95 under concurrency lands in Phase 2.

| Metric                                    | Value                                   |
| ----------------------------------------- | --------------------------------------- |
| Tests                                     | 62 passing (`pytest`)                   |
| Line + branch coverage                    | **100.0%** (`coverage`, gate at 90% in CI) |
| Lint                                      | flake8 clean (`app` + `tests`)          |
| CI                                        | flake8 job + pytest job vs. Postgres 16 + Redis 7 service containers |
| Thumbnail latency (320×240 PNG, local)    | source→`ready` in ~1–2 s end to end     |
| `GET /photos/{id}` cache hit, 1 client    | p50 ≈ 3.1 ms, p90 ≈ 3.9 ms (n=500, localhost) |
| `GET /photos` list (DB), 1 client         | p50 ≈ 5.7 ms, p90 ≈ 7.8 ms (n=500, localhost) |
| `GET /healthz`, 1 client                  | p50 ≈ 1.9 ms, p90 ≈ 3.0 ms (n=500, localhost) |

Single-client latencies are a baseline, not a load result — they say nothing
about throughput or tail latency under concurrency. Phase 2 replaces them with
k6 numbers and a documented SLO.

### What broke while building Phase 0

- **`passlib[bcrypt]` import error.** passlib's bcrypt backend reads
  `bcrypt.__about__`, removed in bcrypt ≥ 4.1, and logs a spurious error.
  Dropped passlib; `app/core/security.py` calls `bcrypt` directly.
- **Alembic + in-memory SQLite in tests.** `engine_from_config` in `env.py`
  builds its own `NullPool` engine, so migrations ran against a throwaway
  connection and the tables vanished. Tests use `Base.metadata.create_all` on
  SQLite and run the real migration only against Postgres (CI).
- **Host port 5432 already in use** by another local stack. Compose no longer
  publishes Postgres/Redis to the host — only the API's 8000.

## Roadmap

- [x] **Phase 0** — CRUD + JWT + async thumbnails + Redis cache + Compose + CI
- [ ] **Phase 1** — Prometheus + Grafana (RED), versioned OpenAPI, Schemathesis contract tests, Postman smoke suite
- [ ] **Phase 2** — k6 load test, documented SLO, tuning ADR, committed HTML report
- [ ] **Phase 3** — photo flag & moderation feature, built test-first, with RBAC
- [ ] **Phase 4** — moderation-notify task, Traefik canary release, `v1.1.0` tag, generated Python SDK

## Repository layout

```
app/
  api/            routers (auth, photos, health) + FastAPI dependencies
  core/           security (bcrypt, JWT)
  models/         SQLAlchemy 2.0 typed models
  schemas/        Pydantic request/response models
  services/       photo + image domain logic (no framework coupling)
  workers/        Celery app + thumbnail task
  alembic/        migrations
  cache.py        Redis cache-aside helper (degrades gracefully)
  storage.py      local blob storage (shared volume)
tests/            pytest suite (unit + integration), 100% covered
docker/           container entrypoint
scripts/smoke.sh  end-to-end check against a running stack
```

## Author

Mitul Goel — [github.com/Mitulol](https://github.com/Mitulol) ·
[linkedin.com/in/mitul-goel](https://linkedin.com/in/mitul-goel)

## License

MIT — see [LICENSE](LICENSE).
