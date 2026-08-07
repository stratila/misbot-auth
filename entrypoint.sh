#!/usr/bin/env sh
set -e

echo "[misbot-auth entrypoint.sh] EXECUTE_MIGRATIONS=${EXECUTE_MIGRATIONS:-false}"

if [ "${EXECUTE_MIGRATIONS:-false}" = "true" ]; then
    echo "[misbot-auth entrypoint.sh] Performing database migrations"
    # No `|| true` here on purpose: alembic exits non-zero on a failed
    # migration and `set -e` turns that into a container that refuses to
    # start, rather than one serving a half-migrated schema.
    /opt/venv/bin/alembic -c /app/alembic.ini upgrade head
fi

if [ "$#" -eq 0 ]; then
    echo "[misbot-auth entrypoint.sh] No command specified"
    exit 1
fi

exec "$@"
