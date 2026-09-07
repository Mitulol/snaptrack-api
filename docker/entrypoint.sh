#!/usr/bin/env bash
# Container entrypoint. Dispatches on the first argument:
#   api     -> run DB migrations, then serve the API with uvicorn
#   worker  -> start the Celery thumbnail worker
#   <other> -> exec it verbatim (useful for `docker compose run api pytest`)
set -euo pipefail

case "${1:-api}" in
  api)
    echo "[entrypoint] running alembic migrations..."
    alembic upgrade head
    echo "[entrypoint] starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}"
    ;;
  worker)
    exec celery -A app.workers.celery_app.celery_app worker \
      --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  *)
    exec "$@"
    ;;
esac
