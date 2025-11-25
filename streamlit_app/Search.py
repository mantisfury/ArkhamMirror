import streamlit as st

# Trigger reload
import pandas as pd
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import re
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv
import importlib
import backend.db.models

importlib.reload(backend.db.models)
from backend.db.models import Document, Entity, Chunk, Project, Anomaly, PageOCR
from backend.embedding_services import embed_hybrid
# from openai import OpenAI # Removed

from backend.utils.auth import check_authentication

load_dotenv()
st.set_page_config(layout="wide", page_title="ArkhamMirror Search")

# Check authentication
check_authentication()

# Initialize State
if "view_doc_id" not in st.session_state:
    st.session_state.view_doc_id = None
if "highlight_chunk" not in st.session_state:
    st.session_state.highlight_chunk = None
if "search_results" not in st.session_state:
    st.session_state.search_results = []

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
# Base.metadata.create_all(engine) # Handled by reset_db.py or migration scripts

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
COLLECTION_NAME = "arkham_mirror_hybrid"


# Helper for Chat
def chat_with_llm(messages, temperature=0.3):
    url = (
        f"{os.getenv('LM_STUDIO_URL', 'http://172.17.144.1:1234/v1')}/chat/completions"
    )
    payload = {
        "model": "qwen/qwen3-vl-8b",
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    try:
        import requests
        import json

        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}, stream=True
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8")
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data_json = json.loads(data_str)
                        content = data_json["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"LLM Error: {e}"


def explain_with_ai(text, context="", lens="General Summary"):
    prompts = {
        "General Summary": "You are a helpful analyst. Summarize the key information in this text.",
        "Red Flag Scanner": "You are a forensic investigator. Identify any suspicious language, inconsistencies, or high-risk entities in this text. Be extremely critical.",
        "Motive Detective": "You are a psychologist. Analyze the text to infer the author's hidden motivations, biases, or what they might be trying to conceal.",
        "Timeline Analyst": "You are a historian. Extract a chronological sequence of events from this text, noting any gaps or non-linear narratives.",
    }

    system_prompt = prompts.get(lens, prompts["General Summary"])

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context: {context}\n\nAnalyze this snippet:\n{text}",
        },
    ]

    return chat_with_llm(messages)


# State Management
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


def delete_document(doc_id):
    session = Session()
    try:
        doc = session.query(Document).get(doc_id)
        if not doc:
            st.error("Document not found.")
            return

        # Delete from Qdrant
        try:
            # Find chunks first to get their IDs
            chunks = session.query(Chunk).filter(Chunk.doc_id == doc_id).all()
            chunk_ids = [c.id for c in chunks]

            if chunk_ids:
                # Delete Anomalies linked to these chunks first (Foreign Key Constraint)
                session.query(Anomaly).filter(Anomaly.chunk_id.in_(chunk_ids)).delete(
                    synchronize_session=False
                )

                # Delete from Qdrant
                qdrant_client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=chunk_ids),
                )
        except Exception as e:
            st.warning(f"Could not delete from Vector DB: {e}")

        # Delete from DB - Cascade Order Matters!
        # 1. Entities
        session.query(Entity).filter(Entity.doc_id == doc_id).delete()
        # 2. Anomalies (already done above, but safe to double check if needed)
        # 3. Chunks
        session.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        # 4. PageOCR
        session.query(PageOCR).filter(PageOCR.document_id == doc_id).delete()
        # 5. MiniDocs (This was the missing link causing FK violation)
        session.query(backend.db.models.MiniDoc).filter(
            backend.db.models.MiniDoc.document_id == doc_id
        ).delete()
        # 6. Document
        session.query(Document).filter(Document.id == doc_id).delete()

        session.commit()

        # Delete file
        if os.path.exists(doc.path):
            try:
                os.remove(doc.path)
            except OSError:
                pass  # File might be open or already gone

        st.success(f"Deleted {doc.title}")
        st.session_state.selected_doc = None
        st.session_state.view_doc_id = None
        st.rerun()
    except Exception as e:
        st.error(f"Error deleting document: {e}")
    finally:
        session.close()


# --- Sidebar ---
with st.sidebar:
    st.header("🗂️ Projects")

    session = Session()
    try:
        projects = session.query(Project).all()
        project_options = {p.name: p.id for p in projects}
        project_options["All Projects"] = None

        selected_project_name = st.selectbox(
            "Select Project",
            options=list(project_options.keys()),
            index=list(project_options.keys()).index("All Projects"),
        )
        selected_project_id = (
            project_options.get(selected_project_name)
            if selected_project_name != "All Projects"
            else None
        )

        # Create New Project
        with st.expander("➕ New Project"):
            new_proj_name = st.text_input("Project Name")
            if st.button("Create Project"):
                if new_proj_name:
                    try:
                        new_proj = Project(name=new_proj_name)
                        session.add(new_proj)
                        session.commit()
                        st.success(f"Created '{new_proj_name}'")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Enter a name.")
    finally:
        session.close()

    st.divider()

    # --- System Controls ---
    st.header("⚙️ System Controls")

    # 1. Background Workers (The Chefs)
    if "workers_running" not in st.session_state:
        st.session_state.workers_running = False

    col_workers, col_status = st.columns([2, 1])
    with col_workers:
        if st.button(
            "🚀 Spawn Worker",
            help="Start a background worker process. Click multiple times to spawn multiple workers.",
        ):
            try:
                import subprocess

                # Use start to open a new window so it doesn't die when Streamlit refreshes?
                # Or just Popen. Popen with shell=True and start is best for Windows visibility.
                subprocess.Popen(
                    ["start", "run_workers.bat"], shell=True, cwd=os.getcwd()
                )
                st.toast("Worker Spawned!", icon="🚀")
            except Exception as e:
                st.error(f"Failed: {e}")

    with col_status:
        # Queue Status
        try:
            from redis import Redis
            from rq import Queue

            redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
            q = Queue(connection=redis_conn)
            job_count = q.count
            st.metric("Queue", job_count)
        except Exception:
            st.metric("Queue", "Err")

    st.divider()

    # 2. Ingestion (The Waiters)
    st.subheader("📥 Ingestion")

    ingest_mode = st.radio(
        "Mode", ["Manual", "Auto-Watch"], horizontal=True, label_visibility="collapsed"
    )

    if ingest_mode == "Auto-Watch":
        if "watcher_running" not in st.session_state:
            st.session_state.watcher_running = False

        if st.toggle("👀 Folder Watcher", value=st.session_state.watcher_running):
            if not st.session_state.watcher_running:
                try:
                    import subprocess

                    subprocess.Popen(["run_watcher.bat"], shell=True, cwd=os.getcwd())
                    st.session_state.watcher_running = True
                    st.toast("Watcher Started", icon="👀")
                except Exception as e:
                    st.error(f"Failed: {e}")
        else:
            if st.session_state.watcher_running:
                st.session_state.watcher_running = False
                st.info("Watcher stopped (close terminal to confirm).")

        st.info("Drop files in `./temp` to auto-ingest.")

    else:  # Manual Mode
        with st.expander("Upload Files", expanded=True):
            uploaded = st.file_uploader("Drop files here", accept_multiple_files=True)
            if uploaded:
                os.makedirs("./temp", exist_ok=True)
                for f in uploaded:
                    with open(f"./temp/{f.name}", "wb") as w:
                        w.write(f.getbuffer())
                st.success(f"Uploaded {len(uploaded)} files.")

        # OCR Mode Selection
        ocr_mode = st.radio(
            "OCR Engine", ["PaddleOCR (Fast)", "Qwen-VL (Smart)"], index=0
        )
        mode_arg = "paddle" if "Paddle" in ocr_mode else "qwen"

        if st.button("⚙️ Process Files", type="primary", width="stretch"):
            with st.spinner("Queueing files..."):
                import subprocess

                cmd = [sys.executable, "-m", "backend.workers.ingest_worker"]
                if selected_project_id:
                    cmd.extend(["--project_id", str(selected_project_id)])

                # Pass the selected OCR mode
                cmd.extend(["--ocr_mode", mode_arg])

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        st.toast("Files Enqueued!", icon="✅")
                    else:
                        st.error(result.stderr)
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.divider()

    # 3. Clustering
    st.subheader("🧩 Clustering")
    if st.button("Run Clustering", width="stretch"):
        with st.status("Clustering...", expanded=True) as status:
            st.write("Loading vectors...")
            import subprocess

            cmd = [sys.executable, "-m", "backend.workers.clustering_worker"]
            if selected_project_id:
                cmd.extend(["--project_id", str(selected_project_id)])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    status.update(
                        label="Clustering Complete!", state="complete", expanded=False
                    )
                    st.rerun()
                else:
                    status.update(label="Clustering Failed", state="error")
                    st.error(result.stderr)
            except Exception as e:
                st.error(f"Failed: {e}")

    st.divider()

    # Progress Monitor
    st.subheader("📊 Processing Status")
    try:
        session = Session()
        # Count active docs
        active_docs = (
            session.query(Document).filter(Document.status == "processing").all()
        )

        if active_docs:
            for d in active_docs:
                # Calculate progress
                total_pages = d.num_pages
                if total_pages > 0:
                    done_pages = (
                        session.query(PageOCR)
                        .filter(PageOCR.document_id == d.id)
                        .count()
                    )
                    progress = done_pages / total_pages
                    st.progress(
                        progress, text=f"{d.title[:20]}... ({done_pages}/{total_pages})"
                    )
                else:
                    st.spinner(f"Splitting {d.title}...")
        else:
            st.caption("No active processing jobs.")
    except Exception as e:
        st.error(f"Monitor error: {e}")
    finally:
        session.close()

    st.divider()
    st.subheader("Filters")

    session = Session()
    try:
        st.markdown("**Entity Type**")
        entity_types = session.query(Entity.label).distinct().all()
        selected_types = st.multiselect("Select Types", [e[0] for e in entity_types])

        st.markdown("**File Type**")
        doc_types = session.query(Document.doc_type).distinct().all()
        selected_exts = st.multiselect("Select Extensions", [d[0] for d in doc_types])
    finally:
        session.close()

# --- Main Layout ---
st.title("🔎 ArkhamMirror Workspace")

# Search Bar
with st.form("search_form"):
    col_input, col_btn = st.columns([8, 1])
    with col_input:
        query = st.text_input(
            "Search Query",
            label_visibility="collapsed",
            placeholder="Search companies, people, and documents...",
        )
    with col_btn:
        search_clicked = st.form_submit_button("Search")

# Search Scope (Outside form to allow dynamic updates if needed, or inside expander)
with st.expander("🔎 Search Options"):
    session = Session()
    try:
        all_docs = session.query(Document).order_by(Document.created_at.desc()).all()
        doc_options = {d.title: d.id for d in all_docs}
        selected_titles = st.multiselect(
            "Limit search to specific documents:",
            options=list(doc_options.keys()),
            default=[],
        )
        st.session_state.selected_doc_ids_for_search = [
            doc_options[t] for t in selected_titles
        ]
    finally:
        session.close()

# Handle Search
if search_clicked and query:
    try:
        q_vecs = embed_hybrid(query)

        # Build Filter
        search_filter = Filter(must=[])

        # Project Filter
        if selected_project_id:
            search_filter.must.append(
                FieldCondition(
                    key="project_id", match=MatchValue(value=selected_project_id)
                )
            )

        # Document Filter (New)
        if (
            "selected_doc_ids_for_search" in st.session_state
            and st.session_state.selected_doc_ids_for_search
        ):
            search_filter.must.append(
                FieldCondition(
                    key="doc_id",
                    match=models.MatchAny(
                        any=st.session_state.selected_doc_ids_for_search
                    ),
                )
            )

        hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=q_vecs["dense"],
            using="dense",
            query_filter=search_filter,
            limit=20,
        ).points
        st.session_state.search_results = hits
    except Exception as e:
        st.error(f"Search failed: {e}")

# Split Pane
col_nav, col_viewer = st.columns([1, 2])

with col_nav:
    tab_results, tab_library = st.tabs(["🔍 Results", "📚 Library"])

    with tab_results:
        if st.session_state.search_results:
            st.caption(f"Found {len(st.session_state.search_results)} matches")
            for hit in st.session_state.search_results:
                with st.container(border=True):
                    doc_id = hit.payload.get("doc_id")
                    st.markdown(f"**Document ID: {doc_id}**")
                    st.caption(f"Score: {hit.score:.2f}")
                    chunk_preview = hit.payload.get("text", "")[:150] + "..."
                    st.text(chunk_preview)
                    if st.button("View Context", key=f"hit_{hit.id}"):
                        st.session_state.view_doc_id = doc_id
                        st.session_state.highlight_chunk = hit.payload.get("text", "")
        else:
            st.info("Run a search to see results.")

    with tab_library:
        session = Session()
        try:
            query_obj = session.query(Document)
            if selected_project_id:
                query_obj = query_obj.filter(Document.project_id == selected_project_id)

            docs = query_obj.order_by(Document.created_at.desc()).all()

            if docs:
                data = [
                    {
                        "ID": d.id,
                        "Name": d.title,
                        "Status": d.status,
                        "Pages": d.num_pages,
                        "Date": d.created_at,
                    }
                    for d in docs
                ]
                df = pd.DataFrame(data)
                event = st.dataframe(
                    df,
                    on_select="rerun",
                    selection_mode="single-row",
                    width="stretch",
                    hide_index=True,
                )
                if event.selection.rows:
                    selected_index = event.selection.rows[0]
                    st.session_state.view_doc_id = df.iloc[selected_index]["ID"]
                    st.session_state.highlight_chunk = (
                        None  # Clear highlight when browsing
                    )
            else:
                st.info("No documents in library.")
        finally:
            session.close()

with col_viewer:
    if st.session_state.view_doc_id:
        session = Session()
        try:
            doc = session.query(Document).get(int(st.session_state.view_doc_id))
            if doc:
                st.subheader(f"📄 {doc.title}")

                # Actions
                c_act1, c_act2, c_act3 = st.columns([1, 2, 3])
                with c_act1:
                    if st.button("🗑️ Delete", type="primary"):
                        delete_document(doc.id)

                with c_act2:
                    if st.button("🔄 Retry Missing Pages"):
                        from backend.retry_utils import retry_missing_pages

                        with st.spinner("Checking for missing pages..."):
                            msg = retry_missing_pages(doc.id)
                            if "Error" in msg:
                                st.error(msg)
                            else:
                                st.success(msg)
                                st.rerun()

                # Tabs
                tab_content, tab_meta, tab_ai = st.tabs(
                    ["Content", "Metadata", "AI Analysis"]
                )

                with tab_content:
                    # Reconstruct full text
                    full_text = reconstruct_full_text(doc.id)

                    # 1. Apply Chunk Highlight (if any)
                    if st.session_state.highlight_chunk:
                        # Use a distinctive background for the specific chunk found in search
                        chunk_text = st.session_state.highlight_chunk
                        # Escape for regex
                        pattern = re.compile(re.escape(chunk_text), re.IGNORECASE)
                        full_text = pattern.sub(
                            lambda m: f"<span style='background-color: #fff9c4; border: 2px solid #fbc02d; padding: 2px;'>{m.group(0)}</span>",
                            full_text,
                        )
                        st.info("💡 Highlighting search result chunk.")

                    # 2. Apply Suspicious Keyword Highlight (Red Flags)
                    suspicious_keywords = [
                        "confidential",
                        "secret",
                        "do not distribute",
                        "delete",
                        "shred",
                        "hidden",
                        "off the books",
                        "private",
                        "restricted",
                    ]
                    for word in suspicious_keywords:
                        pattern = re.compile(re.escape(word), re.IGNORECASE)
                        full_text = pattern.sub(
                            lambda m: f"<span style='background-color: #ff4b4b66; font-weight: bold; padding: 2px; border-radius: 4px;'>{m.group(0)}</span>",
                            full_text,
                        )

                    st.markdown(full_text, unsafe_allow_html=True)

                with tab_meta:
                    st.json(
                        {
                            "id": doc.id,
                            "title": doc.title,
                            "path": doc.path,
                            "type": doc.doc_type,
                            "created_at": str(doc.created_at),
                            "hash": doc.file_hash,
                        }
                    )

                    st.divider()
                    st.subheader("🔗 Extracted Entities")
                    entities = (
                        session.query(Entity)
                        .filter(Entity.doc_id == doc.id)
                        .order_by(Entity.label, Entity.count.desc())
                        .all()
                    )

                    if entities:
                        # Group by label
                        from collections import defaultdict

                        grouped = defaultdict(list)
                        for e in entities:
                            grouped[e.label].append(f"{e.text} ({e.count})")

                        for label, items in grouped.items():
                            with st.expander(f"{label} ({len(items)})"):
                                st.write(", ".join(items))
                    else:
                        st.caption("No entities extracted yet.")

                    st.divider()
                    st.subheader("🕵️ Forensic File Check")

                    # Path check logic
                    final_path = None
                    if os.path.exists(doc.path):
                        final_path = doc.path
                    else:
                        processed_path = os.path.join(
                            os.path.dirname(doc.path),
                            "processed",
                            os.path.basename(doc.path),
                        )
                        if os.path.exists(processed_path):
                            final_path = processed_path

                    if final_path:
                        stats = os.stat(final_path)
                        created = datetime.fromtimestamp(stats.st_ctime)
                        modified = datetime.fromtimestamp(stats.st_mtime)
                        c1, c2 = st.columns(2)
                        c1.metric("Created", created.strftime("%Y-%m-%d %H:%M:%S"))
                        c2.metric("Modified", modified.strftime("%Y-%m-%d %H:%M:%S"))
                        if modified < created:
                            st.warning(
                                "⚠️ Anomaly: Modification time is BEFORE creation time."
                            )
                    else:
                        st.error(f"File not found: {doc.path}")

                with tab_ai:
                    st.markdown("### 🧠 Investigation Lens")
                    lens = st.selectbox(
                        "Select Analysis Mode",
                        [
                            "General Summary",
                            "Motive Detective",
                            "Timeline Analyst",
                        ],
                    )
                    c_run, c_stop = st.columns([1, 1])
                    with c_run:
                        run_clicked = st.button("Run Analysis")
                    with c_stop:
                        if st.button("🛑 Stop", help="Stop the current analysis"):
                            st.stop()

                    if run_clicked:
                        with st.spinner(f"Running {lens}..."):
                            # Increased limit for larger context window (approx 25k tokens)
                            limit = 100000
                            if len(full_text) > limit:
                                st.warning(
                                    f"[WARNING] Document is too large ({len(full_text)} chars). Analyzing the first {limit} characters only."
                                )
                                analysis_text = full_text[:limit]
                            else:
                                analysis_text = full_text

                            stream = explain_with_ai(analysis_text, query, lens)
                            if isinstance(stream, str):
                                st.error(stream)
                            else:
                                st.write_stream(stream)

            else:
                st.error("Document not found in DB.")
        finally:
            session.close()
    else:
        st.info("Select a document to view.")
