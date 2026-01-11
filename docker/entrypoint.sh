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
