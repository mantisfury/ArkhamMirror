"""
Settings State

Manages application settings and the Nuclear Wipe feature.
"""

import reflex as rx
import logging
from typing import Dict

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class KeywordItem(BaseModel):
    id: int
    keyword: str
    weight: float
    is_active: bool


class SettingsState(rx.State):
    """State for application settings and data management."""

    # Wipe confirmation flow
    wipe_dialog_open: bool = False
    wipe_confirmation_text: str = ""
    wipe_in_progress: bool = False
    wipe_result: Dict = {}
    wipe_error: str = ""

    # Data statistics
    data_stats: Dict = {}
    stats_loading: bool = False

    # Health check status
    health_status: Dict = {}
    health_loading: bool = False

    # Wipe options
    wipe_files: bool = True
    wipe_database: bool = True
    wipe_vectors: bool = True
    wipe_queue: bool = True

    def open_wipe_dialog(self):
        """Open the nuclear wipe confirmation dialog."""
        self.wipe_dialog_open = True
        self.wipe_confirmation_text = ""
        self.wipe_result = {}
        self.wipe_error = ""
        # Load stats when dialog opens
        return SettingsState.load_data_stats

    def close_wipe_dialog(self):
        """Close the wipe dialog."""
        self.wipe_dialog_open = False
        self.wipe_confirmation_text = ""
        self.wipe_error = ""

    def set_confirmation_text(self, value: str):
        """Update the confirmation text."""
        self.wipe_confirmation_text = value

    def toggle_wipe_files(self, value: bool):
        self.wipe_files = value

    def toggle_wipe_database(self, value: bool):
        self.wipe_database = value

    def toggle_wipe_vectors(self, value: bool):
        self.wipe_vectors = value

    def toggle_wipe_queue(self, value: bool):
        self.wipe_queue = value

    @rx.var
    def can_wipe(self) -> bool:
        """Check if the wipe button should be enabled."""
        return (
            self.wipe_confirmation_text.upper() == "DELETE ALL DATA"
            and not self.wipe_in_progress
            and (
                self.wipe_files
                or self.wipe_database
                or self.wipe_vectors
                or self.wipe_queue
            )
        )

    @rx.var
    def total_files_display(self) -> str:
        """Display string for total files."""
        if not self.data_stats:
            return "Loading..."
        return f"{self.data_stats.get('total_files', 0):,} files"

    @rx.var
    def total_size_display(self) -> str:
        """Display string for total size."""
        if not self.data_stats:
            return ""
        return f"({self.data_stats.get('total_size_mb', 0):.1f} MB)"

    @rx.var
    def wipe_success(self) -> bool:
        """Check if wipe was successful."""
        return self.wipe_result.get("success", False)

    @rx.var
    def wipe_files_deleted(self) -> int:
        """Get number of files deleted in wipe."""
        return self.wipe_result.get("total_files_deleted", 0)

    # Health status computed vars for each service
    @rx.var
    def pg_status(self) -> str:
        """PostgreSQL status."""
        return self.health_status.get("postgresql", {}).get("status", "unknown")

    @rx.var
    def pg_message(self) -> str:
        """PostgreSQL message."""
        return self.health_status.get("postgresql", {}).get("message", "")

    @rx.var
    def qdrant_status(self) -> str:
        """Qdrant status."""
        return self.health_status.get("qdrant", {}).get("status", "unknown")

    @rx.var
    def qdrant_message(self) -> str:
        """Qdrant message."""
        return self.health_status.get("qdrant", {}).get("message", "")

    @rx.var
    def redis_status(self) -> str:
        """Redis status."""
        return self.health_status.get("redis", {}).get("status", "unknown")

    @rx.var
    def redis_message(self) -> str:
        """Redis message."""
        return self.health_status.get("redis", {}).get("message", "")

    @rx.var
    def lm_status(self) -> str:
        """LM Studio status."""
        return self.health_status.get("lm_studio", {}).get("status", "unknown")

    @rx.var
    def lm_message(self) -> str:
        """LM Studio message."""
        return self.health_status.get("lm_studio", {}).get("message", "")

    @rx.var
    def spacy_status(self) -> str:
        """spaCy status."""
        return self.health_status.get("spacy", {}).get("status", "unknown")

    @rx.var
    def spacy_message(self) -> str:
        """spaCy message."""
        return self.health_status.get("spacy", {}).get("message", "")

    async def load_data_stats(self):
        """Load statistics about data to be deleted."""
        self.stats_loading = True
        yield

        try:
            from app.arkham.services.utils.data_wipe import get_data_silo_stats

            self.data_stats = get_data_silo_stats()
        except Exception as e:
            self.data_stats = {"error": str(e)}
        finally:
            self.stats_loading = False

    async def execute_nuclear_wipe(self):
        """Execute the nuclear wipe operation."""
        if not self.can_wipe:
            self.wipe_error = "Please type 'DELETE ALL DATA' to confirm"
            return

        self.wipe_in_progress = True
        self.wipe_error = ""
        self.wipe_result = {}
        yield

        try:
            from app.arkham.services.utils.data_wipe import nuclear_wipe

            result = nuclear_wipe(
                clear_files=self.wipe_files,
                clear_database=self.wipe_database,
                clear_vectors=self.wipe_vectors,
                clear_queue=self.wipe_queue,
            )

            self.wipe_result = result.to_dict()

            if result.success:
                self.wipe_error = ""

                # Reset all frontend state caches after successful wipe
                try:
                    from app.arkham.state.overview_state import OverviewState
                    from app.arkham.state.ingestion_status_state import (
                        IngestionStatusState,
                    )

                    overview_state = await self.get_state(OverviewState)
                    if overview_state:
                        overview_state.reset_stats()

                    ingestion_state = await self.get_state(IngestionStatusState)
                    if ingestion_state:
                        ingestion_state.refresh_status()
                except Exception as state_e:
                    logger.warning(f"Could not reset frontend state: {state_e}")
            else:
                self.wipe_error = (
                    f"Completed with issues: {', '.join(result.steps_failed)}"
                )

        except Exception as e:
            self.wipe_error = f"Wipe failed: {str(e)}"
            self.wipe_result = {"success": False, "error": str(e)}
        finally:
            self.wipe_in_progress = False
            self.wipe_confirmation_text = ""

    async def check_health_status(self):
        """Check the health status of all services."""
        self.health_loading = True
        yield

        status = {
            "postgresql": {"status": "unknown", "message": ""},
            "qdrant": {"status": "unknown", "message": ""},
            "redis": {"status": "unknown", "message": ""},
            "lm_studio": {"status": "unknown", "message": ""},
            "spacy": {"status": "unknown", "message": ""},
        }

        # Check PostgreSQL
        try:
            from sqlalchemy import create_engine, text
            from config.settings import DATABASE_URL

            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            status["postgresql"] = {"status": "ok", "message": "Connected"}
        except Exception as e:
            status["postgresql"] = {"status": "error", "message": str(e)[:50]}

        yield

        # Check Qdrant
        try:
            from qdrant_client import QdrantClient
            from config.settings import QDRANT_URL

            client = QdrantClient(url=QDRANT_URL, timeout=5.0)
            collections = client.get_collections()
            count = len(collections.collections)
            status["qdrant"] = {"status": "ok", "message": f"{count} collection(s)"}
        except Exception as e:
            status["qdrant"] = {"status": "error", "message": str(e)[:50]}

        yield

        # Check Redis
        try:
            import redis
            from config.settings import REDIS_URL

            r = redis.from_url(REDIS_URL, socket_timeout=5)
            r.ping()
            status["redis"] = {"status": "ok", "message": "Connected"}
        except Exception as e:
            status["redis"] = {"status": "error", "message": str(e)[:50]}

        yield

        # Check LM Studio
        try:
            import requests
            from config.settings import LM_STUDIO_URL

            # LM_STUDIO_URL already includes /v1, so we just append /models
            response = requests.get(f"{LM_STUDIO_URL}/models", timeout=3)
            if response.status_code == 200:
                models = response.json().get("data", [])
                if models:
                    status["lm_studio"] = {
                        "status": "ok",
                        "message": f"{len(models)} model(s) available",
                    }
                else:
                    status["lm_studio"] = {
                        "status": "warning",
                        "message": "No models loaded",
                    }
            else:
                status["lm_studio"] = {
                    "status": "error",
                    "message": f"HTTP {response.status_code}",
                }
        except requests.exceptions.ConnectionError:
            status["lm_studio"] = {
                "status": "warning",
                "message": "Not running (optional)",
            }
        except Exception as e:
            status["lm_studio"] = {"status": "error", "message": str(e)[:50]}

        yield

        # Check spaCy
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
            status["spacy"] = {"status": "ok", "message": "Model loaded"}
        except OSError:
            status["spacy"] = {"status": "warning", "message": "Model not installed"}
        except Exception as e:
            status["spacy"] = {"status": "error", "message": str(e)[:50]}

        self.health_status = status
        self.health_loading = False

    # Anomaly Keywords Management
    keywords: list[KeywordItem] = []
    new_keyword: str = ""
    new_weight: float = 0.2
    is_keywords_loading: bool = False

    async def load_keywords(self):
        """Load anomaly keywords from database."""
        self.is_keywords_loading = True
        yield
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.settings import DATABASE_URL
            from app.arkham.services.db.models import AnomalyKeyword

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                items = (
                    session.query(AnomalyKeyword).order_by(AnomalyKeyword.keyword).all()
                )
                self.keywords = [
                    KeywordItem(
                        id=k.id,
                        keyword=k.keyword,
                        weight=k.weight,
                        is_active=bool(k.is_active),
                    )
                    for k in items
                ]
        except Exception as e:
            logger.error(f"Error loading keywords: {e}")
        finally:
            self.is_keywords_loading = False

    async def add_keyword(self):
        """Add a new anomaly keyword."""
        if not self.new_keyword.strip():
            return

        self.is_keywords_loading = True
        yield
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.settings import DATABASE_URL
            from app.arkham.services.db.models import AnomalyKeyword

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                # Check duplicate
                existing = (
                    session.query(AnomalyKeyword)
                    .filter_by(keyword=self.new_keyword.strip().lower())
                    .first()
                )
                if existing:
                    self.is_keywords_loading = False
                    return

                kw = AnomalyKeyword(
                    keyword=self.new_keyword.strip().lower(),
                    weight=self.new_weight,
                    is_active=1,
                )
                session.add(kw)
                session.commit()

            self.new_keyword = ""
            self.is_keywords_loading = False
            yield SettingsState.load_keywords
        except Exception as e:
            logger.error(f"Error adding keyword: {e}")
            self.is_keywords_loading = False

    async def delete_keyword(self, kid: int):
        """Delete an anomaly keyword."""
        self.is_keywords_loading = True
        yield
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.settings import DATABASE_URL
            from app.arkham.services.db.models import AnomalyKeyword

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                session.query(AnomalyKeyword).filter(AnomalyKeyword.id == kid).delete()
                session.commit()

            self.is_keywords_loading = False
            yield SettingsState.load_keywords
        except Exception as e:
            logger.error(f"Error deleting keyword: {e}")
            self.is_keywords_loading = False

    async def toggle_keyword(self, kid: int):
        """Toggle keyword active status."""
        self.is_keywords_loading = True
        yield
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.settings import DATABASE_URL
            from app.arkham.services.db.models import AnomalyKeyword

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                kw = session.query(AnomalyKeyword).get(kid)
                if kw:
                    kw.is_active = 0 if kw.is_active else 1
                    session.commit()

            self.is_keywords_loading = False
            yield SettingsState.load_keywords
        except Exception as e:
            logger.error(f"Error toggling keyword: {e}")
            self.is_keywords_loading = False

    def set_new_keyword(self, val: str):
        self.new_keyword = val

    def set_new_weight(self, val: str):
        try:
            self.new_weight = float(val)
        except:
            pass
