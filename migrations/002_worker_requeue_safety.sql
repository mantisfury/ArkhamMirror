-- Migration 002: Worker-failure requeue safety
-- When a worker fails (crash, stale heartbeat), the job is requeued. This adds
-- a separate counter (worker_requeue_count) and cap (max_worker_requeues) so
-- we stop requeuing after N worker-failures and mark the job dead with a
-- user-visible warning (possible toxic job).

-- Add worker-failure requeue tracking to jobs
ALTER TABLE arkham_jobs.jobs
    ADD COLUMN IF NOT EXISTS worker_requeue_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE arkham_jobs.jobs
    ADD COLUMN IF NOT EXISTS max_worker_requeues INTEGER NOT NULL DEFAULT 3;

COMMENT ON COLUMN arkham_jobs.jobs.worker_requeue_count IS
    'Times this job was requeued because the worker failed (stale/crash). Kept separate from retry_count (job failure).';
COMMENT ON COLUMN arkham_jobs.jobs.max_worker_requeues IS
    'Max worker-failure requeues before marking dead. Default 3. Exceeding triggers user warning (possible toxic job).';

-- Replace cleanup_stale_workers to respect worker_requeue_count / max_worker_requeues
CREATE OR REPLACE FUNCTION arkham_jobs.cleanup_stale_workers(timeout_seconds INTEGER DEFAULT 120)
RETURNS INTEGER AS $$
DECLARE
    cleaned INTEGER := 0;
    stale_worker RECORD;
    wr_count INTEGER;
    max_wr INTEGER;
BEGIN
    FOR stale_worker IN
        SELECT id, current_job FROM arkham_jobs.workers
        WHERE last_heartbeat < NOW() - (timeout_seconds || ' seconds')::INTERVAL
          AND state NOT IN ('stopped', 'error')
    LOOP
        IF stale_worker.current_job IS NOT NULL THEN
            SELECT j.worker_requeue_count, COALESCE(j.max_worker_requeues, 3)
              INTO wr_count, max_wr
              FROM arkham_jobs.jobs j
             WHERE j.id = stale_worker.current_job
               AND j.status = 'processing';

            IF FOUND THEN
                IF wr_count < max_wr THEN
                    -- Requeue: worker failed, job may be fine
                    UPDATE arkham_jobs.jobs
                    SET status = 'pending',
                        worker_id = NULL,
                        started_at = NULL,
                        worker_requeue_count = worker_requeue_count + 1,
                        last_error = 'Worker failed (stale heartbeat); requeued.'
                    WHERE id = stale_worker.current_job
                      AND status = 'processing';
                ELSE
                    -- Safety limit: stop requeuing, mark dead, user warning
                    INSERT INTO arkham_jobs.dead_letters
                    (job_id, pool, job_type, payload, error, retry_count, original_created_at)
                    SELECT id, pool, job_type, payload,
                           'Job requeued too many times due to worker failure; possible toxic job. Last: Worker failed (stale heartbeat).',
                           retry_count, created_at
                    FROM arkham_jobs.jobs
                    WHERE id = stale_worker.current_job AND status = 'processing';

                    UPDATE arkham_jobs.jobs
                    SET status = 'dead',
                        completed_at = NOW(),
                        last_error = 'Job requeued too many times due to worker failure; possible toxic job. Last: Worker failed (stale heartbeat).',
                        worker_id = NULL,
                        started_at = NULL
                    WHERE id = stale_worker.current_job AND status = 'processing';
                END IF;
            END IF;
        END IF;

        UPDATE arkham_jobs.workers
        SET state = 'error'
        WHERE id = stale_worker.id;

        cleaned := cleaned + 1;
    END LOOP;

    RETURN cleaned;
END;
$$ LANGUAGE plpgsql;
