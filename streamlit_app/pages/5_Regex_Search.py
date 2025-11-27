import streamlit as st
import pandas as pd
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Document, SensitiveDataMatch
from backend.utils.pattern_detector import get_detector
from backend.utils.auth import check_authentication

load_dotenv()
st.set_page_config(layout="wide", page_title="Regex Search")

# Check authentication
check_authentication()

# Database setup
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)

st.title("🔍 Regex Search & Sensitive Data Detection")
st.caption("Search for sensitive patterns across all documents")

# Sidebar - Pattern Selection
with st.sidebar:
    st.header("Search Patterns")

    detector = get_detector()
    pattern_descriptions = detector.get_pattern_descriptions()

    st.markdown("### Built-in Patterns")
    selected_patterns = st.multiselect(
        "Select patterns to search:",
        options=list(pattern_descriptions.keys()),
        default=["email", "phone", "ssn"],
        format_func=lambda x: pattern_descriptions[x]
    )

    st.divider()
    st.markdown("### Custom Regex")
    custom_pattern = st.text_input(
        "Custom regex pattern (advanced):",
        placeholder=r"\b\d{3}-\d{3}-\d{4}\b"
    )
    custom_pattern_name = st.text_input(
        "Pattern name:",
        placeholder="custom_phone"
    )

    st.divider()
    confidence_threshold = st.slider(
        "Minimum Confidence",
        0.0, 1.0, 0.5, 0.1
    )

# Main content
tab_search, tab_detected = st.tabs(["🔎 Search Documents", "📊 Already Detected"])

with tab_search:
    st.markdown("### Search Documents for Patterns")
    st.info("💡 This searches through ALL text in the database using real-time pattern matching")

    if st.button("🚀 Run Search", type="primary", disabled=not selected_patterns):
        session = Session()
        try:
            with st.spinner("Searching documents..."):
                # Get all chunks
                from backend.db.models import Chunk
                chunks = session.query(Chunk).all()

                if not chunks:
                    st.warning("No processed documents found. Upload and process documents first.")
                else:
                    results = []
                    progress_bar = st.progress(0)

                    for idx, chunk in enumerate(chunks):
                        matches = detector.detect_patterns(chunk.text, pattern_types=selected_patterns)

                        for match in matches:
                            if match.confidence >= confidence_threshold:
                                results.append({
                                    "doc_id": chunk.doc_id,
                                    "chunk_id": chunk.id,
                                    "pattern_type": match.pattern_type,
                                    "match_text": match.match_text,
                                    "confidence": match.confidence,
                                    "context": f"...{match.context_before} **{match.match_text}** {match.context_after}..."
                                })

                        progress_bar.progress((idx + 1) / len(chunks))

                    progress_bar.empty()

                    if results:
                        st.success(f"Found {len(results)} matches across {len(set([r['doc_id'] for r in results]))} documents")

                        # Group by pattern type
                        df = pd.DataFrame(results)

                        # Get document titles
                        doc_ids = df["doc_id"].unique()
                        docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
                        doc_map = {d.id: d.title for d in docs}
                        df["document"] = df["doc_id"].map(doc_map)

                        # Display results by pattern type
                        for pattern_type in df["pattern_type"].unique():
                            pattern_df = df[df["pattern_type"] == pattern_type]

                            with st.expander(f"🔍 {pattern_type.upper().replace('_', ' ')} ({len(pattern_df)} matches)", expanded=True):
                                for _, row in pattern_df.iterrows():
                                    confidence_color = "🟢" if row["confidence"] > 0.8 else "🟡" if row["confidence"] > 0.5 else "🔴"
                                    st.markdown(f"{confidence_color} **{row['document']}** - `{row['match_text']}` (Confidence: {row['confidence']:.2f})")
                                    st.caption(row["context"])
                                    st.markdown("---")

                    else:
                        st.info("No matches found for the selected patterns")

        finally:
            session.close()

with tab_detected:
    st.markdown("### Previously Detected Sensitive Data")
    st.caption("Patterns automatically detected during document processing")

    session = Session()
    try:
        # Get all sensitive data matches
        matches = session.query(SensitiveDataMatch).all()

        if not matches:
            st.info("No sensitive data has been detected yet. Process documents to enable automatic detection.")
        else:
            # Statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Matches", len(matches))
            with col2:
                unique_docs = len(set([m.doc_id for m in matches]))
                st.metric("Documents with Sensitive Data", unique_docs)
            with col3:
                unique_types = len(set([m.pattern_type for m in matches]))
                st.metric("Pattern Types Found", unique_types)

            st.divider()

            # Filter controls
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                pattern_filter = st.multiselect(
                    "Filter by pattern type:",
                    options=list(set([m.pattern_type for m in matches])),
                    default=list(set([m.pattern_type for m in matches]))
                )
            with col_filter2:
                conf_filter = st.slider("Minimum confidence:", 0.0, 1.0, 0.0, 0.1, key="detected_conf")

            # Filter matches
            filtered = [m for m in matches if m.pattern_type in pattern_filter and m.confidence >= conf_filter]

            if filtered:
                # Group by document
                doc_groups = defaultdict(list)
                for match in filtered:
                    doc_groups[match.doc_id].append(match)

                # Get document info
                doc_ids = list(doc_groups.keys())
                docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
                doc_map = {d.id: d for d in docs}

                st.markdown(f"### Showing {len(filtered)} matches from {len(doc_groups)} documents")

                for doc_id, doc_matches in doc_groups.items():
                    doc = doc_map.get(doc_id)
                    doc_title = doc.title if doc else f"Document #{doc_id}"

                    with st.expander(f"📄 {doc_title} ({len(doc_matches)} matches)"):
                        # Group by pattern type within document
                        pattern_groups = defaultdict(list)
                        for match in doc_matches:
                            pattern_groups[match.pattern_type].append(match)

                        for pattern_type, pattern_matches in pattern_groups.items():
                            st.markdown(f"**{pattern_type.upper().replace('_', ' ')}** ({len(pattern_matches)})")

                            for match in pattern_matches[:5]:  # Show first 5
                                confidence_color = "🟢" if match.confidence > 0.8 else "🟡" if match.confidence > 0.5 else "🔴"
                                st.markdown(f"{confidence_color} `{match.match_text}` (Confidence: {match.confidence:.2f})")
                                if match.context_before or match.context_after:
                                    context = f"...{match.context_before} **[{match.match_text}]** {match.context_after}..."
                                    st.caption(context)

                            if len(pattern_matches) > 5:
                                st.info(f"+ {len(pattern_matches) - 5} more {pattern_type} matches")

                            st.markdown("---")
            else:
                st.info("No matches found with current filters")

    finally:
        session.close()

# Help section
with st.expander("ℹ️ Pattern Information"):
    st.markdown("""
    ### Supported Patterns

    **Financial:**
    - **SSN**: Social Security Numbers (US format)
    - **Credit Card**: Major credit card numbers (Visa, MC, Amex, etc.) with Luhn validation
    - **IBAN**: International Bank Account Numbers
    - **Bitcoin**: Cryptocurrency addresses

    **Contact Information:**
    - **Email**: Email addresses
    - **Phone**: US and international phone numbers

    **Technical:**
    - **IP Address**: IPv4 addresses
    - **API Key**: Generic API keys (32+ characters)
    - **AWS Access Key**: AWS access key IDs
    - **GitHub Token**: GitHub personal access tokens

    **Identity:**
    - **Passport**: Potential passport numbers
    - **Driver's License**: Potential driver's license numbers

    ### Confidence Scores
    - **High (0.8-1.0)**: Pattern passed validation (e.g., Luhn algorithm for credit cards)
    - **Medium (0.5-0.8)**: Pattern matched with reasonable entropy
    - **Low (0.0-0.5)**: Basic pattern match, may need verification

    ### Security Note
    This tool helps identify sensitive data for:
    - **Redaction**: Find and remove sensitive information before sharing
    - **Compliance**: Ensure documents don't contain unauthorized PII
    - **Forensics**: Locate financial/identity information in investigations
    """)
