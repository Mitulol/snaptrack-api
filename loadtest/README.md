# Load testing

k6 (in Docker) driving auth + photo-CRUD traffic against the Compose stack.

## Run it

```bash
docker compose up -d              # stack must be healthy first
./loadtest/run.sh                 # 50 VUs, ~90s; SLO thresholds enforced
```

The exit code is k6's: **non-zero if any SLO threshold in
`docs/perf_slo.md` is breached**. Outputs land in `loadtest/results/`:

- `summary.html` — human-readable report (committed as the last-run snapshot)
- `summary.json` — raw metrics

## Knobs (env vars)

| Var | Default | Meaning |
| --- | --- | --- |
| `VUS` | 50 | peak virtual users (ramp 20s → hold 60s → 10s down) |
| `SLEEP_MAX` | 0.6 | max think time between iterations (s); lower = heavier |
| `USER_POOL` | 40 | users registered in `setup()`, one seeded photo each |
| `PROM_RW` | 0 | `1` → stream metrics to Prometheus for the Grafana **Load test (k6)** panels |
| `NETWORK` | `snaptrack_default` | Compose network to join |

```bash
VUS=200 SLEEP_MAX=0.1 ./loadtest/run.sh     # saturation test
PROM_RW=1 ./loadtest/run.sh                 # watch it live in Grafana (:3000)
```

## Live in Grafana

With `PROM_RW=1`, open the **SnapTrack API — RED** dashboard → *Load test (k6)*
row: client-observed p90/p95/p99, offered load vs throughput, and p95 per
operation. Prometheus keeps k6 series for its retention window (6h).

## What's here

```
k6/script.js        scenario + thresholds (== the SLO)
k6/vendor/          pinned copies of k6-summary + k6-reporter (no runtime fetch)
run.sh              docker wrapper (network, volumes, prom-rw wiring)
results/            committed HTML + JSON from the last real run
```

