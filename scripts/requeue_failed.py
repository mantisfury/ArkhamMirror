from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
conn = Redis.from_url(redis_url)
q = Queue(connection=conn)
registry = FailedJobRegistry(queue=q)

failed_job_ids = registry.get_job_ids()
print(f"Found {len(failed_job_ids)} failed jobs.")

for job_id in failed_job_ids:
    print(f"Requeuing {job_id}...")
    registry.requeue(job_id)

print("Done.")
