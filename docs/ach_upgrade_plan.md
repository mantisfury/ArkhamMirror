# ACH Corpus Evidence Extraction - Implementation Plan

## Executive Summary

This plan extends the ACH shard with **Retrieval-Augmented Generation (RAG)** capabilities, allowing analysts to search their ingested document corpus for evidence relevant to hypotheses. The implementation uses existing SHATTERED infrastructure (VectorService, DocumentService, LLMService) to ground AI-generated evidence in actual document content.

---

## 1. Architecture Analysis

### Existing Infrastructure (No Changes Required to Frame)

| Service | Location | Capability |
|---------|----------|------------|
| **VectorService** | `arkham_frame/services/vectors.py` | Qdrant-based vector search with `search_text()`, `embed_text()` |
| **DocumentService** | `arkham_frame/services/documents.py` | Chunk/page retrieval with `get_document_chunks()` |
| **LLMService** | `arkham_frame/services/llm.py` | Structured JSON extraction with `extract_json()` |
| **EmbedShard** | `arkham-shard-embed` | Auto-embeds document chunks to `arkham_chunks` collection |
| **EntitiesShard** | `arkham-shard-entities` | Entity storage with `arkham_entities` table |

### Standard Vector Collections (Already Exist)

```python
COLLECTION_DOCUMENTS = "arkham_documents"  # Document-level embeddings
COLLECTION_CHUNKS = "arkham_chunks"        # Chunk-level embeddings (PRIMARY)
COLLECTION_ENTITIES = "arkham_entities"    # Entity embeddings
```

### Key Finding

The infrastructure is already RAG-ready. The `arkham_chunks` collection contains embedded text chunks with metadata linking to source documents. We need only add orchestration logic in the ACH shard.

---

## 2. Data Flow Design

```
                         ACH CORPUS EXTRACTION FLOW

 User selects hypothesis    +-----------------------+
           |                |  ACH Shard (New)      |
           v                |  CorpusSearchService  |
 +-------------------+      +-----------+-----------+
 | Hypothesis Text   |                  |
 | "The breach was   |                  |
 |  caused by vendor"|                  |
 +--------+----------+                  |
          |                             |
          v                             v
 +-------------------+      +-----------------------+
 | VectorService     |----->| arkham_chunks         |
 | search_text()     |      | (Qdrant collection)   |
 +--------+----------+      +-----------------------+
          |                             |
          | Top N chunks (default: 30)  |
          v                             v
 +-------------------+      +-----------------------+
 | DocumentService   |----->| arkham_frame.chunks   |
 | get_document_     |      | (PostgreSQL table)    |
 | chunks()          |      +-----------------------+
 +--------+----------+
          |
          | Chunk text + metadata
          v
 +-------------------+
 | LLMService        |
 | extract_json()    |
 | - Classify: supports/contradicts/neutral
 | - Extract exact quotes
 | - Rate relevance
 +--------+----------+
          |
          | Structured evidence candidates
          v
 +-------------------+
 | User Review       |
 | - Accept/Reject   |
 | - Bulk actions    |
 +--------+----------+
          |
          v
 +-------------------+
 | ACH Matrix        |
 | Evidence added    |
 | with source links |
 +-------------------+
```

---

## 3. Implementation Phases

### Phase 1: Core Extraction (MVP)

**Goal**: Single hypothesis search, top 30 chunks, manual review

#### 3.1.1 New Files to Create

```
packages/arkham-shard-ach/arkham_shard_ach/
├── corpus.py          # CorpusSearchService class
├── prompts.py         # Evidence extraction prompts (new)
└── models.py          # Add ExtractedEvidence model
```

#### 3.1.2 CorpusSearchService Class

```python
# corpus.py

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class EvidenceRelevance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"

@dataclass
class ExtractedEvidence:
    """Evidence extracted from corpus."""
    quote: str                    # Exact text from chunk
    source_document_id: str
    source_document_name: str
    source_chunk_id: str
    page_number: Optional[int]
    relevance: EvidenceRelevance  # How it relates to hypothesis
    explanation: str              # Why this is relevant
    hypothesis_id: str
    similarity_score: float       # Vector similarity score
    verified: bool = False        # Quote verified in source

class CorpusSearchService:
    """Search corpus for evidence relevant to hypotheses."""

    def __init__(self, vectors_service, documents_service, llm_service):
        self.vectors = vectors_service
        self.documents = documents_service
        self.llm = llm_service

    async def search_for_evidence(
        self,
        hypothesis_text: str,
        hypothesis_id: str,
        scope: Optional[dict] = None,  # project_id, document_ids, tags
        chunk_limit: int = 30,
        min_similarity: float = 0.5,
    ) -> List[ExtractedEvidence]:
        """
        Search corpus for evidence relevant to a hypothesis.

        Args:
            hypothesis_text: The hypothesis to search for
            hypothesis_id: ID of the hypothesis
            scope: Optional scope filters
            chunk_limit: Max chunks to retrieve
            min_similarity: Minimum similarity threshold

        Returns:
            List of ExtractedEvidence candidates
        """
        # 1. Vector search for relevant chunks
        filter_dict = self._build_filter(scope)

        results = await self.vectors.search_text(
            collection="arkham_chunks",
            text=hypothesis_text,
            limit=chunk_limit,
            filter=filter_dict,
            score_threshold=min_similarity,
        )

        if not results:
            return []

        # 2. Retrieve full chunk text and document metadata
        chunks_with_context = await self._enrich_chunks(results)

        # 3. LLM analysis in batches
        evidence = await self._analyze_chunks(
            chunks_with_context,
            hypothesis_text,
            hypothesis_id
        )

        # 4. Verify quotes exist in source
        verified = await self._verify_quotes(evidence)

        return verified
```

#### 3.1.3 New API Endpoints

```python
# In api.py, add:

class CorpusSearchRequest(BaseModel):
    """Request to search corpus for evidence."""
    matrix_id: str
    hypothesis_id: str
    chunk_limit: int = 30
    min_similarity: float = 0.5
    scope: Optional[dict] = None  # {"project_id": "...", "document_ids": [...]}

class AcceptEvidenceRequest(BaseModel):
    """Accept extracted evidence into matrix."""
    matrix_id: str
    evidence: List[dict]  # ExtractedEvidence items to accept

@router.post("/ai/corpus-search")
async def search_corpus_for_evidence(request: CorpusSearchRequest):
    """Search document corpus for evidence relevant to a hypothesis."""
    ...

@router.post("/ai/accept-evidence")
async def accept_corpus_evidence(request: AcceptEvidenceRequest):
    """Add reviewed corpus evidence to the matrix."""
    ...
```

#### 3.1.4 LLM Prompt for Evidence Classification

```python
# prompts.py

EVIDENCE_EXTRACTION_PROMPT = """You are an intelligence analyst reviewing document excerpts for evidence relevant to a hypothesis.

HYPOTHESIS: {hypothesis}

DOCUMENT EXCERPTS:
{chunks}

For each excerpt that contains relevant evidence, extract:
1. The exact quote from the text (use quotation marks, no paraphrasing)
2. Classification: supports, contradicts, neutral, or ambiguous
3. Brief explanation of relevance (1-2 sentences)

IMPORTANT:
- Only use text that actually appears in the excerpts
- If an excerpt has no relevant evidence, skip it
- Be objective - look for evidence that could support OR contradict
- Rate ambiguous if the evidence could be interpreted multiple ways

Respond with JSON array:
[
  {
    "chunk_index": 0,
    "quote": "exact text from document",
    "classification": "supports|contradicts|neutral|ambiguous",
    "explanation": "Why this is relevant to the hypothesis"
  }
]

If no relevant evidence found, respond with: []
"""
```

#### 3.1.5 Evidence Model Updates

```python
# In models.py, update Evidence dataclass:

@dataclass
class Evidence:
    """Evidence item in an ACH matrix."""
    id: str
    matrix_id: str
    description: str

    # Source information
    source: str = ""
    evidence_type: EvidenceType = EvidenceType.FACT

    # Corpus extraction fields (NEW)
    source_document_id: Optional[str] = None
    source_chunk_id: Optional[str] = None
    source_page_number: Optional[int] = None
    source_quote: Optional[str] = None     # Original extracted quote
    extraction_method: str = "manual"       # "manual" | "corpus" | "ai"
    similarity_score: Optional[float] = None

    # Existing fields...
    credibility: float = 1.0
    relevance: float = 1.0
    row_index: int = 0
    document_ids: list[str] = field(default_factory=list)
```

---

### Phase 2: Enhanced Control

**Goal**: Configurable limits, scope filtering, bulk accept/reject

#### 3.2.1 Scope Filtering Options

```python
@dataclass
class SearchScope:
    """Scope for corpus search."""
    project_id: Optional[str] = None      # Filter by project
    document_ids: Optional[List[str]] = None  # Specific documents
    date_from: Optional[datetime] = None  # Date range
    date_to: Optional[datetime] = None
    mime_types: Optional[List[str]] = None  # PDF only, etc.
    exclude_documents: Optional[List[str]] = None  # Exclude specific docs
```

#### 3.2.2 Configurable Settings

```python
@dataclass
class CorpusSearchConfig:
    """Configuration for corpus search."""
    chunk_limit: int = 30
    min_similarity: float = 0.5
    max_chunks_per_document: int = 5  # Prevent single doc domination
    dedupe_threshold: float = 0.9     # Remove near-duplicate chunks
    batch_size: int = 10              # Chunks per LLM call
```

#### 3.2.3 Bulk Accept UI Flow

```typescript
// Frontend component for bulk accept
interface CorpusSearchResults {
  hypothesis_id: string;
  results: ExtractedEvidence[];
}

// User can:
// 1. View all results in a list
// 2. Click to expand and see source context
// 3. Select multiple items with checkboxes
// 4. "Accept Selected" button to add to matrix
// 5. "Accept All" button for bulk add
```

---

### Phase 3: Advanced Features

**Goal**: Multi-hypothesis search, contradiction detection, auto-suggestions

#### 3.3.1 Multi-Hypothesis Batch Search

```python
async def search_all_hypotheses(
    self,
    matrix: ACHMatrix,
    scope: Optional[SearchScope] = None,
    chunk_limit_per_hypothesis: int = 20,
) -> Dict[str, List[ExtractedEvidence]]:
    """
    Search corpus for evidence relevant to all hypotheses.

    Runs searches in parallel and deduplicates results
    (same chunk can be relevant to multiple hypotheses).
    """
    tasks = []
    for hypothesis in matrix.hypotheses:
        tasks.append(
            self.search_for_evidence(
                hypothesis.title + " " + hypothesis.description,
                hypothesis.id,
                scope,
                chunk_limit_per_hypothesis,
            )
        )

    results = await asyncio.gather(*tasks)

    # Organize by hypothesis and cross-link shared evidence
    return self._organize_and_dedupe(matrix.hypotheses, results)
```

#### 3.3.2 Contradiction Detection Mode

```python
async def find_contradictions(
    self,
    matrix: ACHMatrix,
    scope: Optional[SearchScope] = None,
) -> List[Contradiction]:
    """
    Find evidence that contradicts multiple hypotheses.

    Looks for chunks where the same evidence:
    - Supports one hypothesis AND contradicts another
    - Contains conflicting claims about the same entity/event
    """
    # 1. Get evidence for all hypotheses
    all_evidence = await self.search_all_hypotheses(matrix, scope)

    # 2. Find chunks that appear for multiple hypotheses with different ratings
    contradictions = []
    seen_chunks = {}

    for hyp_id, evidence_list in all_evidence.items():
        for ev in evidence_list:
            if ev.source_chunk_id in seen_chunks:
                prev_hyp, prev_rating = seen_chunks[ev.source_chunk_id]
                if self._are_contradictory(prev_rating, ev.relevance):
                    contradictions.append(Contradiction(
                        chunk_id=ev.source_chunk_id,
                        quote=ev.quote,
                        hypothesis_a=(prev_hyp, prev_rating),
                        hypothesis_b=(hyp_id, ev.relevance),
                    ))
            else:
                seen_chunks[ev.source_chunk_id] = (hyp_id, ev.relevance)

    return contradictions
```

#### 3.3.3 Corpus-Based Hypothesis Suggestions

```python
async def suggest_hypotheses_from_corpus(
    self,
    focus_question: str,
    scope: Optional[SearchScope] = None,
    max_suggestions: int = 5,
) -> List[HypothesisSuggestion]:
    """
    Suggest hypotheses based on themes in the corpus.

    1. Search corpus for chunks relevant to focus question
    2. Cluster by semantic similarity
    3. Ask LLM to identify distinct hypothesis themes
    """
    # Get broad set of relevant chunks
    chunks = await self.vectors.search_text(
        collection="arkham_chunks",
        text=focus_question,
        limit=100,
        filter=self._build_filter(scope),
    )

    # Cluster chunks (simple approach: top 3 from each document)
    # OR use k-means on embeddings for better clustering

    # LLM: identify distinct hypothesis themes
    prompt = HYPOTHESIS_DISCOVERY_PROMPT.format(
        question=focus_question,
        chunks=self._format_chunks_for_prompt(chunks),
    )

    return await self.llm.extract_json(prompt)
```

---

## 4. Entity Integration

### 4.1 Entity-Aware Search

When searching for evidence, also search the entity collection:

```python
async def search_with_entities(
    self,
    hypothesis_text: str,
    hypothesis_id: str,
) -> List[ExtractedEvidence]:
    """
    Enhanced search that also queries entity mentions.

    If hypothesis mentions a person/org, find documents
    where that entity appears and search those more deeply.
    """
    # 1. Extract entities from hypothesis
    entities = await self._extract_entities_from_text(hypothesis_text)

    # 2. Find documents containing those entities
    entity_docs = await self._find_documents_with_entities(entities)

    # 3. Prioritize chunks from those documents
    scope = {"document_ids": entity_docs[:10]}

    # 4. Regular corpus search with entity-aware scope
    return await self.search_for_evidence(
        hypothesis_text,
        hypothesis_id,
        scope=scope,
    )
```

### 4.2 Entity Table Queries

```python
async def _find_documents_with_entities(
    self,
    entity_names: List[str],
) -> List[str]:
    """Find documents where these entities are mentioned."""
    # Query arkham_entities table
    query = """
        SELECT DISTINCT document_ids
        FROM arkham_entities
        WHERE LOWER(name) = ANY(:names)
        AND canonical_id IS NULL
    """

    rows = await self.db.fetch_all(
        query,
        {"names": [n.lower() for n in entity_names]}
    )

    # Flatten document_ids from JSONB arrays
    doc_ids = []
    for row in rows:
        doc_ids.extend(row["document_ids"] or [])

    return list(set(doc_ids))
```

---

## 5. UI Integration

### 5.1 Button Placement

Add corpus search buttons alongside existing LLM assist buttons:

```typescript
// In ACHMatrix component, add button per hypothesis:
<Button onClick={() => searchCorpus(hypothesis.id)}>
  <SearchIcon /> Search Corpus
</Button>

// Or global button for all hypotheses:
<Button onClick={searchAllHypotheses}>
  <SearchIcon /> Find Evidence in Documents
</Button>
```

### 5.2 Results Display Component

```typescript
// CorpusEvidenceResults.tsx
interface Props {
  results: ExtractedEvidence[];
  onAccept: (evidence: ExtractedEvidence[]) => void;
  onReject: (evidence: ExtractedEvidence) => void;
}

function CorpusEvidenceResults({ results, onAccept, onReject }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  return (
    <div className="corpus-results">
      <div className="header">
        <span>{results.length} potential evidence items found</span>
        <Button onClick={() => onAccept(getSelected())}>
          Accept Selected ({selected.size})
        </Button>
      </div>

      {results.map(ev => (
        <EvidenceCard
          key={ev.source_chunk_id}
          evidence={ev}
          selected={selected.has(ev.source_chunk_id)}
          onSelect={() => toggleSelect(ev.source_chunk_id)}
          onViewSource={() => openDocumentViewer(ev.source_document_id, ev.page_number)}
        />
      ))}
    </div>
  );
}
```

### 5.3 Source Context Viewer

```typescript
// When user clicks "View Source", show chunk in document context
interface SourceViewer {
  documentId: string;
  chunkId: string;
  pageNumber: number;
  highlightText: string;  // The quoted text to highlight
}

// Could reuse Documents shard viewer if available,
// or implement simple text view with highlight
```

---

## 6. Export Updates

### 6.1 HTML Export Enhancement

Update export.py to include source links for corpus-extracted evidence:

```python
def _format_evidence_source(self, evidence: Evidence) -> str:
    """Format evidence source for export."""
    if evidence.extraction_method == "corpus":
        return f"Document: {evidence.source_document_id}, p.{evidence.source_page_number}"
    return evidence.source or "Manual entry"
```

### 6.2 Add Source Column to Matrix Table

```html
<!-- In HTML export, add source info -->
<th>Evidence</th>
<th>Source</th>  <!-- NEW -->
<th>H1</th>
...
```

---

## 7. Validation & Quality

### 7.1 Quote Verification

Always verify extracted quotes exist in source:

```python
async def _verify_quotes(
    self,
    evidence: List[ExtractedEvidence],
) -> List[ExtractedEvidence]:
    """
    Verify extracted quotes actually exist in source chunks.
    Uses fuzzy matching to handle minor LLM paraphrasing.
    """
    from difflib import SequenceMatcher

    verified = []
    for ev in evidence:
        # Get original chunk text
        chunk = await self.documents.get_chunk(ev.source_chunk_id)
        if not chunk:
            ev.verified = False
            continue

        # Fuzzy match quote in chunk
        ratio = SequenceMatcher(
            None,
            ev.quote.lower(),
            chunk.text.lower()
        ).ratio()

        if ratio > 0.85:  # 85% similarity threshold
            ev.verified = True
        else:
            # Try finding quote as substring
            if ev.quote.lower() in chunk.text.lower():
                ev.verified = True
            else:
                ev.verified = False
                logger.warning(f"Quote not found in source: {ev.quote[:50]}...")

        verified.append(ev)

    return verified
```

### 7.2 Duplicate Detection

Check if evidence already exists in matrix:

```python
async def _check_duplicates(
    self,
    matrix: ACHMatrix,
    evidence: List[ExtractedEvidence],
) -> List[ExtractedEvidence]:
    """
    Flag evidence that might duplicate existing matrix evidence.
    Uses semantic similarity to catch paraphrased duplicates.
    """
    existing_embeddings = await self._embed_existing_evidence(matrix)

    for ev in evidence:
        ev_embedding = await self.vectors.embed_text(ev.quote)

        for existing in matrix.evidence:
            existing_emb = existing_embeddings.get(existing.id)
            if existing_emb:
                similarity = cosine_similarity(ev_embedding, existing_emb)
                if similarity > 0.85:
                    ev.possible_duplicate = existing.id

    return evidence
```

---

## 8. Performance Considerations

### 8.1 Chunk Retrieval Batching

```python
# Retrieve chunks in batches to avoid overwhelming DB
async def _enrich_chunks(self, search_results: List[SearchResult]) -> List[dict]:
    BATCH_SIZE = 20
    enriched = []

    for i in range(0, len(search_results), BATCH_SIZE):
        batch = search_results[i:i+BATCH_SIZE]
        chunk_ids = [r.id for r in batch]

        # Batch query for chunk texts
        chunks = await self.documents.get_chunks_by_ids(chunk_ids)

        for result, chunk in zip(batch, chunks):
            enriched.append({
                "chunk": chunk,
                "similarity_score": result.score,
                "payload": result.payload,
            })

    return enriched
```

### 8.2 LLM Batching

```python
# Process chunks in batches for LLM analysis
async def _analyze_chunks(
    self,
    chunks: List[dict],
    hypothesis: str,
    hypothesis_id: str,
) -> List[ExtractedEvidence]:
    BATCH_SIZE = 10  # ~5000 tokens per batch
    all_evidence = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]

        prompt = EVIDENCE_EXTRACTION_PROMPT.format(
            hypothesis=hypothesis,
            chunks=self._format_chunks(batch),
        )

        try:
            result = await self.llm.extract_json(prompt)
            evidence = self._parse_llm_response(result, batch, hypothesis_id)
            all_evidence.extend(evidence)
        except Exception as e:
            logger.error(f"LLM batch failed: {e}")
            # Continue with other batches

    return all_evidence
```

### 8.3 Caching

```python
# Cache embeddings for frequently searched hypotheses
from functools import lru_cache

@lru_cache(maxsize=100)
async def _get_hypothesis_embedding(self, hypothesis_text: str) -> List[float]:
    return await self.vectors.embed_text(hypothesis_text)
```

---

## 9. Questions Resolved

Based on the proposal questions, here are the decisions:

| Question | Decision | Rationale |
|----------|----------|-----------|
| Where should orchestration live? | ACH shard (new `corpus.py`) | Keeps feature cohesive, no cross-shard dependencies |
| Cross-shard communication? | Via Frame services, not direct imports | Use `frame.get_service("vectors")` pattern |
| Mark extracted evidence differently? | Yes, `extraction_method="corpus"` | Allows filtering/display differentiation |
| Default chunk limit? | 30 | Balances thoroughness vs. speed (< 5 second target) |
| Embedding model suitability? | Yes | BGE-M3 handles question-style queries well |
| Reuse existing services? | Yes | VectorService.search_text(), DocumentService, LLMService |

---

## 10. Implementation Checklist

### Phase 1 (MVP)

- [ ] Create `corpus.py` with `CorpusSearchService` class
- [ ] Add `ExtractedEvidence` model to models.py
- [ ] Update `Evidence` dataclass with corpus fields
- [ ] Create `prompts.py` with evidence extraction prompt
- [ ] Add `/ai/corpus-search` endpoint
- [ ] Add `/ai/accept-evidence` endpoint
- [ ] Update shard.py to initialize CorpusSearchService
- [ ] Frontend: Add "Search Corpus" button per hypothesis
- [ ] Frontend: Create CorpusEvidenceResults component
- [ ] Add quote verification logic
- [ ] Add duplicate detection logic
- [ ] Test with sample documents and hypotheses

### Phase 2 (Enhanced)

- [ ] Implement SearchScope filtering
- [ ] Add configurable settings endpoint
- [ ] Implement bulk accept/reject
- [ ] Add max-per-document limit
- [ ] Add deduplication threshold
- [ ] Update export to include source links
- [ ] Frontend: Scope selection UI
- [ ] Frontend: Settings panel

### Phase 3 (Advanced)

- [ ] Multi-hypothesis batch search
- [ ] Contradiction detection mode
- [ ] Corpus-based hypothesis suggestions
- [ ] Entity-aware search enhancement
- [ ] Evidence clustering
- [ ] Frontend: Contradiction viewer
- [ ] Frontend: Hypothesis suggestion integration

---

## 11. API Specification

### POST /api/ach/ai/corpus-search

**Request:**
```json
{
  "matrix_id": "uuid",
  "hypothesis_id": "uuid",
  "chunk_limit": 30,
  "min_similarity": 0.5,
  "scope": {
    "project_id": "uuid",
    "document_ids": ["uuid1", "uuid2"],
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  }
}
```

**Response:**
```json
{
  "matrix_id": "uuid",
  "hypothesis_id": "uuid",
  "results": [
    {
      "quote": "The vendor had access to the network...",
      "source_document_id": "uuid",
      "source_document_name": "Security_Audit_2024.pdf",
      "source_chunk_id": "uuid",
      "page_number": 12,
      "relevance": "supports",
      "explanation": "Confirms vendor network access",
      "similarity_score": 0.87,
      "verified": true,
      "possible_duplicate": null
    }
  ],
  "search_time_ms": 2340,
  "chunks_analyzed": 30
}
```

### POST /api/ach/ai/accept-evidence

**Request:**
```json
{
  "matrix_id": "uuid",
  "evidence": [
    {
      "quote": "The vendor had access...",
      "source_document_id": "uuid",
      "source_chunk_id": "uuid",
      "relevance": "supports",
      "explanation": "Confirms vendor access"
    }
  ],
  "auto_rate": true
}
```

**Response:**
```json
{
  "matrix_id": "uuid",
  "added": 1,
  "evidence_ids": ["uuid"]
}
```

---

## 12. Dependencies

### Python Packages (Already Installed)
- `qdrant-client` - Vector search
- `sentence-transformers` - Embeddings (via VectorService)
- `httpx` - LLM HTTP client

### New Dependencies
None required. All functionality uses existing Frame services.

---

## 13. Success Metrics

1. **Speed**: < 30 seconds for typical corpus (1000 documents)
2. **Accuracy**: Zero hallucinated quotes (100% verification pass rate)
3. **Usability**: Feature discoverable via existing LLM assist pattern
4. **Integration**: Evidence links work in export (HTML, PDF)
5. **Grounding**: Every extracted piece of evidence traceable to source

---

## References

- [Enhancing RAG: A Study of Best Practices (2025)](https://arxiv.org/abs/2501.07391)
- [Chunking Strategies for RAG](https://medium.com/@adnanmasood/chunking-strategies-for-retrieval-augmented-generation-rag-a-comprehensive-guide-5522c4ea2a90)
- [Common RAG Techniques Explained - Microsoft](https://www.microsoft.com/en-us/microsoft-cloud/blog/2025/02/04/common-retrieval-augmented-generation-rag-techniques-explained/)
- Original proposal: `docs/ACH_corpus_proposal.md`
