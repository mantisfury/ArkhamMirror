# 🗺️ ArkhamMirror Roadmap

This roadmap outlines the future development direction of ArkhamMirror. We welcome community contributions to help us achieve these goals!

## v0.1 (Current Release)

- [x] Hybrid OCR (Paddle + Qwen-VL)
- [x] Semantic Search (Dense + Sparse Embeddings)
- [x] Local LLM Integration (LM Studio)
- [x] Anomaly Detection (Keyword/Visual)
- [x] Basic Document Clustering
- [x] Streamlit UI

## v0.2: The "Connector" Update (In Progress)

*Focus: Linking entities and improving ingestion.*

- [ ] **Cross-Document Entity Linking**: Automatically detect that "John Doe" in Doc A is the same as "J. Doe" in Doc B.
  - *Requires*: Entity Resolution (Deduplication), Graph Database (NetworkX/Neo4j), Relationship Extraction.
- [ ] **Data Extraction (Core)**:
  - **Table Extraction**: Convert PDF tables to CSV/Excel (using Table Transformer).
  - **Metadata Scrubbing**: Extract author, creation date, and software metadata.
  - **Regex Search**: Find specific patterns (Credit Cards, IBANs, Emails, SSNs).
- [ ] **Visual Analytics (Quick Wins)**:
  - **Wordclouds**: Visualize top terms per document or cluster.
  - **Heatmaps**: Entity co-occurrence matrices and activity-over-time grids.
- [ ] **Ingestion Progress Bar**: Real-time status updates in the UI.
- [ ] **Configurable Pipelines**: Allow users to define custom extraction steps via YAML.
- [ ] **Multilingual Embeddings**: Switch to `BAAI/bge-m3` to enable cross-language semantic search (e.g. search English, find Russian).
- [x] **More File Types**: Support for .docx, .eml, .msg, .txt, and images.
- [x] **NER Integration**: Extract People, Orgs, and Locations.

## v0.3: The "Analyst" Update (Advanced Logic)

*Focus: Visualizing relationships and temporal analysis.*

- [ ] **Interactive Graph Explorer**: Visual UI (using NetworkX/PyVis) to navigate connections between people, organizations, and events.
- [ ] **Geospatial Analysis**: Map extracted locations to visualize physical connections.
- [ ] **Multilingual Support**:
  - **Offline Translation**: Translate foreign documents to English (using Qwen-VL or NLLB).
- [ ] **Data Refinement**:
  - **OCR Correction UI**: Manually fix OCR errors to improve search index.
- [ ] **Timeline Analysis**:
  - **Event Extraction**: Identify dates and associated events.
  - **Interactive Timelines**: Plot events chronologically to see the "story" of a case.
- [ ] **Consistency Checking**:
  - **Fact Checking**: Cross-reference claims against other documents.
  - **Stylometry**: Detect voice changes (e.g., multiple authors in one doc).

## v0.4: The "Watchdog" Update (Statistical Anomaly)

*Focus: Deep statistical analysis and secure team collaboration.*

> [!IMPORTANT]
> ArkhamMirror will ALWAYS be local-first. "Collaboration" means allowing a team of journalists to work together on a private, self-hosted server (LAN/VPN), NOT sending data to a public cloud.

- [ ] **Advanced Anomaly Detection**:
  - **Local Outlier Factor (LOF)**: Detect documents that are statistically distant from their clusters.
  - **Autoencoders**: Identify "unique" documents that don't fit standard patterns.
  - **Paraphrase Detection**: Find leaks by identifying re-worded content across documents.
- [ ] **Local User Auth**: Simple user accounts for team access on a shared local server.
- [ ] **Annotation System**: Highlight and comment on documents shared within the private network.
- [ ] **Headless API**: Decouple the backend (FastAPI) to allow custom local interfaces or integration with other offline tools.

## Future Ideas

- **Face Recognition**: Identify people in photos across documents.
- **Audio Fingerprinting**: Match audio clips.
- **Dark Web Scraper**: Optional module to pull data from onion sites.
