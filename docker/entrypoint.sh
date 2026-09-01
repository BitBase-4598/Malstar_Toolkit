#!/bin/sh
set -e
mkdir -p "${UPLOAD_DIR:-/home/data/uploads}"
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 1 \
  --threads 8 \
  --timeout 900 \
  --access-logfile - \
  --error-logfile - \
  app:app
