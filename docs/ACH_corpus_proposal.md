**Proposal: ACH Corpus Evidence Extraction Feature**

---

## Overview

Add capability to extract potential evidence from the user's ingested document corpus to support ACH analysis, using vector search to find relevant chunks and LLM to identify/classify evidence.

---

## Feature Goals

1. Allow users to search their own documents for evidence relevant to specific hypotheses
2. Return cited, verifiable evidence with source links
3. Avoid LLM hallucination by grounding in actual document content
4. Keep it optional — doesn't replace manual or AI-generated evidence

---

## Architecture Requirements

### Services Needed

| Service | Role |
|---------|------|
| **VectorService** | Query embeddings for hypothesis similarity search |
| **DocumentService** | Retrieve source documents and metadata |
| **ChunkService** | Get actual chunk text for matched embeddings |
| **LLMService** | Analyze chunks, extract structured evidence |
| **ACH Shard** | Orchestrate the flow, present results, handle user acceptance |

### Data Flow

```
User selects hypothesis → 
  Embed hypothesis text →
    Vector search (top N chunks) →
      Retrieve chunk text + metadata →
        LLM analyzes for evidence →
          Return structured results →
            User reviews/accepts →
              Evidence added to matrix with source links
```

---

## Key Design Decisions to Make

### 1. Scope Selection
How does user define what to search?
- All documents - upper limit must be set to prevent overloading llm
- Current project only
- Specific tags/folders
- Hand-selected documents
- Date range

### 2. Chunk Retrieval Limits
- How many chunks to retrieve? (Suggest: configurable, default 30)
- Similarity threshold cutoff?
- How to handle ties/near-duplicates?

### 3. LLM Prompt Structure
- Single hypothesis or batch? - single
- What classification schema? (Supports / Contradicts / Neutral / Ambiguous)
- Confidence scoring? - avoid official-sounding jargon like significance and confidence levels
- How to enforce citation accuracy?

### 4. Output Format
```typescript
interface ExtractedEvidence {
  quote: string;           // Exact text from chunk
  source_document_id: string;
  source_chunk_id: string;
  page_number?: number;
  relevance: 'supports' | 'contradicts' | 'neutral';
  confidence: number;      // 0-1
  explanation: string;     // Why this is relevant
  hypothesis_id: string;   // Which hypothesis this relates to
}
```

### 5. Validation Requirements
- Verify extracted quote exists in source chunk (fuzzy match?)
- Flag if LLM appears to be paraphrasing vs quoting
- Handle cases where LLM finds nothing relevant

### 6. UI/UX Flow
- Where does this live? New tab? Button on evidence panel? - buttons like other llm assist features
- How to show progress during search?
- How to present candidates for review?
- Bulk accept/reject or one-by-one? one by one, option for bulk
- How to show source context (link to document viewer?)

---

## Edge Cases to Handle

| Case | Handling |
|------|----------|
| No relevant chunks found | "No evidence found. Try broadening search or rephrasing hypothesis." |
| Too many results | Pagination, "show more" pattern |
| Chunk references deleted document | Skip gracefully, log warning |
| LLM returns malformed response | Retry once, then show error |
| Duplicate evidence (already in matrix) | Detect and flag, let user decide |
| Very long chunks | Truncate for display, full text on click |
| Multiple hypotheses reference same evidence | Allow evidence to link to multiple hypotheses |

---

## Performance Considerations

| Concern | Mitigation |
|---------|------------|
| Slow vector search on large corpus | Index optimization, limit scope |
| LLM latency | Async with progress indicator, allow cancel |
| Token limits | Batch chunks into multiple LLM calls if needed |
| Rate limiting | Respect LLMService rate limits |

---

## Suggested Implementation Phases

### Phase 1: Basic Extraction
- Single hypothesis search
- Top 30 chunks, fixed
- Simple supports/contradicts classification
- Manual review for each result
- Add to matrix with source link

### Phase 2: Enhanced Control
- Configurable chunk limits
- Scope filtering (project, tags, selection)
- Confidence thresholds
- Bulk accept/reject

### Phase 3: Advanced Features
- Multi-hypothesis batch search
- "Find contradictions between documents" mode
- Auto-suggest hypotheses based on corpus themes
- Evidence clustering (group similar findings)

---

## Questions for Planner to Resolve

1. Which existing services/events can be reused vs need new endpoints?
2. Where should the orchestration logic live — ACH shard or new dedicated service?
3. How to handle cross-shard communication (ACH ↔ Documents ↔ Vectors)?
4. Should extracted evidence be marked differently than manual evidence in the matrix?
5. What's the right default chunk limit for balance of thoroughness vs speed?
6. Does the current embedding model capture hypothesis-style queries well, or need tuning?

---

## Success Criteria

- User can extract evidence from corpus for a hypothesis in < 30 seconds (typical corpus)
- Every piece of extracted evidence links to viewable source
- Zero hallucinated quotes (validation catches them)
- Feature is discoverable but not intrusive to existing workflow
- Works with existing ACH export (evidence sources included in report)

---

**End of proposal. Hand off to planner with full project context.**