import streamlit as st
import folium
from streamlit_folium import st_folium
from sqlalchemy.orm import Session
import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.db.models import CanonicalEntity, EntityRelationship
from backend.config import get_db_session
from backend.geocoding_service import get_geocoder

st.set_page_config(page_title="Geospatial Analysis", page_icon="🌍", layout="wide")

st.title("🌍 Geospatial Analysis")
st.markdown(
    "Visualize the physical locations of entities extracted from your documents."
)

# Sidebar
st.sidebar.header("Map Settings")

# Database Session
db: Session = get_db_session()

# Geocoding Trigger
if st.sidebar.button("🚀 Run Geocoding"):
    with st.spinner("Geocoding entities... (this may take a while due to rate limits)"):
        geocoder = get_geocoder()
        geocoder.batch_process_entities(
            db, limit=20
        )  # Small limit for UI responsiveness
        st.sidebar.success("Batch complete!")
        st.rerun()

# Filters
entity_types = st.sidebar.multiselect(
    "Entity Types", ["GPE", "LOC", "FAC", "ORG"], default=["GPE", "LOC"]
)

min_mentions = st.sidebar.slider("Minimum Mentions", 1, 50, 1)


# Fetch Data
@st.cache_data(ttl=60)
def get_location_data(types, min_count):
    return (
        db.query(CanonicalEntity)
        .filter(
            CanonicalEntity.label.in_(types),
            CanonicalEntity.total_mentions >= min_count,
            CanonicalEntity.latitude.isnot(None),
            CanonicalEntity.longitude.isnot(None),
        )
        .all()
    )


entities = get_location_data(entity_types, min_mentions)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Mapped Entities", len(entities))
col2.metric(
    "Total Locations",
    db.query(CanonicalEntity).filter(CanonicalEntity.label.in_(["GPE", "LOC"])).count(),
)
col3.metric(
    "Geocoded %",
    f"{len(entities) / max(1, db.query(CanonicalEntity).filter(CanonicalEntity.label.in_(['GPE', 'LOC'])).count()) * 100:.1f}%",
)

# Map
if entities:
    # Calculate center
    avg_lat = sum(e.latitude for e in entities) / len(entities)
    avg_lon = sum(e.longitude for e in entities) / len(entities)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=2)

    for entity in entities:
        # Color code by type
        color = "blue"
        if entity.label == "GPE":
            color = "blue"
        elif entity.label == "LOC":
            color = "green"
        elif entity.label == "FAC":
            color = "orange"
        elif entity.label == "ORG":
            color = "red"

        # Size by mentions (logarithmic-ish)
        radius = min(20, 5 + (entity.total_mentions * 0.5))

        folium.CircleMarker(
            location=[entity.latitude, entity.longitude],
            radius=radius,
            popup=f"<b>{entity.canonical_name}</b><br>Type: {entity.label}<br>Mentions: {entity.total_mentions}",
            tooltip=entity.canonical_name,
            color=color,
            fill=True,
            fill_color=color,
        ).add_to(m)

    st_folium(m, width="100%", height=600)

    # Data Table
    with st.expander("📍 View Location Data"):
        data = [
            {
                "Name": e.canonical_name,
                "Type": e.label,
                "Mentions": e.total_mentions,
                "Address": e.resolved_address,
                "Lat": e.latitude,
                "Lon": e.longitude,
            }
            for e in entities
        ]
        st.dataframe(pd.DataFrame(data))

else:
    st.info(
        "No geocoded entities found matching your filters. Try running the geocoder or adjusting filters."
    )

    # Show un-geocoded entities
    ungeocoded = (
        db.query(CanonicalEntity)
        .filter(
            CanonicalEntity.label.in_(entity_types), CanonicalEntity.latitude.is_(None)
        )
        .limit(10)
        .all()
    )

    if ungeocoded:
        st.warning(
            f"Found {len(ungeocoded)}+ entities that need geocoding (e.g., {', '.join([e.canonical_name for e in ungeocoded[:3]])}). Click 'Run Geocoding' in the sidebar."
        )

db.close()
