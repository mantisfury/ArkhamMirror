import sys
from rq import Worker


# Patch for Windows to force SimpleWorker (no fork)
class WindowsWorker(Worker):
    def fork_work_horse(self, job, queue):
        raise NotImplementedError("Fork is not supported on Windows")

    def execute_job(self, job, queue):
        # Execute directly in the main process (no fork)
        self.perform_job(job, queue)


if __name__ == "__main__":
    # We need to monkey-patch or pass arguments to force SimpleWorker behavior
    # But the easiest way on Windows with RQ is to use the SimpleWorker class directly
    # or just run the worker with a specific flag if available.
    # However, RQ's CLI doesn't easily expose SimpleWorker class selection via args.

    # Let's try to run the worker programmatically using SimpleWorker
    from rq.worker import SimpleWorker
    from redis import Redis
    import os
    from dotenv import load_dotenv

    load_dotenv()

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    conn = Redis.from_url(redis_url)

    qs = sys.argv[2:] if len(sys.argv) > 2 else ["default"]
    w = SimpleWorker(qs, connection=conn)
    w.work()
