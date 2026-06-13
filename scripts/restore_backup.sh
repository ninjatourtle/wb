#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /backups/tenderflow-YYYYMMDD-HHMMSS.dump"
  exit 1
fi

PGPASSWORD="${POSTGRES_PASSWORD:?}" pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --host="${POSTGRES_HOST:-db}" \
  --username="${POSTGRES_USER:-tenderflow}" \
  --dbname="${POSTGRES_DB:-tenderflow}" \
  "$1"
