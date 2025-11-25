import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from backend.db.models import Document, Entity, Anomaly, Chunk

load_dotenv()
st.set_page_config(layout="wide", page_title="ArkhamMirror Overview")

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)

st.title("📊 ArkhamMirror Overview")

session = Session()
try:
    # Metrics
    # Filters
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        # Project Filter (Placeholder)
        selected_project = st.selectbox(
            "Filter by Project", ["All Projects", "Default Project"]
        )

    with col_filter2:
        # File Filter
        all_docs = session.query(Document).all()
        doc_options = {f"{d.title}": d.id for d in all_docs}
        doc_options["All Files"] = None
        selected_file_label = st.selectbox("Filter by File", list(doc_options.keys()))
        selected_file_id = doc_options[selected_file_label]

    # Metrics Query Construction
    q_docs = session.query(Document)
    q_ents = session.query(Entity).join(Document, Entity.doc_id == Document.id)
    q_anoms = (
        session.query(Anomaly)
        .join(Chunk, Anomaly.chunk_id == Chunk.id)
        .join(Document, Chunk.doc_id == Document.id)
    )

    if selected_file_id:
        q_docs = q_docs.filter(Document.id == selected_file_id)
        q_ents = q_ents.filter(Document.id == selected_file_id)
        q_anoms = q_anoms.filter(Document.id == selected_file_id)

    total_docs = q_docs.count()
    total_entities = q_ents.count()
    total_anomalies = q_anoms.count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Documents", total_docs)
    col2.metric("Extracted Entities", total_entities)
    col3.metric("Detected Anomalies", total_anomalies)

    st.divider()

    # Charts
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Top Entities")
        top_entities = (
            session.query(
                Entity.text, Entity.label, func.count(Entity.text).label("count")
            )
            .group_by(Entity.text, Entity.label)
            .order_by(func.count(Entity.text).desc())
            .limit(10)
            .all()
        )

        if top_entities:
            df_ent = pd.DataFrame(top_entities, columns=["Entity", "Type", "Count"])
            fig_ent = px.bar(
                df_ent,
                x="Count",
                y="Entity",
                color="Type",
                orientation="h",
                title="Top 10 Entities",
            )
            st.plotly_chart(fig_ent, use_container_width=True)
        else:
            st.info("No entities found yet.")

    with col_right:
        st.subheader("Document Types")
        doc_types = (
            session.query(Document.doc_type, func.count(Document.id).label("count"))
            .group_by(Document.doc_type)
            .all()
        )

        if doc_types:
            df_docs = pd.DataFrame(doc_types, columns=["Type", "Count"])
            fig_docs = px.pie(
                df_docs, values="Count", names="Type", title="Distribution by File Type"
            )
            st.plotly_chart(fig_docs, use_container_width=True)
        else:
            st.info("No documents found yet.")

finally:
    session.close()
