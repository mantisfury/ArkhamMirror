import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import os
import numpy as np
import umap.umap_ as umap
from dotenv import load_dotenv
from backend.db.models import Document, Chunk, TimelineEvent, DateMention
from qdrant_client import QdrantClient
import re
from datetime import datetime

load_dotenv()
st.set_page_config(layout="wide", page_title="Arkham Atlas")

# --- Setup ---
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
COLLECTION_NAME = "arkham_mirror_hybrid"

st.title("🗺️ Arkham Atlas: Visual Intelligence")

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Filters")

    # Project Filter (Placeholder for now as Project model isn't fully integrated in UI yet)
    # selected_project = st.selectbox("Select Project", ["All Projects"])

    view_mode = st.radio("View Mode", ["Cluster Map", "Timeline Analysis", "Word Clouds", "Entity Heatmap"])


# --- Helper Functions ---
def get_doc_vectors(session):
    """Fetches document centroids for visualization."""
    docs = session.query(Document).all()
    if not docs:
        return [], []

    doc_data = []
    vectors = []

    # This is heavy for large datasets, but okay for <10k docs locally
    # Ideally we cache these centroids in the DB
    for doc in docs:
        # Get chunks to compute centroid
        chunks = session.query(Chunk).filter(Chunk.doc_id == doc.id).all()
        if not chunks:
            continue

        chunk_ids = [c.id for c in chunks]
        points = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME, ids=chunk_ids, with_vectors=True
        )
        chunk_vecs = [p.vector["dense"] for p in points if p.vector]
        if chunk_vecs:
            centroid = np.mean(chunk_vecs, axis=0)

            cluster_name = "Unclustered"
            if hasattr(doc, "cluster_id") and doc.cluster_id:
                from backend.db.models import Cluster

                cluster = session.query(Cluster).get(doc.cluster_id)
                if cluster:
                    cluster_name = cluster.name

            doc_data.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "cluster": cluster_name,
                    "date": doc.created_at,  # Fallback if no extracted date
                    "type": doc.doc_type,
                }
            )
            vectors.append(centroid)

    return doc_data, np.array(vectors)


def extract_dates_from_text(text):
    """Simple regex to find years/dates in text for timeline."""
    # Look for YYYY patterns between 1990 and 2030
    matches = re.findall(r"\b(199\d|20[0-2]\d)\b", text)
    return [int(m) for m in matches]


# --- Main Logic ---
session = Session()
try:
    if view_mode == "Cluster Map":
        st.subheader("🌌 Semantic Cluster Map")
        st.caption(
            "Each dot is a document. Closer dots are semantically similar. Colors represent discovered topics."
        )

        with st.spinner("Computing map projection..."):
            doc_data, X = get_doc_vectors(session)

            if len(doc_data) > 2:
                # Reduce to 2D with UMAP
                reducer = umap.UMAP(n_components=2, random_state=42)
                embedding = reducer.fit_transform(X)

                df = pd.DataFrame(doc_data)
                df["x"] = embedding[:, 0]

            else:
                st.warning("Not enough documents to visualize. Need at least 3.")

    elif view_mode == "Timeline Analysis":
        st.subheader("📅 Temporal Investigation")
        st.caption(
            "Interactive timeline with extracted events, dates, and gap analysis."
        )

        # Sub-view selector
        timeline_view = st.radio(
            "Timeline View",
            ["Event Timeline", "Date Distribution", "Gap Analysis"],
            horizontal=True
        )

        if timeline_view == "Event Timeline":
            st.markdown("### Chronological Event Timeline")

            # Filter controls
            col1, col2, col3 = st.columns(3)
            with col1:
                event_type_filter = st.multiselect(
                    "Event Types",
                    ["meeting", "transaction", "communication", "deadline", "incident", "other"],
                    default=["meeting", "transaction", "communication", "deadline", "incident", "other"]
                )
            with col2:
                min_confidence = st.slider("Minimum Confidence", 0.0, 1.0, 0.3, 0.1)
            with col3:
                max_events = st.number_input("Max Events to Display", 10, 500, 100, 10)

            # Fetch events from database
            events_query = session.query(TimelineEvent, Document).join(
                Document, TimelineEvent.doc_id == Document.id
            ).filter(
                TimelineEvent.event_type.in_(event_type_filter),
                TimelineEvent.confidence >= min_confidence,
                TimelineEvent.event_date.isnot(None)
            ).order_by(TimelineEvent.event_date.desc()).limit(max_events)

            events = events_query.all()

            if events:
                # Prepare data for visualization
                event_data = []
                for event, doc in events:
                    event_data.append({
                        "date": event.event_date,
                        "description": event.description[:100] + ("..." if len(event.description) > 100 else ""),
                        "type": event.event_type,
                        "document": doc.title or f"Doc #{doc.id}",
                        "confidence": event.confidence,
                        "precision": event.date_precision,
                        "doc_id": doc.id,
                        "event_id": event.id
                    })

                df_events = pd.DataFrame(event_data)

                # Interactive timeline using Plotly
                fig = px.scatter(
                    df_events,
                    x="date",
                    y="type",
                    color="type",
                    size="confidence",
                    hover_data=["description", "document", "confidence", "precision"],
                    title="Event Timeline",
                    template="plotly_dark",
                    height=600,
                    size_max=20
                )

                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Event Type",
                    showlegend=True,
                    hovermode="closest"
                )

                st.plotly_chart(fig, use_container_width=True)

                # Event table
                st.markdown("### Event Details")
                display_df = df_events[["date", "type", "description", "document", "confidence"]].copy()
                display_df["date"] = pd.to_datetime(display_df["date"]).dt.strftime('%Y-%m-%d')
                display_df["confidence"] = display_df["confidence"].apply(lambda x: f"{x:.2f}")

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )

            else:
                st.warning("No timeline events found. Process documents to extract events automatically.")
                st.info("💡 Events are extracted during document processing. Upload documents and wait for processing to complete.")

        elif timeline_view == "Date Distribution":
            st.markdown("### Date Mentions Distribution")

            # Fetch date mentions
            date_mentions = session.query(DateMention).filter(
                DateMention.parsed_date.isnot(None)
            ).all()

            if date_mentions:
                dates = [dm.parsed_date for dm in date_mentions if dm.parsed_date]
                years = [d.year for d in dates]

                # Histogram of years
                fig_hist = px.histogram(
                    x=years,
                    nbins=min(50, len(set(years))),
                    title="Date Mentions by Year",
                    labels={"x": "Year", "y": "Frequency"},
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig_hist, use_container_width=True)

                # Stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Date Mentions", len(date_mentions))
                with col2:
                    st.metric("Earliest Date", min(dates).strftime("%Y-%m-%d"))
                with col3:
                    st.metric("Latest Date", max(dates).strftime("%Y-%m-%d"))

            else:
                st.warning("No date mentions found. Process documents to extract dates automatically.")

        elif timeline_view == "Gap Analysis":
            st.markdown("### Timeline Gap Detection")
            st.caption("Identify suspicious gaps in the timeline where events may be missing.")

            gap_threshold = st.slider("Gap Threshold (days)", 7, 365, 30, 7)

            # Fetch events with dates
            events = session.query(TimelineEvent).filter(
                TimelineEvent.event_date.isnot(None)
            ).order_by(TimelineEvent.event_date).all()

            if len(events) >= 2:
                # Calculate gaps
                gaps = []
                for i in range(len(events) - 1):
                    current = events[i]
                    next_event = events[i + 1]

                    gap_days = (next_event.event_date - current.event_date).days

                    if gap_days > gap_threshold:
                        gaps.append({
                            "start_date": current.event_date,
                            "end_date": next_event.event_date,
                            "duration_days": gap_days,
                            "before_event": current.description[:80] + "...",
                            "after_event": next_event.description[:80] + "..."
                        })

                if gaps:
                    st.warning(f"⚠️ Found {len(gaps)} suspicious gap(s) in timeline")

                    # Display gaps
                    for idx, gap in enumerate(gaps, 1):
                        with st.expander(f"Gap #{idx}: {gap['duration_days']} days ({gap['start_date'].strftime('%Y-%m-%d')} → {gap['end_date'].strftime('%Y-%m-%d')})"):
                            st.markdown(f"**Before:** {gap['before_event']}")
                            st.markdown(f"**After:** {gap['after_event']}")
                            st.markdown(f"**Duration:** {gap['duration_days']} days")

                    # Visualization
                    gap_df = pd.DataFrame(gaps)
                    fig = px.timeline(
                        gap_df,
                        x_start="start_date",
                        x_end="end_date",
                        y=[f"Gap {i+1}" for i in range(len(gaps))],
                        title="Timeline Gaps Visualization",
                        template="plotly_dark",
                        height=max(300, len(gaps) * 50)
                    )
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.success(f"✅ No significant gaps found (threshold: {gap_threshold} days)")

            else:
                st.info("Not enough timeline events to perform gap analysis. Need at least 2 events with dates.")

    elif view_mode == "Word Clouds":
        st.subheader("☁️ Word Frequency Analysis")
        st.caption("Visual representation of most frequent terms across documents or clusters.")

        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        from collections import Counter
        import string

        # Get scope filter
        scope = st.radio("Scope", ["All Documents", "By Cluster", "By Document Type"])

        def generate_wordcloud_text(chunks):
            """Generate text corpus from chunks, removing stopwords and noise."""
            from spacy.lang.en.stop_words import STOP_WORDS

            text = " ".join([c.text.lower() for c in chunks])

            # Remove punctuation and stopwords
            words = [
                word
                for word in text.split()
                if word not in STOP_WORDS and word not in string.punctuation and len(word) > 2
            ]

            return " ".join(words)

        with st.spinner("Generating word cloud..."):
            if scope == "All Documents":
                # Sample chunks (all would be too heavy)
                chunks = session.query(Chunk).limit(1000).all()
                text = generate_wordcloud_text(chunks)

                if text:
                    wordcloud = WordCloud(
                        width=1200,
                        height=600,
                        background_color="white",
                        colormap="viridis",
                        max_words=100,
                    ).generate(text)

                    fig, ax = plt.subplots(figsize=(15, 8))
                    ax.imshow(wordcloud, interpolation="bilinear")
                    ax.axis("off")
                    st.pyplot(fig)

            elif scope == "By Cluster":
                from backend.db.models import Cluster

                clusters = session.query(Cluster).all()

                if not clusters:
                    st.warning("No clusters found. Run clustering first.")
                else:
                    for cluster in clusters[:5]:  # Limit to top 5
                        st.markdown(f"### {cluster.name}")

                        # Get docs in cluster
                        docs = session.query(Document).filter_by(cluster_id=cluster.id).all()
                        doc_ids = [d.id for d in docs]

                        if doc_ids:
                            chunks = session.query(Chunk).filter(Chunk.doc_id.in_(doc_ids)).limit(500).all()
                            text = generate_wordcloud_text(chunks)

                            if text:
                                wordcloud = WordCloud(
                                    width=800,
                                    height=400,
                                    background_color="white",
                                    colormap="plasma",
                                    max_words=50,
                                ).generate(text)

                                fig, ax = plt.subplots(figsize=(10, 5))
                                ax.imshow(wordcloud, interpolation="bilinear")
                                ax.axis("off")
                                st.pyplot(fig)

            elif scope == "By Document Type":
                doc_types = session.query(Document.doc_type).distinct().all()
                doc_types = [dt[0] for dt in doc_types if dt[0]]

                for doc_type in doc_types:
                    st.markdown(f"### {doc_type}")

                    docs = session.query(Document).filter_by(doc_type=doc_type).all()
                    doc_ids = [d.id for d in docs]

                    if doc_ids:
                        chunks = session.query(Chunk).filter(Chunk.doc_id.in_(doc_ids)).limit(500).all()
                        text = generate_wordcloud_text(chunks)

                        if text:
                            wordcloud = WordCloud(
                                width=800,
                                height=400,
                                background_color="white",
                                colormap="coolwarm",
                                max_words=50,
                            ).generate(text)

                            fig, ax = plt.subplots(figsize=(10, 5))
                            ax.imshow(wordcloud, interpolation="bilinear")
                            ax.axis("off")
                            st.pyplot(fig)

    elif view_mode == "Entity Heatmap":
        st.subheader("🔥 Entity Co-Occurrence Heatmap")
        st.caption("Shows which entities (people, organizations, locations) frequently appear together.")

        from backend.db.models import CanonicalEntity, EntityRelationship
        import seaborn as sns

        # Get top N entities
        top_n = st.slider("Number of entities to display", 5, 30, 15)

        with st.spinner("Building entity co-occurrence matrix..."):
            # Get top entities by total mentions
            top_entities = (
                session.query(CanonicalEntity)
                .order_by(CanonicalEntity.total_mentions.desc())
                .limit(top_n)
                .all()
            )

            if not top_entities:
                st.warning("No entities found. Process documents first.")
            else:
                entity_ids = [e.id for e in top_entities]
                entity_names = {e.id: e.canonical_name for e in top_entities}

                # Build co-occurrence matrix
                matrix = np.zeros((top_n, top_n))

                relationships = (
                    session.query(EntityRelationship)
                    .filter(
                        EntityRelationship.entity1_id.in_(entity_ids),
                        EntityRelationship.entity2_id.in_(entity_ids),
                    )
                    .all()
                )

                for rel in relationships:
                    if rel.entity1_id in entity_names and rel.entity2_id in entity_names:
                        idx1 = entity_ids.index(rel.entity1_id)
                        idx2 = entity_ids.index(rel.entity2_id)
                        matrix[idx1, idx2] = rel.strength
                        matrix[idx2, idx1] = rel.strength  # Symmetric

                # Create DataFrame for heatmap
                labels = [entity_names[eid][:20] for eid in entity_ids]  # Truncate long names
                df_matrix = pd.DataFrame(matrix, index=labels, columns=labels)

                # Plot heatmap
                fig, ax = plt.subplots(figsize=(12, 10))
                sns.heatmap(
                    df_matrix,
                    annot=True,
                    fmt=".0f",
                    cmap="YlOrRd",
                    linewidths=0.5,
                    ax=ax,
                    cbar_kws={"label": "Co-occurrence Count"},
                )
                ax.set_title("Entity Co-Occurrence Heatmap")
                plt.xticks(rotation=45, ha="right")
                plt.yticks(rotation=0)
                plt.tight_layout()
                st.pyplot(fig)

                # Entity network stats
                st.markdown("---")
                st.subheader("Top Connected Entities")

                connection_counts = matrix.sum(axis=1)
                connection_df = pd.DataFrame(
                    {
                        "Entity": labels,
                        "Total Connections": connection_counts.astype(int),
                    }
                ).sort_values("Total Connections", ascending=False)

                st.dataframe(connection_df, use_container_width=True)

finally:
    session.close()
