# Entities Shard

Entity browser and management shard for the SHATTERED/ArkhamFrame architecture.

## Overview

The Entities shard provides a comprehensive interface for browsing, managing, and resolving entities extracted from documents. It supports entity merging, relationship management, and canonical entity resolution.

## Features

### Entity Browsing
- **Type Filtering**: Filter entities by type (PERSON, ORGANIZATION, LOCATION, etc.)
- **Search**: Search entities by name, aliases, or mention text
- **Mention Tracking**: View all document mentions for each entity
- **Detail View**: See complete entity information with metadata

### Entity Management
- **Edit Entities**: Update entity names, types, and metadata
- **Merge Duplicates**: Combine duplicate entities into canonical form
- **Create Relationships**: Link entities with typed relationships
- **Canonical Resolution**: Maintain authoritative entity records

### Entity Types

Supported entity types:
- `PERSON` - Individual people
- `ORGANIZATION` - Companies, agencies, groups
- `LOCATION` - Places, addresses, geographic locations
- `DATE` - Temporal references
- `MONEY` - Monetary amounts
- `EVENT` - Named events
- `PRODUCT` - Products or services
- `DOCUMENT` - Referenced documents
- `CONCEPT` - Abstract concepts
- `OTHER` - Other entity types

### Relationship Types

Supported relationship types:
- `WORKS_FOR` - Employment relationship
- `LOCATED_IN` - Geographic relationship
- `MEMBER_OF` - Membership relationship
- `OWNS` - Ownership relationship
- `RELATED_TO` - Generic relationship
- `MENTIONED_WITH` - Co-occurrence relationship

## API Endpoints

### Entity Management

```
GET    /api/entities/items              # List entities with pagination/filtering
GET    /api/entities/items/{id}         # Get entity details
PUT    /api/entities/items/{id}         # Update entity
DELETE /api/entities/items/{id}         # Delete entity
GET    /api/entities/count               # Get total entity count
```

### Entity Merging

```
GET    /api/entities/duplicates         # Get potential duplicate entities
POST   /api/entities/merge              # Merge entities into canonical form
GET    /api/entities/merge-suggestions  # Get AI-suggested merges (requires vectors)
```

### Relationships

```
GET    /api/entities/relationships              # List relationships
POST   /api/entities/relationships              # Create relationship
DELETE /api/entities/relationships/{id}         # Delete relationship
GET    /api/entities/{id}/relationships         # Get entity relationships
```

### Mentions

```
GET    /api/entities/{id}/mentions      # Get all mentions for entity
```

## Events

### Published Events

- `entities.entity.viewed` - Entity detail page viewed
- `entities.entity.merged` - Entities merged into canonical form
- `entities.entity.edited` - Entity metadata updated
- `entities.relationship.created` - Relationship created between entities
- `entities.relationship.deleted` - Relationship removed

### Subscribed Events

- `parse.entity.created` - New entity extracted from document
- `parse.entity.updated` - Entity mention updated

## Dependencies

### Required Services
- **database**: Entity storage and persistence
- **events**: Event publishing for entity changes

### Optional Services
- **vectors**: Similarity-based merge suggestions (enables smart duplicate detection)
- **entities**: Frame's EntityService (provides advanced entity resolution features)

## UI Routes

### Main Routes
- `/entities` - Entity browser (list view)
- `/entities/:id` - Entity detail view

### Sub-routes
- `/entities/merge` - Merge duplicates interface
- `/entities/relationships` - Relationship browser

## Installation

```bash
cd packages/arkham-shard-entities
pip install -e .
```

The shard will be automatically discovered by ArkhamFrame on next restart.

## Usage

### Browsing Entities

```python
# Via API
GET /api/entities/items?page=1&page_size=20&filter=PERSON&sort=name
```

### Merging Entities

```python
# Merge duplicate entities
POST /api/entities/merge
{
  "entity_ids": ["entity-1", "entity-2", "entity-3"],
  "canonical_id": "entity-1",  # Which entity to keep
  "canonical_name": "John Smith"
}
```

### Creating Relationships

```python
# Create relationship between entities
POST /api/entities/relationships
{
  "source_id": "entity-1",
  "target_id": "entity-2",
  "relationship_type": "WORKS_FOR",
  "confidence": 0.9
}
```

## Database Schema

Entities are stored in the `arkham_entities` schema:

```sql
-- Entities table
arkham_entities.entities (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  canonical_id UUID,  -- Points to canonical entity if merged
  aliases TEXT[],
  metadata JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Entity mentions (links to documents)
arkham_entities.mentions (
  id UUID PRIMARY KEY,
  entity_id UUID REFERENCES entities(id),
  document_id UUID,
  mention_text TEXT,
  confidence FLOAT,
  start_offset INT,
  end_offset INT
)

-- Entity relationships
arkham_entities.relationships (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES entities(id),
  target_id UUID REFERENCES entities(id),
  relationship_type TEXT,
  confidence FLOAT,
  metadata JSONB
)
```

## Development

### Testing

```bash
pytest tests/
```

### Type Checking

```bash
mypy arkham_shard_entities/
```

## Architecture Notes

- **No Shard Dependencies**: This shard does NOT import other shards directly
- **Event-Driven**: Listens to parse shard events via EventBus only
- **Frame Services**: Uses Frame's database and event services
- **Canonical Entities**: Merged entities maintain references to canonical entity
- **Mention Tracking**: Preserves all original mentions even after merge

## License

Part of the SHATTERED project.
