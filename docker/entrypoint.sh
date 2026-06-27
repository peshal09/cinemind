#!/usr/bin/env bash
set -e

# depends_on: service_healthy gates us until Postgres/Redis are up, but seeding
# is idempotent so this is safe to run on every container start.
echo "[entrypoint] seeding database (idempotent)..."
python -m app.db.seed

echo "[entrypoint] starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
