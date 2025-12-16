import logging

logger = logging.getLogger(__name__)

import reflex as rx
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from config.settings import DATABASE_URL


class Fact(BaseModel):
    claim: str
    doc_id: int
    doc_title: str = ""  # Document title for display
    chunk_id: int
    chunk_text: str = ""  # Text excerpt as evidence
    reliability: str  # High/Medium/Low (renamed from confidence)
    category: str


class FactRelation(BaseModel):
    fact_indices: List[int]
    explanation: str
    reliability: str  # Renamed from confidence
    severity: str = ""


class EntityFactAnalysis(BaseModel):
    entity_id: int
    entity_name: str
    total_facts: int
    conflicts: int
    confirmations: int


class FactComparisonState(rx.State):
    """State for Cross-Document Fact Comparison."""

    # Document selection for analysis
    available_documents: List[dict] = []
    selected_doc_ids: List[int] = []
    use_all_documents: bool = True

    # Entity selection for analysis
    available_entities: List[dict] = []
    selected_entity_ids: List[int] = []
    use_top_entities: bool = True  # Default: analyze top 10 by mentions
    entity_search_query: str = ""
    show_entity_selector: bool = False

    # Analysis results
    entity_analyses: List[EntityFactAnalysis] = []
    cached_entity_details: dict = {}  # Store full analysis per entity from corpus run

    # Selected entity detail
    selected_entity_id: Optional[int] = None
    selected_entity_name: str = ""
    facts: List[Fact] = []
    corroborating: List[FactRelation] = []
    conflicting: List[FactRelation] = []
    unique_indices: List[int] = []

    # Summary stats
    total_entities_analyzed: int = 0
    total_facts_found: int = 0
    total_conflicts: int = 0
    total_confirmations: int = 0

    # UI state
    is_loading: bool = False
    is_analyzing_entity: bool = False
    active_tab: str = "overview"
    show_doc_selector: bool = False

    # Modal state - Fact detail
    fact_modal_open: bool = False
    selected_fact_index: int = -1

    # Modal state - Relation detail (corroboration/conflict)
    relation_modal_open: bool = False
    selected_relation_index: int = -1
    selected_relation_type: str = ""  # "corroboration" or "conflict"

    # Modal state - Stats detail
    stats_modal_open: bool = False
    stats_modal_type: str = ""  # "entities", "facts", "confirmations", "conflicts"

    # Table sorting
    sort_column: str = "entity_name"
    sort_ascending: bool = True

    # Cache status
    results_from_cache: bool = False
    cache_timestamp: str = ""  # ISO timestamp of when cache was created
    cache_expires_at: str = ""  # ISO timestamp of when cache expires

    # Modal control methods
    def open_fact_modal(self, index: int):
        """Open fact detail modal."""
        self.fact_modal_open = True
        self.selected_fact_index = index

    def close_fact_modal(self):
        """Close fact detail modal."""
        self.fact_modal_open = False
        self.selected_fact_index = -1

    def open_relation_modal(self, index: int, rel_type: str):
        """Open relation detail modal."""
        self.relation_modal_open = True
        self.selected_relation_index = index
        self.selected_relation_type = rel_type

    def close_relation_modal(self):
        """Close relation detail modal."""
        self.relation_modal_open = False
        self.selected_relation_index = -1
        self.selected_relation_type = ""

    def open_stats_modal(self, modal_type: str):
        """Open stats detail modal."""
        self.stats_modal_open = True
        self.stats_modal_type = modal_type

    def close_stats_modal(self):
        """Close stats detail modal."""
        self.stats_modal_open = False
        self.stats_modal_type = ""

    def set_sort(self, column: str):
        """Set sort column, toggle ascending if same column clicked."""
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True

    @rx.var
    def selected_fact(self) -> Optional[Fact]:
        """Get the currently selected fact for modal."""
        if 0 <= self.selected_fact_index < len(self.facts):
            return self.facts[self.selected_fact_index]
        return None

    @rx.var
    def selected_relation(self) -> Optional[FactRelation]:
        """Get the currently selected relation for modal."""
        if self.selected_relation_type == "corroboration":
            if 0 <= self.selected_relation_index < len(self.corroborating):
                return self.corroborating[self.selected_relation_index]
        elif self.selected_relation_type == "conflict":
            if 0 <= self.selected_relation_index < len(self.conflicting):
                return self.conflicting[self.selected_relation_index]
        return None

    @rx.var
    def sorted_entity_analyses(self) -> List[EntityFactAnalysis]:
        """Get sorted entity analyses based on current sort settings."""
        analyses = list(self.entity_analyses)
        if not analyses:
            return []

        # Sort based on column
        if self.sort_column == "entity_name":
            analyses.sort(
                key=lambda a: a.entity_name.lower(), reverse=not self.sort_ascending
            )
        elif self.sort_column == "total_facts":
            analyses.sort(key=lambda a: a.total_facts, reverse=not self.sort_ascending)
        elif self.sort_column == "confirmations":
            analyses.sort(
                key=lambda a: a.confirmations, reverse=not self.sort_ascending
            )
        elif self.sort_column == "conflicts":
            analyses.sort(key=lambda a: a.conflicts, reverse=not self.sort_ascending)

        return analyses

    @rx.var
    def selected_doc_ids_str(self) -> List[str]:
        """Get selected doc IDs as strings."""
        return [str(d) for d in self.selected_doc_ids]

    @rx.var
    def selected_entity_ids_str(self) -> List[str]:
        """Get selected entity IDs as strings."""
        return [str(e) for e in self.selected_entity_ids]

    @rx.var
    def selection_summary(self) -> str:
        """Summary of document selection."""
        if self.use_all_documents:
            return f"All {len(self.available_documents)} documents"
        elif len(self.selected_doc_ids) == 0:
            return "No documents selected"
        elif len(self.selected_doc_ids) == 1:
            return "1 document selected"
        else:
            return f"{len(self.selected_doc_ids)} documents selected"

    @rx.var
    def entity_selection_summary(self) -> str:
        """Summary of entity selection."""
        if self.use_top_entities:
            return "Top 10 entities by mentions"
        elif len(self.selected_entity_ids) == 0:
            return "No entities selected"
        elif len(self.selected_entity_ids) == 1:
            return "1 entity selected"
        else:
            return f"{len(self.selected_entity_ids)} entities selected"

    @rx.var
    def document_options(self) -> List[dict]:
        """Format documents for checkbox list."""
        return [
            {"id": str(doc["id"]), "label": f"{doc['title']} ({doc['doc_type']})"}
            for doc in self.available_documents
        ]

    @rx.var
    def filtered_entity_options(self) -> List[dict]:
        """Format and filter entities for display."""
        query = self.entity_search_query.lower().strip()
        entities = self.available_entities

        if query:
            entities = [
                e
                for e in entities
                if query in e.get("name", "").lower()
                or query in e.get("type", "").lower()
            ]

        # Limit to 50 for performance
        return [
            {
                "id": str(e["id"]),
                "name": e["name"],
                "type": e.get("type", ""),
                "mentions": e.get("mentions", 0),
            }
            for e in entities[:50]
        ]

    def load_documents(self):
        """Load available documents for selection."""
        try:
            from app.arkham.services.anomaly_service import get_all_documents

            self.available_documents = get_all_documents()
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            self.available_documents = []

    def load_entities(self):
        """Load available entities for selection."""
        try:
            from app.arkham.services.db.models import CanonicalEntity
            from sqlalchemy import create_engine, desc
            from sqlalchemy.orm import sessionmaker

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.total_mentions > 0)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(500)  # Reasonable limit for UI
                    .all()
                )
                self.available_entities = [
                    {
                        "id": e.id,
                        "name": e.canonical_name,
                        "type": e.label or "",
                        "mentions": e.total_mentions or 0,
                    }
                    for e in entities
                ]
        except Exception as e:
            logger.error(f"Error loading entities: {e}")
            self.available_entities = []

    def toggle_document(self, doc_id_str: str):
        """Toggle document in selection."""
        try:
            doc_id = int(doc_id_str)
            if doc_id in self.selected_doc_ids:
                self.selected_doc_ids = [
                    d for d in self.selected_doc_ids if d != doc_id
                ]
            else:
                self.selected_doc_ids = self.selected_doc_ids + [doc_id]

            if self.selected_doc_ids:
                self.use_all_documents = False
        except ValueError:
            pass

    def toggle_entity(self, entity_id_str: str):
        """Toggle entity in selection."""
        try:
            entity_id = int(entity_id_str)
            if entity_id in self.selected_entity_ids:
                self.selected_entity_ids = [
                    e for e in self.selected_entity_ids if e != entity_id
                ]
            else:
                self.selected_entity_ids = self.selected_entity_ids + [entity_id]

            if self.selected_entity_ids:
                self.use_top_entities = False
        except ValueError:
            pass

    def select_all_documents(self):
        """Select all available documents."""
        self.selected_doc_ids = [doc["id"] for doc in self.available_documents]
        self.use_all_documents = False

    def clear_doc_selection(self):
        """Clear document selection and use all documents."""
        self.selected_doc_ids = []
        self.use_all_documents = True

    def clear_entity_selection(self):
        """Clear entity selection and use top entities."""
        self.selected_entity_ids = []
        self.use_top_entities = True
        self.entity_search_query = ""

    def toggle_doc_selector(self):
        """Toggle document selector visibility."""
        self.show_doc_selector = not self.show_doc_selector
        if self.show_doc_selector and not self.available_documents:
            self.load_documents()

    def toggle_entity_selector(self):
        """Toggle entity selector visibility."""
        self.show_entity_selector = not self.show_entity_selector
        if self.show_entity_selector and not self.available_entities:
            self.load_entities()

    def set_entity_search(self, query: str):
        """Update entity search query."""
        self.entity_search_query = query

    @rx.event(background=True)
    async def run_corpus_analysis(self, force_refresh: bool = False):
        """Analyze selected or top entities across the corpus."""
        async with self:
            self.is_loading = True

        try:
            from app.arkham.services.fact_comparison_service import (
                get_fact_comparison_service,
            )

            service = get_fact_comparison_service()
            # Pass use_cache based on force_refresh
            use_cache = not force_refresh

            # Determine which documents to analyze
            doc_ids = None if self.use_all_documents else self.selected_doc_ids

            # Determine which entities to analyze
            entity_ids = None if self.use_top_entities else self.selected_entity_ids

            # Adjust limit: if user selected specific entities, analyze all of them
            limit = len(self.selected_entity_ids) if entity_ids else 10

            result = await asyncio.to_thread(
                service.run_corpus_analysis,
                limit=limit,
                use_cache=use_cache,
                doc_ids_filter=doc_ids,
                entity_ids_filter=entity_ids,
            )

            analyses = [
                EntityFactAnalysis(
                    entity_id=e["entity_id"],
                    entity_name=e["entity_name"],
                    total_facts=e["total_facts"],
                    conflicts=e["conflicts"],
                    confirmations=e["confirmations"],
                )
                for e in result.get("entities", [])
            ]

            summary = result.get("summary", {})

            async with self:
                self.entity_analyses = analyses
                self.cached_entity_details = result.get("entity_details", {})
                self.total_entities_analyzed = summary.get("entities_analyzed", 0)
                self.total_facts_found = summary.get("total_facts", 0)
                self.total_conflicts = summary.get("total_conflicts", 0)
                self.total_confirmations = summary.get("total_confirmations", 0)
                # Cache status
                self.results_from_cache = result.get("from_cache", False)
                self.cache_timestamp = result.get("cached_at", "")
                self.cache_expires_at = result.get("expires_at", "")
                self.is_loading = False

        except Exception as e:
            logger.error(f"Error in corpus analysis: {e}")
            async with self:
                self.is_loading = False
                self.results_from_cache = False
                self.cache_timestamp = ""
                self.cache_expires_at = ""

    @rx.event(background=True)
    async def analyze_entity(self, entity_id: int, entity_name: str):
        """Show cached facts for a specific entity (from corpus analysis)."""
        async with self:
            self.selected_entity_id = entity_id
            self.selected_entity_name = entity_name
            self.is_analyzing_entity = True
            self.active_tab = "detail"

        try:
            # First, check if we have cached results from the corpus analysis
            entity_id_str = str(entity_id)
            if entity_id_str in self.cached_entity_details:
                # Use cached results - no LLM call needed!
                result = self.cached_entity_details[entity_id_str]
            else:
                # Fall back to fresh analysis if not in cache
                from app.arkham.services.fact_comparison_service import (
                    get_fact_comparison_service,
                )

                service = get_fact_comparison_service()
                result = await asyncio.to_thread(
                    service.analyze_entity_facts, entity_id
                )

            # Parse facts
            facts = [
                Fact(
                    claim=f.get("claim", ""),
                    doc_id=f.get("doc_id", 0),
                    doc_title=f.get("doc_title", ""),
                    chunk_id=f.get("chunk_id", 0),
                    chunk_text=f.get("chunk_text", ""),
                    reliability=f.get("reliability", f.get("confidence", "Medium")),
                    category=f.get("category", "Other"),
                )
                for f in result.get("facts", [])
            ]

            # Parse comparison
            comparison = result.get("comparison", {})

            corroborating = [
                FactRelation(
                    fact_indices=c.get("facts", []),
                    explanation=c.get("explanation", ""),
                    reliability=c.get("reliability", c.get("confidence", "Medium")),
                    severity="",
                )
                for c in comparison.get("corroborating", [])
            ]

            conflicting = [
                FactRelation(
                    fact_indices=c.get("facts", []),
                    explanation=c.get("explanation", ""),
                    reliability=c.get("reliability", c.get("confidence", "Medium")),
                    severity=c.get("severity", "Medium"),
                )
                for c in comparison.get("conflicting", [])
            ]

            unique_indices = comparison.get("unique", [])

            async with self:
                self.facts = facts
                self.corroborating = corroborating
                self.conflicting = conflicting
                self.unique_indices = unique_indices

        except Exception as e:
            logger.error(f"Error analyzing entity: {e}")
        finally:
            async with self:
                self.is_analyzing_entity = False

    def clear_selection(self):
        self.selected_entity_id = None
        self.selected_entity_name = ""
        self.facts = []
        self.corroborating = []
        self.conflicting = []
        self.unique_indices = []
        self.active_tab = "overview"

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    @rx.var
    def has_selection(self) -> bool:
        return self.selected_entity_id is not None

    @rx.var
    def facts_count(self) -> int:
        return len(self.facts)

    @rx.var
    def conflicts_count(self) -> int:
        return len(self.conflicting)

    @rx.var
    def confirmations_count(self) -> int:
        return len(self.corroborating)

    # Aggregated data for Overview stats modals
    @rx.var
    def all_facts_aggregated(self) -> List[dict]:
        """Get all facts across all analyzed entities for the stats modal."""
        all_facts = []
        for entity_id, details in self.cached_entity_details.items():
            entity_name = ""
            # Find entity name from entity_analyses
            for ea in self.entity_analyses:
                if str(ea.entity_id) == entity_id:
                    entity_name = ea.entity_name
                    break
            for f in details.get("facts", []):
                all_facts.append(
                    {
                        "claim": f.get("claim", ""),
                        "doc_id": f.get("doc_id", 0),
                        "doc_title": f.get("doc_title", ""),
                        "category": f.get("category", "Other"),
                        "reliability": f.get(
                            "reliability", f.get("confidence", "Medium")
                        ),
                        "entity_name": entity_name,
                    }
                )
        return all_facts

    @rx.var
    def all_corroborations_aggregated(self) -> List[dict]:
        """Get all corroborations across all analyzed entities."""
        all_corroborations = []
        for entity_id, details in self.cached_entity_details.items():
            entity_name = ""
            for ea in self.entity_analyses:
                if str(ea.entity_id) == entity_id:
                    entity_name = ea.entity_name
                    break
            comparison = details.get("comparison", {})
            for c in comparison.get("corroborating", []):
                all_corroborations.append(
                    {
                        "explanation": c.get("explanation", ""),
                        "fact_indices": c.get("facts", []),
                        "reliability": c.get(
                            "reliability", c.get("confidence", "Medium")
                        ),
                        "entity_name": entity_name,
                    }
                )
        return all_corroborations

    @rx.var
    def all_conflicts_aggregated(self) -> List[dict]:
        """Get all conflicts across all analyzed entities."""
        all_conflicts = []
        for entity_id, details in self.cached_entity_details.items():
            entity_name = ""
            for ea in self.entity_analyses:
                if str(ea.entity_id) == entity_id:
                    entity_name = ea.entity_name
                    break
            comparison = details.get("comparison", {})
            for c in comparison.get("conflicting", []):
                all_conflicts.append(
                    {
                        "explanation": c.get("explanation", ""),
                        "fact_indices": c.get("facts", []),
                        "severity": c.get("severity", "Medium"),
                        "entity_name": entity_name,
                    }
                )
        return all_conflicts

    def get_fact_by_index(self, index: int) -> Optional[Fact]:
        """Get a specific fact by index from current entity's facts."""
        if 0 <= index < len(self.facts):
            return self.facts[index]
        return None

    @rx.var
    def related_facts_for_modal(self) -> List[dict]:
        """Get the facts related to the selected relation for display in modal."""
        if not self.selected_relation:
            return []

        result = []
        for idx in self.selected_relation.fact_indices:
            if 0 <= idx < len(self.facts):
                fact = self.facts[idx]
                result.append(
                    {
                        "index": idx,
                        "claim": fact.claim,
                        "doc_id": fact.doc_id,
                        "doc_title": fact.doc_title,
                        "category": fact.category,
                        "reliability": fact.reliability,
                        "chunk_text": fact.chunk_text,
                    }
                )
        return result
