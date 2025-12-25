"""
ArkhamFrame FastAPI Application.

The main entry point for the Frame REST API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .frame import ArkhamFrame

logger = logging.getLogger(__name__)

# Global frame instance
frame: ArkhamFrame = None


async def load_shards(frame: ArkhamFrame, app: FastAPI) -> None:
    """
    Load and initialize available shards using entry points.

    Shards register themselves via pyproject.toml:
        [project.entry-points."arkham.shards"]
        dashboard = "arkham_shard_dashboard:DashboardShard"
        ingest = "arkham_shard_ingest:IngestShard"
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:
        from importlib_metadata import entry_points

    # Discover shards via entry points
    eps = entry_points(group="arkham.shards")

    for ep in eps:
        shard_name = ep.name
        try:
            logger.info(f"Loading shard: {shard_name}")

            # Load the shard class
            shard_class = ep.load()

            # Instantiate (no args) and initialize with frame
            shard = shard_class()
            await shard.initialize(frame)

            # Register routes if shard has them
            router = shard.get_routes() or shard.get_api_router()

            if router:
                # Routes already include /api prefix
                app.include_router(
                    router,
                    tags=[shard_name.capitalize()],
                )

            frame.shards[shard_name] = shard
            logger.info(f"Shard loaded: {shard_name}")

        except Exception as e:
            logger.warning(f"Failed to load shard {shard_name}: {e}")
            import traceback
            traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Frame lifecycle."""
    global frame

    # Startup
    logger.info("Starting ArkhamFrame...")
    frame = ArkhamFrame()
    await frame.initialize()

    # Load shards
    await load_shards(frame, app)

    yield

    # Shutdown shards
    for name, shard in frame.shards.items():
        try:
            await shard.shutdown()
            logger.info(f"Shard {name} shut down")
        except Exception as e:
            logger.error(f"Error shutting down shard {name}: {e}")

    # Shutdown frame
    logger.info("Stopping ArkhamFrame...")
    await frame.shutdown()


# Create FastAPI app
app = FastAPI(
    title="ArkhamFrame",
    description="ArkhamMirror Shattered Frame - Core Infrastructure API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
from .api import health, documents, entities, projects, shards, events, frame as frame_api
from .api import export, templates, notifications, scheduler

app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(entities.router, prefix="/api/entities", tags=["Entities"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(shards.router, prefix="/api/shards", tags=["Shards"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(frame_api.router, prefix="/api/frame", tags=["Frame"])

# Output Services API routes
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["Scheduler"])


# Static file serving for Shell UI
# In production, Frame serves the built React app from arkham-shard-shell/dist
def setup_static_serving():
    """Set up static file serving for the Shell UI."""
    import os
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Look for Shell dist directory
    # Try relative paths from Frame package location
    possible_paths = [
        Path(__file__).parent.parent.parent / "arkham-shard-shell" / "dist",
        Path(__file__).parent.parent.parent.parent / "arkham-shard-shell" / "dist",
        Path.cwd() / "arkham-shard-shell" / "dist",
    ]

    shell_dist = None
    for path in possible_paths:
        if path.exists() and (path / "index.html").exists():
            shell_dist = path
            break

    if shell_dist:
        logger.info(f"Serving Shell UI from: {shell_dist}")

        # Mount static assets
        app.mount("/assets", StaticFiles(directory=shell_dist / "assets"), name="assets")

        # Serve index.html for all non-API routes (SPA fallback)
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # API routes are handled by routers above
            if path.startswith("api/"):
                return {"error": "Not found"}

            # Serve static files if they exist
            file_path = shell_dist / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

            # SPA fallback - serve index.html
            return FileResponse(shell_dist / "index.html")
    else:
        logger.info("Shell UI dist not found - static serving disabled")
        logger.info("Build the Shell with 'npm run build' in arkham-shard-shell/")


# Only set up static serving in production mode
import os
if os.environ.get("ARKHAM_SERVE_SHELL", "false").lower() == "true":
    setup_static_serving()


def get_frame() -> ArkhamFrame:
    """Get the global Frame instance."""
    if frame is None:
        raise RuntimeError("Frame not initialized")
    return frame
