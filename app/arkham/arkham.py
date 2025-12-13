import reflex as rx
import logging
import sys

# Initialize logging BEFORE any other imports
from .utils.logging_config import setup_logging, log_exception

# Read log level from config
try:
    import yaml
    from pathlib import Path

    # Use config.yaml from app directory (consolidated location)
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        log_level = config.get("system", {}).get("log_level", "INFO")
except Exception as e:
    log_level = "INFO"
    print(
        f"Warning: Could not load config.yaml, using default log level: {e}",
        file=sys.stderr,
    )

setup_logging(level=log_level, enable_console=True, enable_json=False)
logger = logging.getLogger(__name__)

logger.info("Starting ArkhamMirror Reflex Application")

from .pages.search import search_page
from .pages.graph import graph_page
from .pages.timeline import timeline_page
from .pages.settings import settings_page
from .pages.ingest import ingest_page
from .pages.anomalies import anomalies_page
from .pages.visualizations import visualizations_page
from .pages.regex_search import regex_search_page
from .pages.map import map_page
from .pages.tables import tables_page

from .pages.overview import overview_page
from .pages.entity_dedup import entity_dedup_page
from .pages.red_flags import red_flags_page
from .pages.metadata_forensics import metadata_forensics_page
from .pages.contradictions import contradictions_page
from .pages.chain import chain_page
from .pages.influence import influence_page
from .pages.fact_comparison import fact_comparison_page
from .pages.narrative import narrative_page
from .pages.hidden_content import hidden_content_page
from .pages.big_picture import big_picture_page
from .pages.timeline_merge import timeline_merge_page
from .pages.duplicates import duplicates_page
from .pages.speculation import speculation_page
from .pages.export import export_page
from .pages.annotations import annotations_page
from .pages.comparison import comparison_page
from .pages.projects import projects_page
from .pages.filters import filter_page
from .pages.pathfinder import pathfinder_page
from .pages.upload_history import upload_history_page
from .pages.document import document_page, DocumentViewState

from .state.ingestion_status_state import IngestionStatusState

# from .pages.error_boundary_test import error_boundary_test_page  # Commented out - test page with missing dependencies
# from .state.app_state import AppState

# Create the app with error handling
# Note: Theme appearance is set to "dark" as default. Dynamic theme switching
# can be implemented via CSS variables or per-component theming if needed.
try:
    logger.info("Initializing Reflex app")
    app = rx.App(
        theme=rx.theme(
            appearance="dark",
            accent_color="blue",
            radius="large",
        ),
        stylesheets=[
            "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap",
        ],
        style={
            "font_family": "Inter, sans-serif",
        },
    )
    logger.info("Reflex app initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize Reflex app: {e}", exc_info=True)
    raise

# Add routes with error handling
logger.info("Registering routes")
try:
    app.add_page(search_page, route="/", title="Search | ArkhamMirror")
    logger.debug("Route registered: / (search)")

    app.add_page(overview_page, route="/overview", title="Overview | ArkhamMirror")
    logger.debug("Route registered: /overview")

    app.add_page(
        entity_dedup_page,
        route="/entity-dedup",
        title="Entity Deduplication | ArkhamMirror",
    )
    logger.debug("Route registered: /entity-dedup")

    app.add_page(anomalies_page, route="/anomalies", title="Anomalies | ArkhamMirror")
    logger.debug("Route registered: /anomalies")

    app.add_page(graph_page, route="/graph", title="Graph | ArkhamMirror")
    logger.debug("Route registered: /graph")

    app.add_page(map_page, route="/map", title="Map | ArkhamMirror")
    logger.debug("Route registered: /map")

    app.add_page(timeline_page, route="/timeline", title="Timeline | ArkhamMirror")
    logger.debug("Route registered: /timeline")

    app.add_page(tables_page, route="/tables", title="Tables | ArkhamMirror")
    logger.debug("Route registered: /tables")

    app.add_page(
        ingest_page,
        route="/ingest",
        title="Ingest & Chat | ArkhamMirror",
        on_load=IngestionStatusState.on_load,
    )
    logger.debug("Route registered: /ingest")

    app.add_page(
        visualizations_page,
        route="/visualizations",
        title="Visualizations | ArkhamMirror",
    )

    app.add_page(
        red_flags_page,
        route="/red-flags",
        title="Red Flags | ArkhamMirror",
    )

    app.add_page(
        metadata_forensics_page,
        route="/metadata-forensics",
        title="Metadata Forensics | ArkhamMirror",
    )

    app.add_page(
        contradictions_page,
        route="/contradictions",
        title="Contradiction Engine | ArkhamMirror",
    )

    app.add_page(
        chain_page,
        route="/contradiction-chain",
        title="Contradiction Chain | ArkhamMirror",
    )

    app.add_page(
        influence_page,
        route="/influence",
        title="Entity Influence | ArkhamMirror",
    )

    app.add_page(
        fact_comparison_page,
        route="/fact-comparison",
        title="Fact Comparison | ArkhamMirror",
    )

    app.add_page(
        narrative_page,
        route="/narrative",
        title="Narrative Reconstruction | ArkhamMirror",
    )

    app.add_page(
        hidden_content_page,
        route="/hidden-content",
        title="Hidden Content Detection | ArkhamMirror",
    )

    app.add_page(
        big_picture_page,
        route="/big-picture",
        title="Big Picture Engine | ArkhamMirror",
    )

    app.add_page(
        timeline_merge_page,
        route="/timeline-merge",
        title="Timeline Merge | ArkhamMirror",
    )

    app.add_page(
        duplicates_page,
        route="/duplicates",
        title="Duplicate Detector | ArkhamMirror",
    )

    app.add_page(
        speculation_page,
        route="/speculation",
        title="Speculation Mode | ArkhamMirror",
    )

    app.add_page(
        export_page,
        route="/export",
        title="Export | ArkhamMirror",
    )

    app.add_page(
        annotations_page,
        route="/annotations",
        title="Annotations | ArkhamMirror",
    )

    app.add_page(
        comparison_page,
        route="/comparison",
        title="Document Comparison | ArkhamMirror",
    )

    app.add_page(
        projects_page,
        route="/projects",
        title="Projects | ArkhamMirror",
    )

    app.add_page(
        filter_page,
        route="/filters",
        title="Advanced Filters | ArkhamMirror",
    )

    app.add_page(
        pathfinder_page,
        route="/pathfinder",
        title="Path Finder | ArkhamMirror",
    )

    app.add_page(
        upload_history_page,
        route="/upload-history",
        title="Upload History | ArkhamMirror",
    )

    app.add_page(
        regex_search_page,
        route="/regex-search",
        title="Regex Search | ArkhamMirror",
    )

    app.add_page(
        settings_page,
        route="/settings",
        title="Settings | ArkhamMirror",
    )

    app.add_page(
        document_page,
        route="/document/[doc_id]",
        title="Document View | ArkhamMirror",
        on_load=DocumentViewState.on_load,
    )

    # Note: App.pages is not accessible in Reflex 0.8.21, count manually
    logger.info("All routes registered successfully")
except Exception as e:
    logger.critical(f"Failed to register routes: {e}", exc_info=True)
    raise
