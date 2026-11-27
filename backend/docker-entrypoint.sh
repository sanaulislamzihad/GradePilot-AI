#!/bin/sh
# Entry point for the backend image: `migrate`, `api`, `worker`, or any other command.
set -e

case "$1" in
  migrate)
    exec alembic upgrade head
    ;;
  api)
    # The API is only reachable through the web proxy, which overwrites
    # X-Forwarded-For with the real client address, so the header can be trusted.
    exec uvicorn app.main:app \
      --host 0.0.0.0 --port 8000 \
      --workers "${API_WORKERS:-2}" \
      --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" \
      --no-server-header
    ;;
  worker)
    exec celery -A app.tasks.celery_app worker \
      --loglevel=info --concurrency "${WORKER_CONCURRENCY:-2}"
    ;;
  *)
    exec "$@"
    ;;
esac
