import reflex as rx
import logging
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)


class KeyActor(BaseModel):
    id: int
    name: str
    type: str
    mentions: int


class KeyRelationship(BaseModel):
    entity1: str
    entity2: str
    type: str
    strength: int


class CentralFigure(BaseModel):
    name: str
    role: str
    significance: str


class Subject(BaseModel):
    name: str
    profile: str
    risk_level: str = "Medium"


class InvestigationHypothesis(BaseModel):
    hypothesis: str
    confidence: str
    supporting_evidence: str = ""


class BigPictureState(rx.State):
    """State for Cross-Document Big Picture Engine."""

    # Corpus stats
    doc_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0
    entity_types: dict = {}

    # Key actors and relationships
    key_actors: List[KeyActor] = []
    key_relationships: List[KeyRelationship] = []

    # Executive summary
    executive_summary: str = ""
    key_themes: List[str] = []
    central_figures: List[CentralFigure] = []
    network_insights: str = ""
    timeline_patterns: str = ""
    red_flags: List[str] = []
    information_gaps: List[str] = []
    focus_areas: List[str] = []

    # Investigation brief
    brief_title: str = ""
    brief_subjects: List[Subject] = []
    brief_hypotheses: List[InvestigationHypothesis] = []
    brief_priority_actions: List[str] = []
    brief_risks: List[str] = []
    brief_evidence_strength: str = ""

    # UI state
    is_loading: bool = False
    is_generating: bool = False
    active_tab: str = "overview"
    has_summary: bool = False
    has_brief: bool = False

    def load_overview(self):
        """Load corpus overview data."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.big_picture_service import (
                get_big_picture_service,
            )

            service = get_big_picture_service()
            overview = service.get_corpus_overview()

            stats = overview.get("stats", {})
            self.doc_count = stats.get("documents", 0)
            self.chunk_count = stats.get("chunks", 0)
            self.entity_count = stats.get("entities", 0)
            self.relationship_count = stats.get("relationships", 0)
            self.entity_types = stats.get("entity_types", {})

            self.key_actors = [
                KeyActor(
                    id=a["id"], name=a["name"], type=a["type"], mentions=a["mentions"]
                )
                for a in overview.get("key_actors", [])
            ]

            self.key_relationships = [
                KeyRelationship(
                    entity1=r["entity1"],
                    entity2=r["entity2"],
                    type=r["type"],
                    strength=r["strength"],
                )
                for r in overview.get("key_relationships", [])
            ]

        except Exception as e:
            logger.error(f"Error loading overview: {e}")
        finally:
            self.is_loading = False

    async def generate_executive_summary(self):
        """Generate LLM-powered executive summary."""
        import asyncio

        self.is_generating = True
        self.active_tab = "summary"
        yield

        try:
            from app.arkham.services.big_picture_service import (
                get_big_picture_service,
            )

            logger.info("BigPictureState: Starting executive summary generation...")
            service = get_big_picture_service()
            result = await asyncio.to_thread(service.generate_executive_summary)
            logger.info("BigPictureState: Executive summary generation complete")

            self.executive_summary = result.get("executive_summary", "")
            self.key_themes = result.get("key_themes", [])
            self.network_insights = result.get("network_insights", "")
            self.timeline_patterns = result.get("timeline_patterns", "")
            self.red_flags = result.get("red_flags", [])
            self.information_gaps = result.get("information_gaps", [])
            self.focus_areas = result.get("focus_areas", [])

            self.central_figures = [
                CentralFigure(
                    name=f.get("name", ""),
                    role=f.get("role", ""),
                    significance=f.get("significance", ""),
                )
                for f in result.get("central_figures", [])
            ]

            self.has_summary = True

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            self.executive_summary = f"Error: {e}"
        finally:
            self.is_generating = False

    def generate_investigation_brief(self):
        """Generate focused investigation brief."""
        self.is_generating = True
        self.active_tab = "brief"
        yield

        try:
            from app.arkham.services.big_picture_service import (
                get_big_picture_service,
            )

            service = get_big_picture_service()
            result = service.generate_investigation_brief()

            self.brief_title = result.get("title", "Investigation Brief")
            self.brief_evidence_strength = result.get("evidence_strength", "Unknown")
            self.brief_priority_actions = result.get("priority_actions", [])
            self.brief_risks = result.get("risks", [])

            self.brief_subjects = [
                Subject(
                    name=s.get("name", ""),
                    profile=s.get("profile", ""),
                    risk_level=s.get("risk_level", "Medium"),
                )
                for s in result.get("subjects", [])
            ]

            self.brief_hypotheses = [
                InvestigationHypothesis(
                    hypothesis=h.get("hypothesis", ""),
                    confidence=h.get("confidence", "Medium"),
                    supporting_evidence=h.get("supporting_evidence", ""),
                )
                for h in result.get("hypotheses", [])
            ]

            self.has_brief = True

        except Exception as e:
            logger.error(f"Error generating brief: {e}")
        finally:
            self.is_generating = False

    def set_active_tab(self, tab: str):
        self.active_tab = tab
