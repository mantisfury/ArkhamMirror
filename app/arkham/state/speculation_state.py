import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class WhatIfScenario(BaseModel):
    id: str
    hypothesis: str
    basis: str
    evidence_needed: List[str] = []
    significance: str = "Medium"
    significance_explanation: str = ""
    investigation_steps: List[str] = []


class InformationGap(BaseModel):
    id: str
    type: str
    description: str
    importance: str = "Medium"
    indicators: List[str] = []
    suggested_sources: List[str] = []


class InvestigativeQuestion(BaseModel):
    id: str
    question: str
    priority: str = "Medium"
    rationale: str = ""
    related_entities: List[str] = []
    potential_sources: List[str] = []


class SpeculationDocument(BaseModel):
    """Typed model for document selection in speculation mode."""

    id: int
    title: str


class SpeculationEntity(BaseModel):
    """Typed model for entity selection in speculation mode."""

    id: int
    name: str
    type: str


class SpeculationState(rx.State):
    """State for Speculation Mode."""

    # Results
    scenarios: List[WhatIfScenario] = []
    gaps: List[InformationGap] = []
    questions: List[InvestigativeQuestion] = []

    # Corpus stats
    doc_count: int = 0
    entity_count: int = 0
    rel_count: int = 0

    # UI state
    is_loading: bool = False
    is_generating: bool = False
    active_tab: str = "scenarios"
    focus_topic: str = ""
    has_results: bool = False

    # Selection/filtering state
    available_documents: List[SpeculationDocument] = []
    available_entities: List[SpeculationEntity] = []
    selected_doc_ids: List[int] = []  # Empty = use all
    selected_entity_ids: List[int] = []  # Empty = use all
    show_filters: bool = False

    def load_summary(self):
        """Load corpus summary stats and filter options."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.speculation_service import (
                get_speculation_service,
            )

            service = get_speculation_service()
            summary = service.get_speculation_summary()

            self.doc_count = summary["documents"]
            self.entity_count = summary["entities"]
            self.rel_count = summary["relationships"]

            # Load filter options and convert to typed models
            options = service.get_filter_options()
            self.available_documents = [
                SpeculationDocument(id=d["id"], title=d["title"])
                for d in options["documents"]
            ]
            self.available_entities = [
                SpeculationEntity(id=e["id"], name=e["name"], type=e["type"])
                for e in options["entities"]
            ]

        except Exception as e:
            logger.error(f"Error loading summary: {e}")
        finally:
            self.is_loading = False

    def toggle_filters(self):
        """Show/hide the filter panel."""
        self.show_filters = not self.show_filters

    def toggle_document(self, doc_id: int):
        """Toggle a document in/out of selection."""
        if doc_id in self.selected_doc_ids:
            self.selected_doc_ids = [d for d in self.selected_doc_ids if d != doc_id]
        else:
            self.selected_doc_ids = self.selected_doc_ids + [doc_id]

    def toggle_entity(self, entity_id: int):
        """Toggle an entity in/out of selection."""
        if entity_id in self.selected_entity_ids:
            self.selected_entity_ids = [
                e for e in self.selected_entity_ids if e != entity_id
            ]
        else:
            self.selected_entity_ids = self.selected_entity_ids + [entity_id]

    def clear_selections(self):
        """Clear all document and entity selections."""
        self.selected_doc_ids = []
        self.selected_entity_ids = []

    def generate_scenarios(self):
        """Generate what-if scenarios."""
        self.is_generating = True
        self.active_tab = "scenarios"
        yield

        try:
            from app.arkham.services.speculation_service import (
                get_speculation_service,
            )

            service = get_speculation_service()
            scenarios = service.generate_what_if_scenarios(
                focus_topic=self.focus_topic if self.focus_topic else None,
                doc_ids=self.selected_doc_ids if self.selected_doc_ids else None,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
            )

            self.scenarios = [
                WhatIfScenario(
                    id=s.get("id", ""),
                    hypothesis=s.get("hypothesis", ""),
                    basis=s.get("basis", ""),
                    evidence_needed=s.get("evidence_needed", []),
                    significance=s.get("significance", "Medium"),
                    significance_explanation=s.get("significance_explanation", ""),
                    investigation_steps=s.get("investigation_steps", []),
                )
                for s in scenarios
            ]

            self.has_results = True

        except Exception as e:
            logger.error(f"Error generating scenarios: {e}")
        finally:
            self.is_generating = False

    def identify_gaps(self):
        """Identify information gaps."""
        self.is_generating = True
        self.active_tab = "gaps"
        yield

        try:
            from app.arkham.services.speculation_service import (
                get_speculation_service,
            )

            service = get_speculation_service()
            gaps = service.identify_gaps(
                doc_ids=self.selected_doc_ids if self.selected_doc_ids else None,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
            )

            self.gaps = [
                InformationGap(
                    id=g.get("id", ""),
                    type=g.get("type", ""),
                    description=g.get("description", ""),
                    importance=g.get("importance", "Medium"),
                    indicators=g.get("indicators", []),
                    suggested_sources=g.get("suggested_sources", []),
                )
                for g in gaps
            ]

            self.has_results = True

        except Exception as e:
            logger.error(f"Error identifying gaps: {e}")
        finally:
            self.is_generating = False

    def generate_questions(self):
        """Generate investigative questions."""
        self.is_generating = True
        self.active_tab = "questions"
        yield

        try:
            from app.arkham.services.speculation_service import (
                get_speculation_service,
            )

            service = get_speculation_service()
            questions = service.generate_investigative_questions(
                doc_ids=self.selected_doc_ids if self.selected_doc_ids else None,
                entity_ids=self.selected_entity_ids
                if self.selected_entity_ids
                else None,
            )

            self.questions = [
                InvestigativeQuestion(
                    id=q.get("id", ""),
                    question=q.get("question", ""),
                    priority=q.get("priority", "Medium"),
                    rationale=q.get("rationale", ""),
                    related_entities=q.get("related_entities", []),
                    potential_sources=q.get("potential_sources", []),
                )
                for q in questions
            ]

            self.has_results = True

        except Exception as e:
            logger.error(f"Error generating questions: {e}")
        finally:
            self.is_generating = False

    def set_focus_topic(self, topic: str):
        self.focus_topic = topic

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    def export_results(self):
        """Export current results to a Markdown file."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"speculation_export_{timestamp}.md"

        content = f"# Speculation Mode Export\n\nGenerated: {timestamp}\n\n"

        if self.focus_topic:
            content += f"**Focus Topic:** {self.focus_topic}\n\n"

        content += "---\n\n"

        # Scenarios
        if self.scenarios:
            content += "## What-If Scenarios\n\n"
            for s in self.scenarios:
                content += f"### Scenario {s.id}: {s.hypothesis}\n"
                content += f"**Significance:** {s.significance}\n\n"
                content += f"**Basis:** {s.basis}\n\n"
                if s.evidence_needed:
                    content += "**Evidence Needed:**\n"
                    for e in s.evidence_needed:
                        content += f"- {e}\n"
                    content += "\n"
                if s.investigation_steps:
                    content += "**Investigation Steps:**\n"
                    for step in s.investigation_steps:
                        content += f"- {step}\n"
                    content += "\n"
                content += "---\n\n"

        # Gaps
        if self.gaps:
            content += "## Information Gaps\n\n"
            for g in self.gaps:
                content += f"### {g.description}\n"
                content += f"**Type:** {g.type} | **Importance:** {g.importance}\n\n"
                if g.indicators:
                    content += "**Indicators:**\n"
                    for i in g.indicators:
                        content += f"- {i}\n"
                    content += "\n"
                if g.suggested_sources:
                    content += "**Suggested Sources:**\n"
                    for s in g.suggested_sources:
                        content += f"- {s}\n"
                    content += "\n"
                content += "---\n\n"

        # Questions
        if self.questions:
            content += "## Investigative Questions\n\n"
            for q in self.questions:
                content += f"### {q.question}\n"
                content += f"**Priority:** {q.priority}\n\n"
                if q.rationale:
                    content += f"**Rationale:** {q.rationale}\n\n"
                if q.related_entities:
                    content += (
                        f"**Related Entities:** {', '.join(q.related_entities)}\n\n"
                    )
                if q.potential_sources:
                    content += "**Potential Sources:**\n"
                    for s in q.potential_sources:
                        content += f"- {s}\n"
                    content += "\n"
                content += "---\n\n"

        return rx.download(
            data=content,
            filename=filename,
        )
