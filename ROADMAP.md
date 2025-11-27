# 🗺️ ArkhamMirror Roadmap

This roadmap outlines the future development direction of ArkhamMirror. We welcome community contributions to help us achieve these goals!

## v0.1 (Current Release)

- [x] Hybrid OCR (Paddle + Qwen-VL)
- [x] Semantic Search (Dense + Sparse Embeddings)
- [x] Local LLM Integration (LM Studio)
- [x] Anomaly Detection (Keyword/Visual)
- [x] Basic Document Clustering
- [x] Streamlit UI

## v0.1.5: The "Hardening" Update (Completed ✅)

*Focus: Security, stability, and code quality before major feature expansion.*

- [x] **Critical Security Fixes**: XSS, Command Injection, Path Traversal, Hardcoded Creds.
- [x] **Basic Authentication**: Simple password protection for the UI (using `streamlit-authenticator`).
- [x] **Network Security**: Bind database ports to localhost to prevent accidental exposure.
- [x] **Code Quality Refactor**:
  - [x] Fix N+1 query performance issues in Anomaly detection.
  - [x] Implement proper database constraints (Foreign Keys, Unique Constraints).
  - [x] Centralize configuration (remove magic numbers).
  - [x] Add unit tests for critical paths.

## v0.2: The "Connector" Update (Completed ✅)

*Focus: Linking entities and improving ingestion.*

- [x] **Cross-Document Entity Linking**: Automatically detect that "John Doe" in Doc A is the same as "J. Doe" in Doc B.
  - Implemented fuzzy matching, canonical entity resolution, co-occurrence tracking
- [x] **Data Extraction (Core)**:
  - [x] **Table Extraction**: Convert PDF tables to CSV (using pdfplumber).
  - [x] **Metadata Scrubbing**: Extract author, creation date, software metadata from PDFs with forensic analysis for tampering detection.
  - [x] **Regex Search**: 12 pattern types (SSN, Credit Cards, Emails, Phone, IP Addresses, API Keys, IBANs, Bitcoin). Includes validation (Luhn algorithm for credit cards, SSN rules).
- [x] **Visual Analytics (Quick Wins)**:
  - [x] **Wordclouds**: Visualize top terms per document or cluster.
  - [x] **Heatmaps**: Entity co-occurrence matrices and activity-over-time grids.
- [ ] **Ingestion Progress Bar**: Real-time status updates in the UI (deferred to v0.4).
- [ ] **Configurable Pipelines**: Allow users to define custom extraction steps via YAML (deferred to v0.4).
- [x] **Multilingual Embeddings**: Using `BAAI/bge-m3` for cross-language semantic search.
- [x] **More File Types**: Support for .docx, .eml, .msg, .txt, and images.
- [x] **NER Integration**: Extract People, Orgs, and Locations.

## v0.2.5: The "Modular Search" Update (Completed ✅)

*Focus: Flexible embedding system and proper hybrid search implementation.*

- [x] **Modular Embedding Architecture**:
  - [x] Provider-based system (swap embedding models without code changes)
  - [x] BGE-m3 provider (multilingual, native hybrid embeddings)
  - [x] MiniLM-BM25 provider (lightweight English-only, BM25 sparse)
  - [x] Configuration for provider selection and hybrid weights
- [x] **True Hybrid Search**:
  - [x] Implement RRF (Reciprocal Rank Fusion) for dense + sparse vectors
  - [x] User-configurable dense/sparse weights (default 70/30)
  - [x] Improved resilience for exact term matching (case numbers, OCR errors)
- [x] **Installation Tiers**:
  - [x] Minimal tier: MiniLM-BM25 (~1.3GB total, English-only)
  - [x] Standard tier: BGE-m3 (~3.5GB total, multilingual)
  - [x] Setup script for model downloads and configuration
- [x] **Documentation**:
  - [x] Embedding provider comparison guide
  - [x] Migration guide for switching providers
  - [x] Re-indexing script for provider changes

## v0.3: The "Analyst" Update (In Progress)

*Focus: Visualizing relationships and temporal analysis.*

- [x] **Interactive Graph Explorer**: Visual UI (using NetworkX/PyVis) to navigate connections between people, organizations, and events.
  - [x] Community Detection (Louvain)
  - [x] Pathfinding (Shortest Path)
- [x] **Timeline Analysis**: (Completed ✅)
  - [x] **Event Extraction**: LLM-based extraction of chronological events with dates, types, and confidence scores
  - [x] **Date Mention Extraction**: Regex and NLP-based extraction of all date references
  - [x] **Interactive Timeline Visualization**: Three-view interface (Event Timeline, Date Distribution, Gap Analysis)
  - [x] **Gap Detection**: Identify suspicious temporal gaps in document timelines
  - [x] **Search Integration**: Filter search results by date range using extracted timeline data
  - [ ] **Timeline Export**: Export timeline data to CSV/JSON for external analysis
  - [ ] **Custom Event Types**: User-configurable event type definitions and classification rules
  - [ ] **Multi-Document Timeline Merging**: Combine timelines from multiple sources with conflict resolution
- [ ] **Entity-Event Linking**: Connect timeline events to extracted entities (who was involved in each event)
- [x] **Geospatial Analysis**: (Completed ✅)
  - [x] **Geocoding Service**: Convert location entities to coordinates (using Nominatim)
  - [x] **Interactive Map**: Visualize entities on a global map with filtering by type and mention count
  - [x] **Batch Processing**: Background script to geocode entities efficiently
- [ ] **Project/Case System**: (Priority High 🔴)
  - **Case Isolation**: Separate workspaces for different investigations to prevent data pollution.
  - **Case Switching**: Easy UI to switch between active cases.
- [ ] **Investigative Lenses**:
  - **Speculation Mode**: LLM prompt mode "What might the author be hiding?"
  - **"What's Weirdest?" Button**: One-click surfacing of the highest-anomaly document.
- [ ] **Infrastructure Hardening (Phase 1)**:
  - **Structured Logging**: Comprehensive logging for debugging.
- [ ] **Multilingual Support**:
  - **Offline Translation**: Translate foreign documents to English (using Qwen-VL or NLLB).
- [ ] **Data Refinement**:
  - **OCR Correction UI**: Manually fix OCR errors to improve search index.
- [ ] **Consistency Checking**:
  - **Fact Checking**: Cross-reference claims against other documents.
  - **Stylometry**: Detect voice changes (e.g., multiple authors in one doc).
- [ ] **Numeric Value Analysis**:
  - **Value Extraction**: Extract all monetary amounts and quantities.
  - **Discrepancy Detection**: "Contract says $5M, Invoice says $4.5M".
- [ ] **Security Hardening**:
  - **File Type Validation**: Strict validation to prevent malicious uploads.

## v0.4: The "Watchdog" Update (Statistical Anomaly)

*Focus: Deep statistical analysis and secure team collaboration.*

> [!IMPORTANT]
> ArkhamMirror will ALWAYS be local-first. "Collaboration" means allowing a team of journalists to work together on a private, self-hosted server (LAN/VPN), NOT sending data to a public cloud.

- [ ] **Advanced Anomaly Detection**:
  - **Local Outlier Factor (LOF)**: Detect documents that are statistically distant from their clusters.
  - **Autoencoders**: Identify "unique" documents that don't fit standard patterns.
  - **Paraphrase Detection**: Find leaks by identifying re-worded content across documents.
  - **Temporal Anomaly Detection**: Flag events happening at unusual times or frequencies
  - **Red Flag Discovery Mode**: LLM heuristics for "ghost entities", linguistic shifts, and suspicious omissions.
- [ ] **Contradiction Engine**:
  - **Cross-Document Fact Comparison**: "Show me every doc that disagrees with File X on dates/numbers".
  - **Contradiction Detection**: Explicit LLM-based pairwise comparison of claims.
- [ ] **Infrastructure Hardening (Phase 2)**:
  - **Async Search**: Non-blocking UI for long queries.
  - **Caching**: Cache embeddings and query results.
  - **Pagination**: Handle large result sets gracefully.
- [ ] **Local User Auth**: Simple user accounts for team access on a shared local server.
- [ ] **Annotation System**: Highlight and comment on documents shared within the private network.
- [ ] **Headless API**: Decouple the backend (FastAPI) to allow custom local interfaces or integration with other offline tools.

## v0.5: The "Synthesizer" Update (Planned)

*Focus: Deep understanding, narrative reconstruction, and missing data inference.*

- [ ] **Shadow Gap Analyzer**: Infer missing content (what's *not* being said).
- [ ] **Big Picture Engine**: Multi-document narrative synthesis ("Tell me the overall story").
- [ ] **Influence Constellation Maps**: Enhanced graph with directionality and "gravity wells".
- [ ] **Document Version Comparison**: Diff tools for tracking changes between document drafts.
- [ ] **Template Detection**: Identify form letters and boilerplate across the corpus.
- [ ] **Citation Network**: Build a graph of document-to-document references/footnotes.

## v0.6: The "Publisher" Update (Planned)

*Focus: Export, reporting, and external integration.*

- [ ] **Redaction Detection**: Identify and analyze redacted sections.
- [ ] **Export Package**: One-click export of investigation artifacts (timeline, graph, docs) for legal/editor review.
- [ ] **Batch Query Mode**: Run structured questions against all documents (CSV export).
- [ ] **Hypothesis Generator**: "What could explain these documents?" mode.

## Future Ideas

- **Face Recognition**: Identify people in photos across documents.
- **Audio Fingerprinting**: Match audio clips.
- **Dark Web Scraper**: Optional module to pull data from onion sites.
- **Handwriting Clustering**: Group documents by handwriting style.
- **Conspiracy Graph Builder**: Experimental "wild" connection mode.
- **Interactive Cluster Map**: 3D UMAP/t-SNE visualization of document embeddings.
