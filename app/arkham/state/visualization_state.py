import reflex as rx
from typing import List, Dict, Any, Optional
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from ..services.visualization_service import (
    get_cluster_map_data,
    get_wordcloud_data,
    get_entity_heatmap_data,
    get_clusters,
    get_doctypes,
)
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL, QDRANT_URL
from app.arkham.services.db.models import (
    Document,
    Chunk,
    Cluster,
    CanonicalEntity,
    EntityRelationship,
)


class VisualizationState(rx.State):
    """State for the visualizations page."""

    view_mode: str = "Cluster Map"
    is_loading: bool = False
    error_message: str = ""

    # Cluster Map Data
    cluster_map_data: List[Dict[str, Any]] = []

    # Word Cloud Data
    wordcloud_image: str = ""
    wordcloud_scope: str = "all"  # "all", "cluster", "doctype"
    wordcloud_filter_id: str = ""
    available_clusters: List[Dict[str, Any]] = []
    available_doctypes: List[str] = []
    # Custom exclusions list - editable by user
    wordcloud_exclusions: List[str] = []
    new_exclusion_word: str = ""

    # Heatmap Data
    heatmap_data: Dict[str, Any] = {"labels": [], "z": []}
    heatmap_top_n: int = 15

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded_heatmap: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if visualization data has been loaded."""
        return bool(self.heatmap_data.get("labels", []))

    @rx.var
    def heatmap_labels(self) -> List[str]:
        """Get labels from heatmap data."""
        return self.heatmap_data.get("labels", [])

    @rx.var
    def cluster_map_figure(self) -> go.Figure:
        """Computed Plotly figure for cluster map."""
        if not self.cluster_map_data:
            return go.Figure()

        df = pd.DataFrame(self.cluster_map_data)

        fig = px.scatter(
            df,
            x="x",
            y="y",
            color="cluster",
            hover_data=["title", "type", "date"],
            title="Semantic Cluster Map",
            template="plotly_dark",
            height=600,
        )

        fig.update_layout(
            xaxis_title="",
            yaxis_title="",
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False),
            legend_title_text="Cluster",
        )

        return fig

    @rx.var
    def heatmap_figure(self) -> go.Figure:
        """Computed Plotly figure for entity heatmap."""
        if not self.heatmap_data or not self.heatmap_data["labels"]:
            return go.Figure()

        # Clean labels: remove newlines and excess whitespace
        labels = [
            label.replace("\n", " ").strip()[:25]
            for label in self.heatmap_data["labels"]
        ]

        fig = go.Figure(
            data=go.Heatmap(
                z=self.heatmap_data["z"],
                x=labels,
                y=labels,
                colorscale="YlOrRd",
                hoverongaps=False,
            )
        )

        fig.update_layout(
            title=dict(text="Entity Co-Occurrence Heatmap", font=dict(size=16)),
            template="plotly_dark",
            height=700,
            xaxis=dict(
                tickangle=-45,
                type="category",  # Force categorical axis - prevents datetime auto-detection
            ),
            yaxis=dict(
                type="category",  # Force categorical axis
            ),
        )

        return fig

    @rx.var
    def cluster_select_items(self) -> List[List[str]]:
        """Returns list of [value, label] for cluster select. Filters out empty values."""
        items = []
        for c in self.available_clusters:
            cluster_id = str(c.get("id", ""))
            cluster_name = c.get("name", "") or f"Cluster {cluster_id}"
            if cluster_id:  # Only include if ID is not empty
                items.append([cluster_id, cluster_name])
        return items

    async def _load_cluster_map_impl(self):
        """Implementation of cluster map loading logic."""
        async with self:
            self.is_loading = True
            self.error_message = ""
        try:
            import asyncio

            data = await asyncio.to_thread(get_cluster_map_data)
            async with self:
                self.cluster_map_data = data
                if not self.cluster_map_data:
                    self.error_message = (
                        "No cluster data available. Run clustering first."
                    )
        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="not_found" if "not found" in str(e).lower() else "default",
                context={"action": "load_cluster_map"},
            )

            toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))
            async with self:
                self.error_message = error_info["user_message"]
        finally:
            async with self:
                self.is_loading = False

    @rx.event(background=True)
    async def load_cluster_map(self):
        """Load data for cluster map."""
        await self._load_cluster_map_impl()

    @rx.event(background=True)
    async def load_wordcloud(self):
        """Load wordcloud image."""
        async with self:
            self.is_loading = True
            self.error_message = ""
        try:
            # Load options if needed
            clusters = get_clusters() if not self.available_clusters else None
            doctypes = get_doctypes() if not self.available_doctypes else None
            image = get_wordcloud_data(
                scope=self.wordcloud_scope,
                filter_id=self.wordcloud_filter_id
                if self.wordcloud_filter_id
                else None,
                custom_exclusions=self.wordcloud_exclusions
                if self.wordcloud_exclusions
                else None,
            )

            async with self:
                if clusters is not None:
                    self.available_clusters = clusters
                if doctypes is not None:
                    # Filter out empty strings to prevent Select.Item errors
                    self.available_doctypes = [
                        dt for dt in doctypes if dt and dt.strip()
                    ]
                self.wordcloud_image = image
                if not self.wordcloud_image:
                    self.error_message = (
                        "No text data available for word cloud generation."
                    )
        except Exception as e:
            from ..utils.error_handler import (
                handle_processing_error,
                format_error_for_ui,
            )
            from ..state.toast_state import ToastState

            error_info = handle_processing_error(
                e,
                error_type="generation_failed"
                if "generation" in str(e).lower()
                else "default",
                context={
                    "action": "generate_wordcloud",
                    "scope": self.wordcloud_scope,
                    "filter_id": self.wordcloud_filter_id,
                },
            )

            toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))
            async with self:
                self.error_message = error_info["user_message"]
        finally:
            async with self:
                self.is_loading = False

    @rx.event(background=True)
    async def load_heatmap(self):
        """Load entity heatmap data."""
        # Skip if already loaded (session cache)
        if self._has_loaded_heatmap and self.heatmap_data.get("labels"):
            return

        async with self:
            self.is_loading = True
            self.error_message = ""
        try:
            data = get_entity_heatmap_data(top_n=self.heatmap_top_n)
            async with self:
                self.heatmap_data = data
                self._has_loaded_heatmap = True  # Mark as loaded for session cache
                if not self.heatmap_data or not self.heatmap_data["labels"]:
                    self.error_message = "No entity relationships found. Process documents with entity extraction enabled."
        except Exception as e:
            from ..utils.error_handler import handle_database_error, format_error_for_ui
            from ..state.toast_state import ToastState

            error_info = handle_database_error(
                e,
                error_type="not_found" if "not found" in str(e).lower() else "default",
                context={"action": "load_entity_heatmap", "top_n": self.heatmap_top_n},
            )

            toast_state = await self.get_state(ToastState)
            async with toast_state:
                toast_state.show_error(format_error_for_ui(error_info))
            async with self:
                self.error_message = error_info["user_message"]
        finally:
            async with self:
                self.is_loading = False

    def refresh_heatmap(self):
        """Force reload heatmap, clearing cache."""
        self._has_loaded_heatmap = False
        return VisualizationState.load_heatmap

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        self.error_message = ""  # Clear error when switching views
        # Don't auto-load - user must click Load/Refresh button

    def set_wordcloud_scope(self, scope: str):
        self.wordcloud_scope = scope
        self.wordcloud_filter_id = ""  # Reset filter when scope changes
        return VisualizationState.load_wordcloud

    def set_wordcloud_filter(self, filter_id: str):
        self.wordcloud_filter_id = filter_id
        return VisualizationState.load_wordcloud

    def set_heatmap_top_n(self, n: list[int | float]):
        self.heatmap_top_n = int(n[0])
        return VisualizationState.load_heatmap

    def set_new_exclusion_word(self, word: str):
        """Set the input field for new exclusion word."""
        self.new_exclusion_word = word

    def add_exclusion(self):
        """Add a word to the exclusions list and regenerate wordcloud."""
        word = self.new_exclusion_word.strip().lower()
        if word and word not in self.wordcloud_exclusions:
            self.wordcloud_exclusions = self.wordcloud_exclusions + [word]
            self.new_exclusion_word = ""
            return VisualizationState.load_wordcloud

    def remove_exclusion(self, word: str):
        """Remove a word from the exclusions list and regenerate wordcloud."""
        self.wordcloud_exclusions = [w for w in self.wordcloud_exclusions if w != word]
        return VisualizationState.load_wordcloud

    @rx.event(background=True)
    async def run_clustering(self):
        """Run clustering directly in background thread."""
        async with self:
            self.is_loading = True
            self.error_message = "Starting clustering analysis..."

        try:
            import asyncio

            # Run clustering in thread to avoid blocking
            async with self:
                self.error_message = "Fetching document vectors from Qdrant..."

            def do_clustering():
                """Execute clustering synchronously."""
                import numpy as np
                import hdbscan
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                from qdrant_client import QdrantClient
                from dotenv import load_dotenv
                from openai import OpenAI
                from collections import defaultdict

                load_dotenv()

                # Database Setup
                engine = create_engine(DATABASE_URL)
                Session = sessionmaker(bind=engine)

                # Import models after engine setup
                from app.arkham.services.db.models import Document, Cluster, Chunk

                # Import LM Studio URL from central config
                from config.settings import LM_STUDIO_URL as LM_URL

                session = Session()

                # Qdrant Setup
                qdrant_client = QdrantClient(url=QDRANT_URL)
                COLLECTION_NAME = "arkham_mirror_hybrid"

                # LLM Setup - use central config URL
                llm_client = OpenAI(base_url=LM_URL, api_key="lm-studio")

                def generate_cluster_name(texts):
                    if not texts:
                        return "Unknown Cluster"
                    context = "\n---\n".join([t[:500] for t in texts[:5]])
                    try:
                        response = llm_client.chat.completions.create(
                            model="local-model",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are a helpful librarian. Read the following document snippets and generate a short, specific topic name (max 5 words) that describes them all. Do not use quotes.",
                                },
                                {
                                    "role": "user",
                                    "content": f"Snippets:\n{context}\n\nTopic Name:",
                                },
                            ],
                            temperature=0.3,
                        )
                        return response.choices[0].message.content.strip()
                    except Exception:
                        return "Unnamed Cluster"

                with Session() as session:
                    try:
                        # Fetch Documents
                        docs = session.query(Document).all()
                        if not docs:
                            return {
                                "success": False,
                                "message": "No documents found to cluster.",
                            }

                        # Fetch Vectors & Compute Centroids
                        doc_vectors = []
                        valid_doc_ids = []

                        # Optimize: Fetch all chunks for these docs in one go
                        doc_ids = [d.id for d in docs]
                        all_chunks = session.query(Chunk).filter(Chunk.doc_id.in_(doc_ids)).all()
                        
                        chunks_by_doc = defaultdict(list)
                        for chunk in all_chunks:
                            chunks_by_doc[chunk.doc_id].append(chunk)

                        for doc in docs:
                            # Get chunks from pre-fetched map
                            chunks = chunks_by_doc.get(doc.id, [])
                            if not chunks:
                                continue

                            chunk_ids = [c.id for c in chunks]
                            points = qdrant_client.retrieve(
                                collection_name=COLLECTION_NAME,
                                ids=chunk_ids,
                                with_vectors=True,
                            )

                            vectors = [p.vector["dense"] for p in points if p.vector]
                            if vectors:
                                centroid = np.mean(vectors, axis=0)
                                doc_vectors.append(centroid)
                                valid_doc_ids.append(doc.id)

                        if not doc_vectors:
                            return {
                                "success": False,
                                "message": "No vectors found in Qdrant.",
                            }

                        X = np.array(doc_vectors)

                        # Run HDBSCAN
                        clusterer = hdbscan.HDBSCAN(
                            min_cluster_size=3, min_samples=2, metric="euclidean"
                        )
                        labels = clusterer.fit_predict(X)

                        # Save Clusters
                        unique_labels = set(labels)
                        num_clusters = len(unique_labels) - (
                            1 if -1 in unique_labels else 0
                        )

                        cluster_map = {}

                        for label in unique_labels:
                            if label == -1:
                                continue

                            cluster = Cluster(
                                project_id=None,
                                label=int(label),
                                name=f"Cluster {label}",
                                size=int(np.sum(labels == label)),
                            )
                            session.add(cluster)
                            session.flush()
                            cluster_map[label] = cluster

                        # Update Documents & Name Clusters
                        cluster_docs_text = {
                            label: [] for label in unique_labels if label != -1
                        }

                        for doc_id, label in zip(valid_doc_ids, labels):
                            doc = session.query(Document).get(doc_id)
                            if label != -1:
                                doc.cluster_id = cluster_map[label].id
                                first_chunk = (
                                    session.query(Chunk)
                                    .filter(Chunk.doc_id == doc.id)
                                    .first()
                                )
                                if first_chunk:
                                    cluster_docs_text[label].append(first_chunk.text)
                            else:
                                doc.cluster_id = None

                        session.commit()

                        # Generate Names with LLM
                        for label, texts in cluster_docs_text.items():
                            name = generate_cluster_name(texts)
                            cluster = cluster_map[label]
                            cluster.name = name

                        session.commit()

                        return {
                            "success": True,
                            "message": f"Clustering complete! Found {num_clusters} clusters from {len(valid_doc_ids)} documents.",
                        }

                    except Exception as e:
                        session.rollback()
                        return {"success": False, "message": str(e)}

            # Run in thread
            result = await asyncio.to_thread(do_clustering)

            if result["success"]:
                async with self:
                    self.error_message = "Clustering complete! Loading cluster map..."

                # Reload cluster map data after successful clustering
                await self._load_cluster_map_impl()

                async with self:
                    if self.cluster_map_data:
                        self.error_message = result["message"]
                    else:
                        self.error_message = result["message"] + " (Refresh to view)"
            else:
                async with self:
                    self.error_message = f"Clustering failed: {result['message']}"

        except Exception as e:
            import logging

            logging.error(f"Failed to run clustering: {e}")

            async with self:
                self.error_message = f"Failed to run clustering: {str(e)}"

        finally:
            async with self:
                self.is_loading = False
