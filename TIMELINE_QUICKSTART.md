# Timeline Analysis - Quick Start Guide

## What's New in v0.3

ArkhamMirror now automatically extracts temporal information from your documents, including:
- **Events with dates** (meetings, transactions, communications, etc.)
- **All date mentions** (for granular temporal analysis)
- **Timeline gaps** (suspicious periods with no activity)
- **Date-filtered search** (find documents within a specific time range)

---

## Getting Started

### 1. Run Database Migration (One-Time Setup)

```bash
cd arkham_mirror
python backend/db/migrate_timeline.py
```

This adds two new tables to your database:
- `timeline_events` - Extracted events with dates and descriptions
- `date_mentions` - All date references found in text

### 2. Process Your Documents

Timeline extraction happens automatically during document processing:

1. Upload documents via Streamlit UI (drag and drop)
2. Click "🚀 Spawn Worker" in the sidebar
3. Wait for processing to complete

**Note**: Only newly processed documents will have timeline data. Existing documents need to be reprocessed.

---

## Using Timeline Features

### View Timeline Analysis

Navigate to: **Pages → 4_Visualizations.py → Timeline Analysis**

Three views available:

#### 1. Event Timeline
- Interactive scatter plot showing all extracted events
- **Filter by**:
  - Event type (meeting, transaction, communication, deadline, incident, other)
  - Confidence threshold (0-1)
  - Max events to display
- **Features**:
  - Hover over points to see event details
  - Events sized by confidence score
  - Color-coded by event type
  - Detailed table below the chart

#### 2. Date Distribution
- Histogram showing frequency of date mentions by year
- **Statistics**:
  - Total date mentions
  - Earliest date found
  - Latest date found
- **Use case**: Identify which time periods are most referenced in your document corpus

#### 3. Gap Analysis
- Detect suspicious temporal gaps in your timeline
- **Configurable threshold**: Set minimum gap size (7-365 days)
- **Output**:
  - List of gaps with duration
  - Events before and after each gap
  - Visual timeline showing gaps
- **Use case**: Find "missing months" or suspicious periods with no documentation

### Search by Date Range

Navigate to: **Search.py → Expand "🔎 Search Options"**

1. Check "Filter by date range"
2. Select start and end dates
3. Search will only return documents with events in that range
4. See count of matching documents before searching

**Note**: Date filtering works with all other search filters (project, document selection, etc.)

---

## How Timeline Extraction Works

### Date Extraction

**Method**: Regex-based pattern matching

**Supported formats**:
- Full dates: `March 15, 2023`, `15 March 2023`, `03/15/2023`, `2023-03-15`
- Month/Year: `March 2023`, `03/2023`
- Year only: `2023`
- Relative: `yesterday`, `last week`, `two months ago`

**Precision levels**:
- `day`: Exact date known (March 15, 2023)
- `month`: Month and year known (March 2023)
- `year`: Only year known (2023)
- `approximate`: Relative dates or fuzzy references

### Event Extraction

**Method**: LLM-based extraction (uses local Qwen-VL via LM Studio)

**Extracted information**:
- Event description (concise 1-sentence summary)
- Date or time period
- Event type classification
- Confidence score (0-1)

**Event types**:
- `meeting`: Board meetings, conferences, discussions
- `transaction`: Payments, transfers, deals, contracts
- `communication`: Emails, calls, messages
- `deadline`: Due dates, expiration dates, cutoff times
- `incident`: Accidents, violations, breaches, problems
- `other`: Unclassified events

**Fallback**: If LLM is unavailable, date mentions are still extracted via regex.

---

## Examples

### Investigative Use Cases

#### 1. Timeline Reconstruction
**Scenario**: You have emails, memos, and transaction records from a corporate investigation.

**Workflow**:
1. Upload all documents
2. Go to Timeline Analysis → Event Timeline
3. Sort events chronologically
4. Export to external tool or take screenshots for report

**Result**: Complete chronological reconstruction of events

#### 2. Finding "Missing Months"
**Scenario**: Suspect documents have been destroyed or withheld.

**Workflow**:
1. Go to Timeline Analysis → Gap Analysis
2. Set threshold to 30 days
3. Review flagged gaps
4. Investigate why no documents exist for those periods

**Result**: Identify suspicious timeline gaps

#### 3. Focused Document Review
**Scenario**: You only care about documents from Q1 2023.

**Workflow**:
1. Go to Search.py
2. Enable date filter: 2023-01-01 to 2023-03-31
3. Search for relevant keywords
4. Only get results from that time period

**Result**: Faster review, less noise

---

## Troubleshooting

### No Timeline Events Found

**Possible causes**:
1. Documents haven't been processed yet (timeline extraction happens during parsing)
2. Documents contain no dates or events
3. LLM service (LM Studio) is not running

**Solutions**:
- Check document processing status in Overview page
- Ensure LM Studio is running on `http://localhost:1234`
- Check worker logs for timeline extraction errors

### Low Confidence Events

**Why**: LLM is uncertain about event classification or date extraction

**Solutions**:
- Increase confidence threshold in filters (only show high-confidence events)
- Manually review low-confidence events to verify accuracy
- Check source text for ambiguous language

### Incorrect Date Parsing

**Why**: Fuzzy date parsing can misinterpret ambiguous formats

**Example**: "02/03/2023" could be Feb 3 or March 2

**Workaround**:
- Use Date Mentions table to see raw date strings
- Verify against original document
- Future enhancement: Locale-aware date parsing

---

## Performance Notes

### Processing Time Impact

Timeline extraction adds approximately:
- **200ms per chunk** (text chunk of ~512 characters)
- **1-2 minutes** for a 100-page document

**Total pipeline**: Upload → Split → OCR → Parse+Timeline → Embed

### Optimization Tips

1. **Disable timeline extraction** if not needed:
   - Comment out lines 90-113 in `backend/workers/parser_worker.py`
   - Re-enable later and reprocess documents

2. **Batch processing**: Process documents overnight for large corpora

3. **LLM fallback**: If LLM is slow/unavailable, date mentions still work (regex-based)

---

## Next Steps

### Recommended Workflow

1. ✅ Run migration: `python backend/db/migrate_timeline.py`
2. ✅ Upload sample documents (start with 5-10 documents)
3. ✅ Process and verify timeline extraction works
4. ✅ Explore Timeline Analysis visualizations
5. ✅ Try date-filtered search
6. ✅ Process full document corpus

### Advanced Features (Future)

- Export timeline to CSV/JSON
- Link timeline events to entities (people/organizations involved)
- Multi-document timeline merging
- Temporal anomaly detection (events happening at unusual times)

---

## Feedback & Issues

Found a bug or have a feature request? Check the project's issue tracker or AI coordination system for reporting.

**Common requests**:
- Export timeline to external formats ✅ Planned for v0.4
- Entity-event linking ✅ Planned for v0.4
- Custom event types ✅ Configurable in future releases
