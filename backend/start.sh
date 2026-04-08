#!/bin/sh
set -e

echo "Starting application..."

# Run pending Alembic migrations BEFORE the API comes up.
# Without this, a deploy that ships a migration leaves the schema
# stale and the app's queries fail with UndefinedColumnError until
# someone runs alembic manually. Lesson learned 2026-04-08:
# silent-channel-health migration shipped without this step and
# the Empresas page returned 500 to all users for several minutes.
echo "Running alembic upgrade head..."
alembic upgrade head

echo "Starting uvicorn..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
