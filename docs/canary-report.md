# Canary report — v1.1.0 candidate

- **Date:** 2026-09-07
- **Change under release:** Phase 3 (photo flagging + moderation, three new
  endpoints, new `flags` / `moderation_actions` tables) and Phase 4
  (moderation-decision notifications: new `notifications` table + Celery
  delivery task). All additive — `oasdiff` reports no breaking changes vs
  `v1.0.0`.
- **Verdict:** :white_check_mark: **promote.** Exact 90/10 split, zero 5xx on
  either backend, canary latency statistically indistinguishable from stable.

## Setup

`docker compose --profile canary up -d --build` adds two services to the normal
stack:

| Service | Role | Traffic |
| --- | --- | --- |
| `api` | stable | 90 % |
| `api-next` | canary (`RELEASE_CHANNEL=next`) | 10 % |

Traefik v3 (`deploy/traefik/`) fronts both on `:8080` with a **weighted**
load-balancer service (`deploy/traefik/dynamic.yml`); the weights reload live.
Both API containers share the same Postgres, Redis and photo volume — this is a
code/rollout canary on one data plane, not a data migration test. Traefik
publishes Prometheus metrics (`traefik_service_*`, labelled
`service="snaptrack-stable@file"` / `"snaptrack-next@file"`), scraped into the
same Prometheus and compared on the **`SnapTrack API — Canary`** Grafana
dashboard.

> **Honest scope:** `api` and `api-next` are built from the *same commit* (this
> v1.1.0 candidate). The canary therefore validates (a) the weighted-routing
> mechanism, (b) that the additive endpoints + two new migrations do not
> regress the existing hot-path endpoints under real split traffic, and (c) the
> per-backend observability needed to make a go/no-go call. It is **not** an A/B
> of two different application versions.

## Load

`BASE_URL=http://traefik:80 PROM_RW=1 VUS=50 HOLD=120s SLEEP_MAX=0.3 ./loadtest/run.sh`
— the standard Phase 2 auth + photo-CRUD mix, driven through the Traefik split
instead of straight at `api`. k6 client-side summary
([`docs/canary/k6-through-traefik.html`](canary/k6-through-traefik.html)):

| Metric | Value |
| --- | --- |
| Requests | 35 491 (207.4 req/s) |
| Failed | **0.00 %** (0 / 35 491) |
| Checks | **100 %** (35 371 / 35 371) |
| `http_req_duration` p95 / p99 | **81.6 ms** / 403 ms (max) |
| Interrupted iterations | 0 |

## Stable vs. canary (Traefik metrics, full run)

| | `snaptrack-stable` | `snaptrack-next` |
| --- | --- | --- |
| Requests served | 31 982 | 3 553 |
| Share of traffic | 90.00 % | **9.9986 %** (target 10 %) |
| 5xx | **0** | **0** |
| non-2xx | 1× `404`¹ | 0 |
| p50 (bucketed²) | 51.2 ms | 50.2 ms |
| p95 (bucketed²) | 97.2 ms | 95.5 ms |
| requests ≤ 100 ms | 97.7 % | 99.5 % |
| mean latency | 36.9 ms | 21.6 ms³ |

¹ One `GET /photos/{id}` that raced a concurrent `DELETE` in the k6 script —
landed on the stable backend, unrelated to the release.
² Traefik's default duration histogram buckets are coarse (`0.1 / 0.3 / 1.2 /
5.0 s`), so these quantiles are bucket-interpolated. The precise latency figure
is k6's client-side p95 (81.6 ms). The bucket *distribution* is the useful
signal here: 99.5 % of canary requests and 97.7 % of stable requests completed
in under 100 ms — no divergence.
³ The canary's mean looks lower, but it served **1/9th** the volume; with
~3.5 k samples its tail is under-observed. Same code, no real latency delta.

## Decision

All three promotion gates pass:

1. **Split is correct** — 9.9986 % vs a 10 % weight over 35 k requests.
2. **No new errors** — 0 × 5xx on the canary (and on stable).
3. **No latency regression** — canary p50/p95 within ~2 ms of stable; both
   ~98 %+ of requests under 100 ms.

→ **Promote.** Cut over: set `snaptrack-next` weight to 100 in
`dynamic.yml` (live, no restart) for a full drain test, then retag the release
and point compose `api` at it. Tagged **`v1.1.0`**.

## Rollback

If a gate had failed: set `snaptrack-next` weight to `0` in
`deploy/traefik/dynamic.yml` (Traefik reloads within ~1 s, `watch: true`), or
`docker compose --profile canary stop api-next`. No stable restart, no data
change — the additive migrations are backward-compatible with the stable image.
