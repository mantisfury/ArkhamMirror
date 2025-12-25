"""
CLI for running ArkhamFrame workers.

Usage:
    python -m arkham_frame.workers.cli --pool cpu-ner --count 2
    python -m arkham_frame.workers.cli --tier recommended
    python -m arkham_frame.workers.cli --list-pools
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

from ..services.workers import WORKER_POOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("arkham.workers")


# Resource tiers from RESOURCE_DETECTION.md
RESOURCE_TIERS = {
    "minimal": {
        # 4GB RAM, no GPU
        "cpu-light": 2,
        "io-file": 2,
    },
    "standard": {
        # 8GB RAM, basic GPU
        "cpu-light": 4,
        "cpu-extract": 1,
        "cpu-ner": 2,
        "io-file": 4,
        "gpu-embed": 1,
    },
    "recommended": {
        # 16GB RAM, 8GB VRAM
        "cpu-light": 8,
        "cpu-heavy": 2,
        "cpu-extract": 2,
        "cpu-ner": 4,
        "cpu-image": 2,
        "io-file": 8,
        "io-db": 4,
        "gpu-paddle": 1,
        "gpu-embed": 1,
    },
    "power": {
        # 32GB RAM, 12GB+ VRAM
        "cpu-light": 16,
        "cpu-heavy": 4,
        "cpu-extract": 4,
        "cpu-ner": 8,
        "cpu-image": 4,
        "cpu-archive": 2,
        "io-file": 16,
        "io-db": 8,
        "gpu-paddle": 2,
        "gpu-qwen": 1,
        "gpu-whisper": 1,
        "gpu-embed": 2,
    },
}


def get_worker_class(pool: str):
    """
    Get the worker class for a pool.

    Returns None if no worker is implemented yet.
    """
    from .examples import EchoWorker, SlowWorker
    from .extract_worker import ExtractWorker
    from .ner_worker import NERWorker
    from .embed_worker import EmbedWorker
    from .light_worker import LightWorker
    from .paddle_worker import PaddleWorker
    from .qwen_worker import QwenWorker
    from .file_worker import FileWorker
    from .image_worker import ImageWorker
    from .enrich_worker import EnrichWorker
    from .db_worker import DBWorker
    from .archive_worker import ArchiveWorker
    from .whisper_worker import WhisperWorker
    from .analysis_worker import AnalysisWorker

    # Worker implementations
    worker_map = {
        # IO workers
        "io-file": FileWorker,
        "io-db": DBWorker,
        # CPU workers
        "cpu-light": LightWorker,
        "cpu-heavy": SlowWorker,  # Example worker for testing
        "cpu-extract": ExtractWorker,
        "cpu-ner": NERWorker,
        "cpu-image": ImageWorker,
        "cpu-archive": ArchiveWorker,
        # GPU workers - OCR
        "gpu-paddle": PaddleWorker,
        "gpu-qwen": QwenWorker,
        # GPU workers - audio
        "gpu-whisper": WhisperWorker,
        # GPU workers - embeddings
        "gpu-embed": EmbedWorker,
        # LLM workers
        "llm-enrich": EnrichWorker,
        "llm-analysis": AnalysisWorker,
    }

    return worker_map.get(pool)


def list_pools():
    """Print all available worker pools."""
    print("\nAvailable Worker Pools:")
    print("=" * 60)

    by_type = {}
    for pool, config in WORKER_POOLS.items():
        pool_type = config["type"]
        if pool_type not in by_type:
            by_type[pool_type] = []
        by_type[pool_type].append((pool, config))

    for pool_type in ["io", "cpu", "gpu", "llm"]:
        if pool_type in by_type:
            print(f"\n{pool_type.upper()} Pools:")
            for pool, config in by_type[pool_type]:
                worker_class = get_worker_class(pool)
                status = "IMPLEMENTED" if worker_class else "NOT IMPLEMENTED"
                vram = f" ({config.get('vram_mb', 0)}MB VRAM)" if "vram_mb" in config else ""
                print(f"  {pool:15} max={config['max_workers']:2}{vram:20} [{status}]")

    print("\n")


def list_tiers():
    """Print resource tiers."""
    print("\nResource Tiers:")
    print("=" * 60)

    for tier, pools in RESOURCE_TIERS.items():
        print(f"\n{tier.upper()}:")
        for pool, count in pools.items():
            print(f"  {pool}: {count}")

    print("\n")


async def run_workers(pools: dict, redis_url: str):
    """Run workers for specified pools."""
    from .runner import WorkerRunner

    runner = WorkerRunner(redis_url=redis_url)

    # Register available worker classes
    for pool in pools.keys():
        worker_class = get_worker_class(pool)
        if worker_class:
            runner.register_worker_class(pool, worker_class)
        else:
            logger.warning(f"No worker implementation for pool {pool}")

    # Check if we have any workers to run
    registered = [p for p in pools.keys() if get_worker_class(p)]
    if not registered:
        logger.error("No worker implementations available for specified pools")
        logger.info("Worker classes need to be implemented and registered in cli.py")
        return

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        runner.request_shutdown()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run
    try:
        await runner.run(pools=list(registered), counts=pools)
    except KeyboardInterrupt:
        pass
    finally:
        await runner.shutdown()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run ArkhamFrame workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m arkham_frame.workers.cli --list-pools
  python -m arkham_frame.workers.cli --pool cpu-ner --count 2
  python -m arkham_frame.workers.cli --tier recommended
  python -m arkham_frame.workers.cli --pool cpu-ner --pool gpu-embed
        """,
    )

    parser.add_argument(
        "--pool",
        action="append",
        dest="pools",
        help="Pool to run workers for (can specify multiple)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of workers per pool (default: 1)",
    )
    parser.add_argument(
        "--tier",
        choices=list(RESOURCE_TIERS.keys()),
        help="Use a predefined resource tier",
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", "redis://localhost:6380"),
        help="Redis connection URL",
    )
    parser.add_argument(
        "--list-pools",
        action="store_true",
        help="List available worker pools",
    )
    parser.add_argument(
        "--list-tiers",
        action="store_true",
        help="List resource tiers",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_pools:
        list_pools()
        return

    if args.list_tiers:
        list_tiers()
        return

    # Determine pools to run
    pools = {}

    if args.tier:
        pools = RESOURCE_TIERS[args.tier].copy()
        logger.info(f"Using tier '{args.tier}' with {len(pools)} pools")

    elif args.pools:
        for pool in args.pools:
            if pool not in WORKER_POOLS:
                logger.error(f"Unknown pool: {pool}")
                logger.info("Use --list-pools to see available pools")
                sys.exit(1)
            pools[pool] = args.count

    else:
        parser.print_help()
        print("\nError: Must specify --pool, --tier, or --list-pools")
        sys.exit(1)

    logger.info(f"Starting workers: {pools}")

    # Run
    asyncio.run(run_workers(pools, args.redis_url))


if __name__ == "__main__":
    main()
