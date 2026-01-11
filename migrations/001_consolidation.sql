-- =============================================================================
-- SHATTERED: PostgreSQL Consolidation Migration
-- Replaces Redis (job queue) and Qdrant (vectors) with PostgreSQL + pgvector
--
-- Run with: psql -U arkham -d arkhamdb -f migrations/001_consolidation.sql
-- =============================================================================

-- ============================================
-- STEP 1: Enable Extensions
-- ============================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search optimization

-- ============================================
-- STEP 2: Create Schemas
-- ============================================

CREATE SCHEMA IF NOT EXISTS arkham_vectors;
CREATE SCHEMA IF NOT EXISTS arkham_jobs;

-- ============================================
-- STEP 3: Vector Storage (replaces Qdrant)
-- ============================================

-- Collection metadata with IVFFlat parameters
CREATE TABLE IF NOT EXISTS arkham_vectors.collections (
    name VARCHAR(100) PRIMARY KEY,
    vector_size INTEGER NOT NULL,
    distance_metric VARCHAR(20) NOT NULL DEFAULT 'cosine',
    index_type VARCHAR(20) NOT NULL DEFAULT 'ivfflat',
    lists INTEGER NOT NULL DEFAULT 100,
    probes INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_reindex TIMESTAMP,
    vector_count INTEGER DEFAULT 0,
    CONSTRAINT valid_metric CHECK (distance_metric IN ('cosine', 'euclidean', 'dot')),
    CONSTRAINT valid_index CHECK (index_type IN ('ivfflat', 'hnsw', 'none'))
);

-- Main embeddings table
CREATE TABLE IF NOT EXISTS arkham_vectors.embeddings (
    id VARCHAR(36) PRIMARY KEY,
    collection VARCHAR(100) NOT NULL,
    embedding vector(2000),  -- Max pgvector dimension with index
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Basic indexes for embeddings
CREATE INDEX IF NOT EXISTS idx_embeddings_collection
    ON arkham_vectors.embeddings(collection);
CREATE INDEX IF NOT EXISTS idx_embeddings_payload
    ON arkham_vectors.embeddings USING gin (payload jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_embeddings_created
    ON arkham_vectors.embeddings(collection, created_at);

-- Update timestamp trigger for embeddings
CREATE OR REPLACE FUNCTION arkham_vectors.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_embeddings_updated ON arkham_vectors.embeddings;
CREATE TRIGGER trg_embeddings_updated
    BEFORE UPDATE ON arkham_vectors.embeddings
    FOR EACH ROW
    EXECUTE FUNCTION arkham_vectors.update_timestamp();

-- Helper function: Calculate optimal IVFFlat lists parameter
CREATE OR REPLACE FUNCTION arkham_vectors.optimal_lists(row_count BIGINT)
RETURNS INTEGER AS $$
BEGIN
    IF row_count < 1000 THEN
        RETURN 10;
    ELSIF row_count < 1000000 THEN
        RETURN GREATEST(10, (row_count / 1000)::INTEGER);
    ELSE
        RETURN GREATEST(100, SQRT(row_count)::INTEGER);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper function: Calculate optimal probes for target recall
CREATE OR REPLACE FUNCTION arkham_vectors.optimal_probes(
    lists INTEGER,
    target_recall NUMERIC DEFAULT 0.95
)
RETURNS INTEGER AS $$
BEGIN
    IF target_recall >= 0.99 THEN
        RETURN GREATEST(lists / 2, (SQRT(lists) * 3)::INTEGER);
    ELSIF target_recall >= 0.95 THEN
        RETURN GREATEST(10, SQRT(lists)::INTEGER);
    ELSE
        RETURN GREATEST(5, lists / 10);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Initialize default collections
INSERT INTO arkham_vectors.collections
    (name, vector_size, distance_metric, index_type, lists, probes)
VALUES
    ('arkham_chunks', 1024, 'cosine', 'ivfflat', 1000, 32),
    ('arkham_documents', 1024, 'cosine', 'ivfflat', 316, 18),
    ('arkham_entities', 1024, 'cosine', 'ivfflat', 707, 27)
ON CONFLICT (name) DO NOTHING;

-- Default IVFFlat indexes for standard collections
-- Note: These will be empty until data is inserted
CREATE INDEX IF NOT EXISTS idx_ivfflat_arkham_chunks
    ON arkham_vectors.embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 1000)
    WHERE collection = 'arkham_chunks';

CREATE INDEX IF NOT EXISTS idx_ivfflat_arkham_documents
    ON arkham_vectors.embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 316)
    WHERE collection = 'arkham_documents';

CREATE INDEX IF NOT EXISTS idx_ivfflat_arkham_entities
    ON arkham_vectors.embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 707)
    WHERE collection = 'arkham_entities';

-- ============================================
-- STEP 4: Job Queue (replaces Redis)
-- ============================================

-- Main jobs table
CREATE TABLE IF NOT EXISTS arkham_jobs.jobs (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    pool VARCHAR(50) NOT NULL,
    job_type VARCHAR(100) NOT NULL DEFAULT 'default',
    payload JSONB NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL DEFAULT 5,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    worker_id VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_error TEXT,
    result JSONB,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'scheduled', 'processing', 'completed', 'failed', 'dead')),
    CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 10)
);

-- Job queue performance indexes
CREATE INDEX IF NOT EXISTS idx_jobs_pending
    ON arkham_jobs.jobs (pool, priority, created_at)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled
    ON arkham_jobs.jobs (scheduled_at)
    WHERE status = 'scheduled';
CREATE INDEX IF NOT EXISTS idx_jobs_processing
    ON arkham_jobs.jobs (worker_id, started_at)
    WHERE status = 'processing';
CREATE INDEX IF NOT EXISTS idx_jobs_cleanup
    ON arkham_jobs.jobs (completed_at)
    WHERE status IN ('completed', 'failed', 'dead');

-- Workers registry table
CREATE TABLE IF NOT EXISTS arkham_jobs.workers (
    id VARCHAR(100) PRIMARY KEY,
    pool VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(100),
    pid INTEGER,
    state VARCHAR(20) NOT NULL DEFAULT 'starting',
    jobs_completed INTEGER DEFAULT 0,
    jobs_failed INTEGER DEFAULT 0,
    current_job VARCHAR(36),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_state CHECK (state IN ('starting', 'idle', 'processing', 'stopping', 'stopped', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_workers_pool
    ON arkham_jobs.workers (pool, state);
CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
    ON arkham_jobs.workers (last_heartbeat);

-- Dead letter queue
CREATE TABLE IF NOT EXISTS arkham_jobs.dead_letters (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    pool VARCHAR(50) NOT NULL,
    job_type VARCHAR(100),
    payload JSONB NOT NULL,
    error TEXT,
    retry_count INTEGER,
    original_created_at TIMESTAMP,
    failed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reprocessed_at TIMESTAMP,
    reprocessed_job_id VARCHAR(36)
);

CREATE INDEX IF NOT EXISTS idx_dlq_pool
    ON arkham_jobs.dead_letters (pool, failed_at);
CREATE INDEX IF NOT EXISTS idx_dlq_pending
    ON arkham_jobs.dead_letters (pool)
    WHERE reprocessed_at IS NULL;

-- ============================================
-- STEP 5: LISTEN/NOTIFY Triggers (replaces Redis Pub/Sub)
-- ============================================

-- Notify when new job is created
CREATE OR REPLACE FUNCTION arkham_jobs.notify_job_created()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('arkham_job_available', json_build_object(
        'pool', NEW.pool,
        'job_id', NEW.id,
        'priority', NEW.priority,
        'job_type', NEW.job_type
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_created ON arkham_jobs.jobs;
CREATE TRIGGER trg_job_created
    AFTER INSERT ON arkham_jobs.jobs
    FOR EACH ROW
    WHEN (NEW.status = 'pending')
    EXECUTE FUNCTION arkham_jobs.notify_job_created();

-- Notify on job status change
CREATE OR REPLACE FUNCTION arkham_jobs.notify_job_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status = 'processing' THEN
        PERFORM pg_notify('arkham_job_completed', json_build_object(
            'job_id', NEW.id,
            'pool', NEW.pool,
            'worker_id', NEW.worker_id,
            'job_type', NEW.job_type
        )::text);
    ELSIF NEW.status IN ('failed', 'dead') AND OLD.status = 'processing' THEN
        PERFORM pg_notify('arkham_job_failed', json_build_object(
            'job_id', NEW.id,
            'pool', NEW.pool,
            'worker_id', NEW.worker_id,
            'error', NEW.last_error
        )::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_status ON arkham_jobs.jobs;
CREATE TRIGGER trg_job_status
    AFTER UPDATE OF status ON arkham_jobs.jobs
    FOR EACH ROW
    EXECUTE FUNCTION arkham_jobs.notify_job_status();

-- Notify on worker state change
CREATE OR REPLACE FUNCTION arkham_jobs.notify_worker_event()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.state IS DISTINCT FROM NEW.state THEN
        PERFORM pg_notify('arkham_worker_event', json_build_object(
            'worker_id', NEW.id,
            'pool', NEW.pool,
            'event', NEW.state,
            'prev_state', OLD.state
        )::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_worker_state ON arkham_jobs.workers;
CREATE TRIGGER trg_worker_state
    AFTER UPDATE OF state ON arkham_jobs.workers
    FOR EACH ROW
    EXECUTE FUNCTION arkham_jobs.notify_worker_event();

-- ============================================
-- STEP 6: Rate Limiting (replaces Redis/SlowAPI)
-- ============================================

CREATE TABLE IF NOT EXISTS arkham_frame.rate_limits (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    request_count INTEGER DEFAULT 1,
    UNIQUE(key, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup
    ON arkham_frame.rate_limits (key, window_start DESC);

-- Rate limit check function
CREATE OR REPLACE FUNCTION arkham_frame.check_rate_limit(
    p_key VARCHAR,
    p_limit INTEGER,
    p_window_seconds INTEGER
) RETURNS TABLE(allowed BOOLEAN, current_count INTEGER, reset_at TIMESTAMP) AS $$
DECLARE
    v_window_start TIMESTAMP;
    v_count INTEGER;
BEGIN
    v_window_start := date_trunc('second', NOW())
                      - (EXTRACT(EPOCH FROM NOW())::integer % p_window_seconds)
                      * INTERVAL '1 second';

    INSERT INTO arkham_frame.rate_limits (key, window_start, request_count)
    VALUES (p_key, v_window_start, 1)
    ON CONFLICT (key, window_start) DO UPDATE
        SET request_count = arkham_frame.rate_limits.request_count + 1
    RETURNING request_count INTO v_count;

    RETURN QUERY SELECT
        v_count <= p_limit,
        v_count,
        v_window_start + p_window_seconds * INTERVAL '1 second';
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- STEP 7: Cleanup Functions
-- ============================================

-- Cleanup old rate limit entries (run periodically)
CREATE OR REPLACE FUNCTION arkham_frame.cleanup_rate_limits()
RETURNS INTEGER AS $$
DECLARE deleted_count INTEGER;
BEGIN
    DELETE FROM arkham_frame.rate_limits
    WHERE window_start < NOW() - INTERVAL '5 minutes';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Cleanup stale workers
CREATE OR REPLACE FUNCTION arkham_jobs.cleanup_stale_workers(timeout_seconds INTEGER DEFAULT 120)
RETURNS INTEGER AS $$
DECLARE
    cleaned INTEGER := 0;
    stale_worker RECORD;
BEGIN
    FOR stale_worker IN
        SELECT id, current_job FROM arkham_jobs.workers
        WHERE last_heartbeat < NOW() - (timeout_seconds || ' seconds')::INTERVAL
          AND state NOT IN ('stopped', 'error')
    LOOP
        -- Release current job back to pending
        IF stale_worker.current_job IS NOT NULL THEN
            UPDATE arkham_jobs.jobs
            SET status = 'pending',
                worker_id = NULL,
                started_at = NULL,
                retry_count = retry_count + 1
            WHERE id = stale_worker.current_job
              AND status = 'processing';
        END IF;

        -- Mark worker as error
        UPDATE arkham_jobs.workers
        SET state = 'error'
        WHERE id = stale_worker.id;

        cleaned := cleaned + 1;
    END LOOP;

    RETURN cleaned;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old completed/failed jobs
CREATE OR REPLACE FUNCTION arkham_jobs.cleanup_old_jobs(retention_days INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE deleted_count INTEGER;
BEGIN
    DELETE FROM arkham_jobs.jobs
    WHERE status IN ('completed', 'failed', 'dead')
      AND completed_at < NOW() - (retention_days || ' days')::INTERVAL;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- STEP 8: Maintenance Settings Table
-- ============================================

-- Store maintenance schedule preferences
CREATE TABLE IF NOT EXISTS arkham_frame.maintenance_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize maintenance settings
INSERT INTO arkham_frame.maintenance_settings (key, value)
VALUES
    ('vector_reindex', '{"schedule": "weekly", "day_of_week": 0, "hour": 3, "last_run": null}'::jsonb),
    ('job_cleanup', '{"retention_days": 7, "last_run": null}'::jsonb),
    ('worker_cleanup', '{"timeout_seconds": 120, "last_run": null}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- COMPLETE
-- ============================================

-- Verify installation
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'SHATTERED Consolidation Migration Complete';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Schemas created: arkham_vectors, arkham_jobs';
    RAISE NOTICE 'Extensions: vector (pgvector)';
    RAISE NOTICE '';
    RAISE NOTICE 'Vector collections:';
    RAISE NOTICE '  - arkham_chunks (IVFFlat, lists=1000)';
    RAISE NOTICE '  - arkham_documents (IVFFlat, lists=316)';
    RAISE NOTICE '  - arkham_entities (IVFFlat, lists=707)';
    RAISE NOTICE '';
    RAISE NOTICE 'Job queue tables:';
    RAISE NOTICE '  - arkham_jobs.jobs';
    RAISE NOTICE '  - arkham_jobs.workers';
    RAISE NOTICE '  - arkham_jobs.dead_letters';
    RAISE NOTICE '';
    RAISE NOTICE 'LISTEN/NOTIFY channels:';
    RAISE NOTICE '  - arkham_job_available';
    RAISE NOTICE '  - arkham_job_completed';
    RAISE NOTICE '  - arkham_job_failed';
    RAISE NOTICE '  - arkham_worker_event';
    RAISE NOTICE '===========================================';
END;
$$;
