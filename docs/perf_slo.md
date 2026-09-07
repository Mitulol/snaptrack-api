# SnapTrack — Performance SLO

Scope: the synchronous HTTP API (`api` service). Thumbnail generation is async
and tracked separately (job success rate + queue age), not here.

## Reference environment

| | |
| --- | --- |
| Host | 1 node, 12 vCPU / 15 GB, Windows 11 + WSL2, Docker Desktop |
| Stack | `docker compose up` — `api` (6 uvicorn workers), 1 Celery worker (4 procs), Postgres 16, Redis 7 |
| Load generator | k6 in Docker on the same host (`loadtest/k6/script.js`) |
| Reference load | 50 VUs, ~0.3 s think time between requests → **~125–145 req/s** offered |
| Traffic mix | 40 % cached read · 25 % list · 15 % upload · 12 % patch · 8 % thumbnail-status |

This is a single-box target. It is deliberately **not** the curriculum's
"500 req/s" number — see [Beyond one node](#beyond-one-node).

## The SLO

Measured at the reference load, over a 90 s steady-state window:

| Objective | Target | Last measured ([report](../loadtest/results/summary.html)) |
| --- | --- | --- |
| Error rate (`http_req_failed`) | **< 0.1 %** | **0.00 %** (0 / 14 217) |
| Checks passing | > 99 % | 100 % |
| Overall request latency `p95` | **≤ 400 ms** | **269 ms** |
| Cached read `GET /photos/{id}` `p95` | ≤ 250 ms | 213 ms |
| List `GET /photos` `p95` | ≤ 300 ms | 240 ms |
| Upload `POST /photos` `p95` | ≤ 600 ms | 348 ms |
| Sustained throughput | ≥ 120 req/s | 135 req/s |
| `/readyz` | 200 throughout | ok |

These targets are encoded as k6 `thresholds` in `loadtest/k6/script.js`, so
`./loadtest/run.sh` exits non-zero if the SLO regresses.

## Capacity envelope (measured)

| Offered load | Throughput | `p95` | Errors | Notes |
| --- | --- | --- | --- | --- |
| 50 VUs / 0.3 s think | 135–143 req/s | ~245–270 ms | 0 % | reference load, SLO passes |
| 60 VUs / 0.3 s think | 156 req/s | 312 ms | 0 % | still under SLO |
| 200 VUs / 0.1 s think | 207 req/s | 1.3 s | 0 % | **saturated** — throughput ceiling, latency ~5× over SLO |

The knee is around 60–80 concurrent users / ~160 req/s. Past that, `api` CPU
saturates (~6 cores) and latency climbs while throughput stays flat — add
capacity rather than pushing a single node harder.

## Error budget

0.1 % over 30 days ≈ **43 minutes** of full downtime, or ~1 in 1000 requests
failing. Consumed by: unhandled 5xx, `/readyz` failing (dependency down),
or `p95` breaching for a sustained window. The Grafana **RED** dashboard
("Errors" row) is the burn-rate view.

## Beyond one node

The API is stateless (JWT auth, all state in Postgres/Redis/the shared blob
volume), so the path to higher throughput is horizontal: run N `api` replicas
behind a load balancer. Phase 4 introduces Traefik in front of `api` for the
canary release; the same routing fans out to replicas. Expected next
bottleneck after ~3–4 replicas is Postgres connections / write throughput,
addressed with PgBouncer and read replicas — out of scope for this project.
