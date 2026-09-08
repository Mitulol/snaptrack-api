#!/usr/bin/env bash
# Run the k6 load test (via Docker) against the running Compose stack.
#
#   ./loadtest/run.sh                 # 50 VUs, ~90s; HTML + JSON report in loadtest/results/
#   VUS=100 ./loadtest/run.sh         # override VU count
#   PROM_RW=1 ./loadtest/run.sh       # also stream metrics to Prometheus (for the Grafana panel)
#   BASE_URL=http://traefik:80 ./loadtest/run.sh   # drive traffic through the canary split
#
# Requires `docker compose up -d` first (the api service must be healthy).
set -euo pipefail

cd "$(dirname "$0")/.."

NETWORK="${NETWORK:-snaptrack_default}"
BASE_URL="${BASE_URL:-http://api:8000}"
VUS="${VUS:-50}"
USER_POOL="${USER_POOL:-40}"

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "network '$NETWORK' not found — run 'docker compose up -d' first" >&2
  exit 1
fi

mkdir -p loadtest/results

docker_args=(
  --rm
  --network "$NETWORK"
  --user "$(id -u):$(id -g)"
  -e "BASE_URL=$BASE_URL"
  -e "VUS=$VUS"
  -e "USER_POOL=$USER_POOL"
  -e "SLEEP_MAX=${SLEEP_MAX:-0.6}"
  -e "HOLD=${HOLD:-60s}"
  -e "SMOKE=${SMOKE:-0}"
  -e RESULTS_DIR=/work/loadtest/results
  -v "$PWD:/work"
  -w /work
)

k6_args=(run)
if [[ "${PROM_RW:-0}" == "1" ]]; then
  k6_args+=(-o experimental-prometheus-rw)
  docker_args+=(
    -e K6_PROMETHEUS_RW_SERVER_URL=http://prometheus:9090/api/v1/write
    -e 'K6_PROMETHEUS_RW_TREND_STATS=p(90),p(95),p(99),avg,max'
  )
fi
k6_args+=(/work/loadtest/k6/script.js)

echo "k6: $VUS VUs -> $BASE_URL on $NETWORK  (prom-rw=${PROM_RW:-0})"
exec docker run "${docker_args[@]}" grafana/k6 "${k6_args[@]}"
