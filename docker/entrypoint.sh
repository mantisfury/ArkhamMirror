#!/bin/bash
# =============================================================================
# SHATTERED KANDOR Entrypoint
# Waits for services and starts the application
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
# Wait for Qdrant (optional)
# -----------------------------------------------------------------------------
if [ -n "$QDRANT_URL" ]; then
    echo "Waiting for Qdrant..."

    # Extract host from QDRANT_URL
    QDRANT_HOST=$(echo $QDRANT_URL | sed -E 's|https?://([^:/]+).*|\1|')
    QDRANT_PORT=$(echo $QDRANT_URL | sed -E 's|.*:([0-9]+).*|\1|')
    QDRANT_PORT=${QDRANT_PORT:-6333}

    for i in {1..30}; do
        if curl -sf "http://$QDRANT_HOST:$QDRANT_PORT/healthz" > /dev/null 2>&1; then
            echo "Qdrant is ready!"
            break
        fi
        echo "Waiting for Qdrant ($i/30)..."
        sleep 1
    done
fi

# -----------------------------------------------------------------------------
# Wait for Redis (optional)
# -----------------------------------------------------------------------------
if [ -n "$REDIS_URL" ]; then
    echo "Waiting for Redis..."

    # Extract host and port from REDIS_URL
    # Format: redis://host:port
    REDIS_HOST=$(echo $REDIS_URL | sed -E 's|redis://([^:/]+).*|\1|')
    REDIS_PORT=$(echo $REDIS_URL | sed -E 's|.*:([0-9]+).*|\1|')
    REDIS_PORT=${REDIS_PORT:-6379}

    for i in {1..30}; do
        if nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
            echo "Redis is ready!"
            break
        fi
        echo "Waiting for Redis ($i/30)..."
        sleep 1
    done
fi

# -----------------------------------------------------------------------------
# Display configuration
# -----------------------------------------------------------------------------
echo ""
echo "Configuration:"
echo "  DATABASE_URL: ${DATABASE_URL:+[configured]}"
echo "  QDRANT_URL: ${QDRANT_URL:-[not set]}"
echo "  REDIS_URL: ${REDIS_URL:-[not set]}"
echo "  LLM_ENDPOINT: ${LLM_ENDPOINT:-${LM_STUDIO_URL:-[not set]}}"
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
