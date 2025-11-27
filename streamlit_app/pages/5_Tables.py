"""
Extracted Tables Viewer

Browse and analyze tables extracted from PDF documents.
"""

import os
import json
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.db.models import ExtractedTable, Document
from backend.utils.auth import check_authentication

# Authentication check
check_authentication()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

st.set_page_config(page_title="Extracted Tables", page_icon="📊", layout="wide")

st.title("📊 Extracted Tables")
st.markdown(
    """
    Browse tables automatically extracted from PDF documents.
    Tables can be downloaded as CSV files for further analysis.
    """
)


@st.cache_data(ttl=300)
def load_tables(doc_id=None):
    """Load extracted tables from database."""
    session = Session()

    try:
        query = session.query(ExtractedTable, Document).join(
            Document, ExtractedTable.doc_id == Document.id
        )

        if doc_id:
            query = query.filter(ExtractedTable.doc_id == doc_id)

        results = query.order_by(
            ExtractedTable.doc_id, ExtractedTable.page_num, ExtractedTable.table_index
        ).all()

        tables = []
        for table, doc in results:
            tables.append(
                {
                    "id": table.id,
                    "doc_id": table.doc_id,
                    "doc_title": doc.title or os.path.basename(doc.path),
                    "page_num": table.page_num,
                    "table_index": table.table_index,
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "headers": json.loads(table.headers) if table.headers else [],
                    "csv_path": table.csv_path,
                    "text_content": table.text_content,
                }
            )

        return tables

    finally:
        session.close()


@st.cache_data(ttl=300)
def load_documents_with_tables():
    """Get list of documents that have extracted tables."""
    session = Session()

    try:
        docs = (
            session.query(Document)
            .join(ExtractedTable, Document.id == ExtractedTable.doc_id)
            .distinct()
            .order_by(Document.title)
            .all()
        )

        return [(doc.id, doc.title or os.path.basename(doc.path)) for doc in docs]

    finally:
        session.close()


def load_table_csv(csv_path):
    """Load CSV file from disk."""
    try:
        if not os.path.exists(csv_path):
            return None
        return pd.read_csv(csv_path)
    except Exception as e:
        st.error(f"Failed to load CSV: {e}")
        return None


# Sidebar
st.sidebar.header("Filters")

# Document filter
docs_with_tables = load_documents_with_tables()

if not docs_with_tables:
    st.warning(
        "No tables found. Extract tables from PDFs by running: `python extract_tables.py`"
    )
    st.stop()

doc_options = {"All Documents": None}
doc_options.update({title: doc_id for doc_id, title in docs_with_tables})

selected_doc = st.sidebar.selectbox("Document", list(doc_options.keys()))
selected_doc_id = doc_options[selected_doc]

# Load tables
tables = load_tables(selected_doc_id)

if not tables:
    st.info("No tables found for the selected filters.")
    st.stop()

st.sidebar.metric("Total Tables", len(tables))

# Main content
st.subheader(f"Found {len(tables)} tables")

# Table selection
table_options = [
    f"Doc: {t['doc_title']} | Page {t['page_num']} | Table {t['table_index']}"
    for t in tables
]

selected_table_idx = st.selectbox("Select Table", range(len(tables)), format_func=lambda i: table_options[i])

if selected_table_idx is not None:
    table = tables[selected_table_idx]

    # Display table info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Document", table["doc_title"])
    with col2:
        st.metric("Page", table["page_num"])
    with col3:
        st.metric("Rows", table["row_count"])
    with col4:
        st.metric("Columns", table["col_count"])

    st.markdown("---")

    # Display table data
    if table["csv_path"] and os.path.exists(table["csv_path"]):
        df = load_table_csv(table["csv_path"])

        if df is not None:
            st.subheader("Table Data")
            st.dataframe(df, use_container_width=True)

            # Download button
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"table_{table['id']}.csv",
                mime="text/csv",
            )

            # Table statistics
            st.markdown("---")
            st.subheader("Table Statistics")

            stat_col1, stat_col2 = st.columns(2)

            with stat_col1:
                st.markdown("**Columns:**")
                for col in df.columns:
                    st.markdown(f"- {col}")

            with stat_col2:
                st.markdown("**Data Types:**")
                for col, dtype in df.dtypes.items():
                    st.markdown(f"- {col}: {dtype}")

    else:
        # Fallback to text content
        st.subheader("Table Content (Plain Text)")
        st.text(table["text_content"])

    # Search within table
    if table["csv_path"]:
        st.markdown("---")
        st.subheader("Search Table")

        search_query = st.text_input("Search for text in table:")

        if search_query and df is not None:
            # Search all cells
            mask = df.apply(
                lambda row: row.astype(str).str.contains(search_query, case=False).any(),
                axis=1,
            )
            results = df[mask]

            if not results.empty:
                st.success(f"Found {len(results)} matching rows")
                st.dataframe(results, use_container_width=True)
            else:
                st.info("No matches found")

# Bulk actions
st.sidebar.markdown("---")
st.sidebar.subheader("Bulk Actions")

if st.sidebar.button("🔄 Re-extract All Tables"):
    with st.spinner("Re-extracting tables from all documents..."):
        import subprocess
        result = subprocess.run(
            ["python", "extract_tables.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

        if result.returncode == 0:
            st.sidebar.success("✓ Tables re-extracted!")
            st.cache_data.clear()
        else:
            st.sidebar.error(f"Failed:\n{result.stderr}")
