"""
RQ Worker script for ArkhamMirror.

This script runs RQ workers using SimpleWorker class which is required for Windows
(no fork support). Workers listen on specified queues and process jobs.

Usage:
    python run_rq_worker.py [queue1] [queue2] ...

Example:
    python run_rq_worker.py default splitter ocr parser embed clustering
"""

import sys
from pathlib import Path

# Add project root to path for central config
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import REDIS_URL
from rq.worker import SimpleWorker
from redis import Redis


if __name__ == "__main__":
    conn = Redis.from_url(REDIS_URL)

    # Parse queue arguments - argv[0] is script name, argv[1:] are queues
    qs = sys.argv[1:] if len(sys.argv) > 1 else ["default"]

    print("=" * 60)
    print("ArkhamMirror RQ Worker")
    print("=" * 60)
    print(f"Queues: {', '.join(qs)}")
    print(f"Redis URL: {REDIS_URL}")
    print("=" * 60)
    print("Worker starting... Press Ctrl+C to stop.")
    print()

    w = SimpleWorker(qs, connection=conn)
    w.work()
