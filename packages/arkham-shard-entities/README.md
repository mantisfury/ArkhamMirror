# arkham-shard-entities

> Entity browser with merge, link, and relationship management

**Version:** 0.1.0
**Category:** Data
**Frame Requirement:** >=0.1.0

## Overview

The Entities shard provides entity management and resolution capabilities for SHATTERED. It offers browsing, editing, merging of duplicate entities, relationship management, and mention tracking across documents.

### Key Capabilities

1. **Entity Management** - Browse, edit, and delete extracted entities
2. **Duplicate Detection** - Find and merge similar entities
3. **Relationship Management** - Create and manage entity relationships
4. **Mention Tracking** - Track entity occurrences across documents
5. **AI Analysis** - AI Junior Analyst for entity pattern analysis

## Features

### Entity Management
- List entities with pagination, sorting, and filtering
- Search by entity name
- Filter by entity type
- View entity details with mention counts
- Edit entity name, type, aliases, metadata
- Delete entities

### Entity Types
- `PERSON` - People names
- `ORGANIZATION` - Companies, institutions
- `GPE` - Geopolitical entities (countries, cities)
- `LOCATION` - Geographic locations
- `DATE` - Dates and times
- `MONEY` - Monetary values
- `PRODUCT` - Products and services
- And more (NER model dependent)

### Duplicate Detection
- Fuzzy string matching (Levenshtein distance)
- Vector similarity matching (when vectors service available)
- Configurable similarity threshold
- Merge candidate suggestions

### Entity Merging
- Merge multiple entities into canonical entity
- Preserve aliases from merged entities
- Update mention references
- Batch merge operations

### Relationship Management
- Create relationships between entities
- Multiple relationship types
- Confidence scoring
- View relationships by entity

### Relationship Types
- `WORKS_FOR` - Employment
- `LOCATED_IN` - Geographic location
- `MEMBER_OF` - Membership
- `OWNS` - Ownership
- `RELATED_TO` - General relationship
- `MENTIONED_WITH` - Co-occurrence
- `PARENT_OF` / `CHILD_OF` - Hierarchical
- `SAME_AS` - Identity
- `PART_OF` - Component
- `OTHER` - Custom

## Installation

```bash
pip install -e packages/arkham-shard-entities
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/entities/health` | Health check |
| GET | `/api/entities/count` | Entity count (badge) |

### Entity CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/entities/items` | List entities |
| GET | `/api/entities/items/{id}` | Get entity |
| PUT | `/api/entities/items/{id}` | Update entity |
| DELETE | `/api/entities/items/{id}` | Delete entity |

### Duplicate Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/entities/duplicates` | Find potential duplicates |
| GET | `/api/entities/merge-suggestions` | AI-suggested merges |
| POST | `/api/entities/merge` | Merge entities |
| POST | `/api/entities/batch/merge` | Batch merge |

### Relationships

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/entities/relationships` | List relationships |
| GET | `/api/entities/relationships/types` | Get relationship types |
| GET | `/api/entities/relationships/stats` | Relationship statistics |
| POST | `/api/entities/relationships` | Create relationship |
| DELETE | `/api/entities/relationships/{id}` | Delete relationship |
| GET | `/api/entities/{id}/relationships` | Get entity's relationships |

### Mentions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/entities/{id}/mentions` | Get entity mentions |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/entities/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### List Entities with Filtering

```bash
GET /api/entities/items?page=1&page_size=20&filter=PERSON&q=john
```

Response:
```json
{
  "items": [
    {
      "id": "ent_123",
      "name": "John Smith",
      "entity_type": "PERSON",
      "canonical_id": null,
      "aliases": ["J. Smith", "Johnny Smith"],
      "metadata": {},
      "mention_count": 15,
      "created_at": "2024-12-15T10:30:00Z",
      "updated_at": "2024-12-15T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Find Duplicates

```bash
GET /api/entities/duplicates?entity_type=PERSON&threshold=0.8&limit=50
```

Response:
```json
[
  {
    "entity_a": {"id": "ent_123", "name": "John Smith", "entity_type": "PERSON"},
    "entity_b": {"id": "ent_456", "name": "Jon Smith", "entity_type": "PERSON"},
    "similarity_score": 0.92,
    "reason": "Very similar names (possible typo)",
    "common_mentions": 0,
    "common_documents": 0
  }
]
```

### Merge Entities

```json
POST /api/entities/merge
{
  "entity_ids": ["ent_123", "ent_456", "ent_789"],
  "canonical_id": "ent_123",
  "canonical_name": "John Smith"
}
```

### Create Relationship

```json
POST /api/entities/relationships
{
  "source_id": "ent_person_123",
  "target_id": "ent_org_456",
  "relationship_type": "WORKS_FOR",
  "confidence": 0.95,
  "metadata": {"position": "CEO"}
}
```

### Get Entity Mentions

```bash
GET /api/entities/ent_123/mentions?page=1&page_size=50
```

Response includes document IDs, mention text, and offsets.

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `entities.entity.viewed` | Entity detail viewed |
| `entities.entity.merged` | Entities merged |
| `entities.entity.edited` | Entity updated |
| `entities.entity.deleted` | Entity deleted |
| `entities.relationship.created` | Relationship created |
| `entities.relationship.deleted` | Relationship deleted |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `parse.entity.created` | Track new extracted entities |
| `parse.entity.updated` | Update entity information |

## UI Routes

| Route | Description |
|-------|-------------|
| `/entities` | All entities list |
| `/entities/merge` | Merge duplicates interface |
| `/entities/relationships` | Relationships view |

## Dependencies

### Required Services
- **database** - Entity storage and persistence
- **events** - Event publishing

### Optional Services
- **vectors** - Vector similarity for merge suggestions
- **entities** - Frame's EntityService for advanced features

## URL State

| Parameter | Description |
|-----------|-------------|
| `entityId` | Active entity ID |
| `view` | View mode (list, detail, merge, relationships) |
| `filter` | Entity type filter |

### Local Storage Keys
- `column_widths` - Column width preferences
- `show_merged` - Show merged entities toggle
- `sort_preference` - Default sort preference

## Similarity Algorithms

### String Similarity
Uses Levenshtein (edit) distance normalized by string length:
- Exact match = 1.0
- Substring containment = 0.95 * (shorter/longer)
- Edit distance = 1.0 - (distance/max_length)

### Vector Similarity
When vectors service is available:
- Embeds both entity names
- Calculates cosine similarity
- Falls back to string similarity on failure

## Development

```bash
# Run tests
pytest packages/arkham-shard-entities/tests/

# Type checking
mypy packages/arkham-shard-entities/
```

## License

MIT
