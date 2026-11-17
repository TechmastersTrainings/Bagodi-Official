#!/bin/sh
set -e

echo "Running database migrations with Alembic..."
alembic upgrade head || {
    echo "Warning: Alembic upgrade encountered an issue or database already up-to-date."
}

echo "Starting Uvicorn ASGI production server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
