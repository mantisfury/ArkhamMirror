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
    MIGRATION_COMPLETE=$(psql "$DATABASE_URL" -tAc "SELECT 1 FROM pg_proc WHERE proname = 'cleanup_stale_workers' AND pronamespace = 'arkham_jobs'::regnamespace" 2>/dev/null || echo "0")

    if [ "$MIGRATION_COMPLETE" != "1" ]; then
        echo "  Running database migrations..."
        if [ -f "/app/migrations/001_consolidation.sql" ]; then
            psql "$DATABASE_URL" -f /app/migrations/001_consolidation.sql 2>&1 | grep -E "^(NOTICE|ERROR)" || true
            echo "  Database migrations complete."
        else
            echo "  Warning: Migration file not found, skipping..."
        fi
    else
        echo "  Database already initialized."
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
