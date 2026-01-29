#!/bin/bash
# =============================================================================
# SHATTERED KANDOR Entrypoint
# Waits for PostgreSQL and starts the application
# =============================================================================

set -e

echo "=============================================="
echo "  SHATTERED KANDOR - Starting Up"
echo "=============================================="

# -----------------------------------------------------------------------------
# Wait for PostgreSQL
# -----------------------------------------------------------------------------
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL..."

    # Extract host and port from DATABASE_URL
    # Format: postgresql://user:pass@host:port/db
    DB_HOST=$(echo $DATABASE_URL | sed -E 's/.*@([^:]+):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed -E 's/.*:([0-9]+)\/.*/\1/')

    # Default port if not specified
    DB_PORT=${DB_PORT:-5432}

    # Wait up to 60 seconds for PostgreSQL
    for i in {1..60}; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            break
        fi
        echo "Waiting for PostgreSQL ($i/60)..."
        sleep 1
    done

    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
        echo "Warning: PostgreSQL not ready after 60 seconds, continuing anyway..."
    fi

    # -------------------------------------------------------------------------
    # Run database migrations (idempotent - safe to run multiple times)
    # -------------------------------------------------------------------------
    echo "Running database migrations..."

    # Check if cleanup_stale_workers function exists (a reliable indicator that
    # the full 001_consolidation.sql migration has run, not just partial schemas)
    MIGRATION_001=$(psql "$DATABASE_URL" -tAc "SELECT 1 FROM pg_proc WHERE proname = 'cleanup_stale_workers' AND pronamespace = 'arkham_jobs'::regnamespace" 2>/dev/null || echo "0")

    if [ "$MIGRATION_001" != "1" ]; then
        echo "  Running migration 001..."
        if [ -f "/app/migrations/001_consolidation.sql" ]; then
            psql "$DATABASE_URL" -f /app/migrations/001_consolidation.sql 2>&1 | grep -E "^(NOTICE|ERROR)" || true
            echo "  Migration 001 complete."
        else
            echo "  Warning: 001_consolidation.sql not found, skipping..."
        fi
    fi

    # Run 002 (worker requeue safety) if worker_requeue_count column is missing
    WORKER_REQUEUE_COL=$(psql "$DATABASE_URL" -tAc "SELECT 1 FROM information_schema.columns WHERE table_schema = 'arkham_jobs' AND table_name = 'jobs' AND column_name = 'worker_requeue_count'" 2>/dev/null || echo "0")
    if [ "$WORKER_REQUEUE_COL" != "1" ]; then
        echo "  Running migration 002 (worker requeue safety)..."
        if [ -f "/app/migrations/002_worker_requeue_safety.sql" ]; then
            psql "$DATABASE_URL" -f /app/migrations/002_worker_requeue_safety.sql 2>&1 | grep -E "^(NOTICE|ERROR)" || true
            echo "  Migration 002 complete."
        else
            echo "  Warning: 002_worker_requeue_safety.sql not found, skipping..."
        fi
    fi

    if [ "$MIGRATION_001" = "1" ] && [ "$WORKER_REQUEUE_COL" = "1" ]; then
        echo "  Database migrations up to date."
    fi
fi

# -----------------------------------------------------------------------------
# Display configuration
# -----------------------------------------------------------------------------
echo ""
echo "Configuration:"
echo "  DATABASE_URL: ${DATABASE_URL:+[configured]}"
echo "  LLM_ENDPOINT: ${LLM_ENDPOINT:-${LM_STUDIO_URL:-[not set]}}"
echo "  EMBED_MODEL: ${EMBED_MODEL:-[not set - semantic search disabled]}"
echo "  ARKHAM_SERVE_SHELL: ${ARKHAM_SERVE_SHELL:-false}"
echo ""

# -----------------------------------------------------------------------------
# Start the application
# -----------------------------------------------------------------------------
echo "Starting ArkhamFrame..."
echo ""

exec python -m uvicorn arkham_frame.main:app \
    --host 0.0.0.0 \
    --port 8100 \
    --log-level info
