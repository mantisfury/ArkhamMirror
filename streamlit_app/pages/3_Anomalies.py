import streamlit as st
import os
import sys
import pandas as pd

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from backend.db.models import Anomaly, Chunk, Document, Entity
from backend.embedding_services import embed_hybrid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from openai import OpenAI
from backend.utils.security_utils import sanitize_for_llm

load_dotenv()
st.set_page_config(layout="wide", page_title="Investigation & Anomalies")

# --- Setup ---
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))

COLLECTION_NAME = "arkham_mirror_hybrid"
llm_client = OpenAI(base_url=os.getenv("LM_STUDIO_URL"), api_key="lm-studio")

# Initialize Chat State
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "I am your forensic assistant. Ask me about specific files, anomalies, or the entire dataset.",
        }
    ]
if "chat_doc_id" not in st.session_state:
    st.session_state.chat_doc_id = None


# --- Helper Functions ---
def reconstruct_full_text(doc_id):
    """Reconstructs full text from overlapping chunks using chunk_index."""
    session = Session()
    try:
        chunks = (
            session.query(Chunk)
            .filter(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        if not chunks:
            return ""

        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        full_text = ""
        current_pos = 0

        for c in sorted_chunks:
            start = c.chunk_index
            end = start + len(c.text)

            if start >= current_pos:
                # Gap or contiguous
                full_text += c.text
                current_pos = end
            else:
                # Overlap
                overlap_len = current_pos - start
                if overlap_len < len(c.text):
                    full_text += c.text[overlap_len:]
                    current_pos = end

        return full_text
    finally:
        session.close()


def get_relevant_context(query, doc_id=None):
    """Retrieves relevant chunks and anomaly info based on the query."""
    context_parts = []

    # 1. Vector Search (RAG)
    try:
        q_vecs = embed_hybrid(query)

        search_filter = None
        if doc_id:
            search_filter = Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            )

        hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=q_vecs["dense"],
            using="dense",
            query_filter=search_filter,
            limit=150,
        ).points

        if hits:
            context_parts.append("### Relevant Text Segments:")
            for hit in hits:
                # Fetch doc title for context
                meta = hit.payload
                # Include Chunk ID and Document Title for citation
                doc_title = "Unknown Document"
                if "doc_id" in meta:
                    session = Session()
                    try:
                        doc = session.query(Document).get(meta["doc_id"])
                        if doc:
                            doc_title = doc.title
                    finally:
                        session.close()

                context_parts.append(
                    f"- [Source: {doc_title} | Chunk ID: {hit.id}] {meta.get('text', '')}"
                )
    except Exception as e:
        context_parts.append(f"Error searching vectors: {e}")

    # 2. Anomaly Context (if keyword detected)
    if (
        "anomal" in query.lower()
        or "outlier" in query.lower()
        or "suspicious" in query.lower()
    ):
        session = Session()
        try:
            # Get general stats
            count = session.query(Anomaly).count()
            context_parts.append(
                f"\n### Anomaly Data:\nTotal Anomalies Detected: {count}"
            )

            # Get top anomalies relevant to the query?
            # For now, just get the top 5 most severe anomalies globally or for the doc
            q = (
                session.query(Anomaly, Chunk)
                .join(Chunk, Anomaly.chunk_id == Chunk.id)
                .order_by(Anomaly.score.desc())
            )
            if doc_id:
                q = q.filter(Chunk.doc_id == doc_id)

            top_anoms = q.limit(5).all()
            if top_anoms:
                context_parts.append("Top Severity Anomalies:")
                for a, c in top_anoms:
                    context_parts.append(
                        f"- Score {a.score:.2f}: {a.reason} (Chunk ID: {c.id})"
                    )
        finally:
            session.close()

    return "\n\n".join(context_parts)


# --- Main Layout ---
st.title("🕵️ Investigation & Anomalies")

# Adjusted layout to give more space to the document viewer
col_context, col_chat = st.columns([1, 1])

with col_context:
    tab_anoms, tab_files = st.tabs(["⚠️ Anomalies", "📂 Files & Viewer"])

    with tab_anoms:
        st.caption("Statistical outliers detected by Isolation Forest.")
        session = Session()
        try:
            anomalies = (
                session.query(Anomaly, Chunk, Document)
                .join(Chunk, Anomaly.chunk_id == Chunk.id)
                .join(Document, Chunk.doc_id == Document.id)
                .order_by(Anomaly.score.desc())
                .limit(50)
                .all()
            )

            if not anomalies:
                st.info("No anomalies detected.")
            else:
                for anom, chunk, doc in anomalies:
                    with st.expander(f"{anom.score:.2f} | {doc.title}"):
                        st.caption(f"Reason: {anom.reason}")
                        st.text(chunk.text[:200] + "...")
                        if st.button("Chat about this", key=f"chat_anom_{anom.id}"):
                            st.session_state.chat_doc_id = doc.id
                            st.session_state.messages.append(
                                {
                                    "role": "user",
                                    "content": f"Tell me about the anomaly in {doc.title} (Score: {anom.score:.2f})",
                                }
                            )
                            st.rerun()
        finally:
            session.close()

    with tab_files:
        st.caption("Select a file to focus the chat context and view its content.")
        session = Session()
        try:
            docs = session.query(Document).order_by(Document.created_at.desc()).all()
            if docs:
                doc_options = {f"{d.title} (ID: {d.id})": d.id for d in docs}
                doc_options["All Files (Global Context)"] = None

                # Find current index
                current_idx = 0
                if st.session_state.chat_doc_id:
                    # Try to find the matching key
                    for i, (k, v) in enumerate(doc_options.items()):
                        if v == st.session_state.chat_doc_id:
                            current_idx = i
                            break

                selected_label = st.selectbox(
                    "Active Context", list(doc_options.keys()), index=current_idx
                )
                st.session_state.chat_doc_id = doc_options[selected_label]

                if st.session_state.chat_doc_id:
                    # --- Document Viewer ---
                    st.divider()
                    st.markdown(f"**Viewing: {selected_label}**")

                    # Fetch full text
                    full_text = reconstruct_full_text(st.session_state.chat_doc_id)

                    # Display in a scrollable container
                    with st.container(height=600):
                        st.markdown(full_text)
                else:
                    st.info(
                        "Searching across ALL files. Select a specific file to view its content."
                    )
            else:
                st.warning("No files found.")
        finally:
            session.close()

with col_chat:
    # Chat Header
    c_header, c_stop = st.columns([4, 1])
    with c_header:
        if st.session_state.chat_doc_id:
            st.subheader(f"💬 Chatting with: Document {st.session_state.chat_doc_id}")
        else:
            st.subheader("💬 Global Investigation Chat")
    with c_stop:
        if st.button("🛑 Stop", help="Stop the current generation"):
            st.stop()

    # Display Messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Ask a question..."):
        # 1. User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Assistant Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Retrieve Context
                context_text = get_relevant_context(
                    prompt, st.session_state.chat_doc_id
                )

                # System Prompt
                system_msg = (
                    "You are an expert forensic investigator analyzing a database of leaked documents. "
                    "Your goal is to answer the user's questions accurately based ONLY on the provided context snippets. "
                    "CRITICAL INSTRUCTION: When you cite information, you MUST include BOTH the Document Title and the Chunk ID in your citation. "
                    "Format your citations exactly like this: [Source: Document Title | Chunk ID: 123]. "
                    "Do not refer to 'Chunk ID' alone. Always attribute the source document."
                    "\n\n"
                    "If the answer is not in the context, say 'I cannot find that information in the provided documents.'"
                )

                messages = [
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": f"Context:\n{sanitize_for_llm(context_text)}\n\nQuestion: {sanitize_for_llm(prompt)}",
                    },
                ]

                try:
                    stream = llm_client.chat.completions.create(
                        model="local-model",
                        messages=messages,
                        temperature=0.3,
                        stream=True,
                    )
                    response = st.write_stream(stream)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    st.error(f"LLM Error: {e}")
