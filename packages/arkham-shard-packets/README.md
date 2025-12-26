# Packets Shard

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

Investigation packet management shard for ArkhamFrame. Bundle and share documents, entities, and analyses for archiving, collaboration, and knowledge transfer.

## Overview

The Packets shard provides comprehensive packet management that:

1. **Creates Packets** - Bundle related investigation materials into shareable units
2. **Manages Content** - Add documents, entities, claims, evidence chains, and reports
3. **Controls Access** - Share packets with granular permissions and expiration
4. **Exports Data** - Generate portable archives for external distribution
5. **Tracks Versions** - Maintain version history with snapshots

## Key Features

### Packet Creation
- Manual packet creation with metadata
- Add multiple content types to a packet
- Organize content with ordering and grouping
- Track packet size and content count

### Packet Status Workflow
- **Status Types:**
  - `draft` - In progress, editable
  - `finalized` - Locked, ready for sharing
  - `shared` - Actively shared with others
  - `archived` - Inactive, preserved for records

### Content Types
- `document` - Full documents with metadata
- `entity` - Entity records and relationships
- `claim` - Claims with evidence chains
- `evidence_chain` - Evidence link graphs
- `matrix` - ACH matrices
- `timeline` - Temporal visualizations
- `report` - Generated reports and summaries

### Access Control
- **Visibility Levels:**
  - `private` - Creator only
  - `team` - Team members
  - `public` - Anyone with link

- **Permissions:**
  - `view` - Read-only access
  - `comment` - Can add comments
  - `edit` - Can modify (draft only)

### Packet Sharing
- Generate shareable access tokens
- Set expiration dates for shares
- Track who accessed what and when
- Revoke shares instantly

### Packet Versioning
- Create version snapshots at any time
- Track changes between versions
- Restore from previous versions
- Maintain version history

### Import/Export
- Export packets as portable archives (.zip, .tar.gz)
- Include all referenced content
- Import packets from archives
- Merge or replace on import

## Dependencies

### Required Frame Services
- **database** - Stores packets, contents, shares, and versions
- **events** - Publishes packet lifecycle events

### Optional Frame Services
- **storage** - File storage for packet exports and snapshots

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `packets.packet.created` | New packet created |
| `packets.packet.updated` | Packet metadata updated |
| `packets.packet.finalized` | Packet finalized (locked) |
| `packets.packet.shared` | Packet shared with others |
| `packets.packet.exported` | Packet exported to file |
| `packets.packet.imported` | Packet imported from file |
| `packets.content.added` | Content added to packet |
| `packets.content.removed` | Content removed from packet |
| `packets.version.created` | Version snapshot created |

### Subscribed Events

None - packets are created via API, not triggered by events.

## API Endpoints

### Packets CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/` | List packets with pagination |
| GET | `/api/packets/{id}` | Get packet details |
| POST | `/api/packets/` | Create new packet |
| PUT | `/api/packets/{id}` | Update packet metadata |
| DELETE | `/api/packets/{id}` | Delete packet |

### Packet Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/packets/{id}/finalize` | Finalize packet (lock) |
| POST | `/api/packets/{id}/archive` | Archive packet |

### Content Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/{id}/contents` | List packet contents |
| POST | `/api/packets/{id}/contents` | Add content to packet |
| DELETE | `/api/packets/{id}/contents/{content_id}` | Remove content |

### Sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/packets/{id}/share` | Create share link |
| GET | `/api/packets/{id}/shares` | List active shares |
| DELETE | `/api/packets/{id}/shares/{share_id}` | Revoke share |

### Export/Import

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/packets/{id}/export` | Export packet to file |
| POST | `/api/packets/import` | Import packet from file |

### Versioning

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/{id}/versions` | List versions |
| POST | `/api/packets/{id}/versions` | Create version snapshot |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/count` | Badge endpoint |
| GET | `/api/packets/health` | Health check |

## Data Models

### Packet
```python
@dataclass
class Packet:
    id: str
    name: str                    # Packet name
    description: str             # Description
    status: PacketStatus         # draft, finalized, shared, archived
    visibility: PacketVisibility # private, team, public
    created_by: str              # Creator user ID
    created_at: datetime
    updated_at: datetime
    version: int                 # Current version number
    contents_count: int          # Number of items
    size_bytes: int              # Total size
    checksum: str                # Content hash
    metadata: Dict[str, Any]
```

### PacketContent
```python
@dataclass
class PacketContent:
    id: str
    packet_id: str
    content_type: ContentType    # document, entity, etc.
    content_id: str              # ID of referenced item
    content_title: str           # Display title
    added_at: datetime
    added_by: str                # User who added
    order: int                   # Display order
```

### PacketShare
```python
@dataclass
class PacketShare:
    id: str
    packet_id: str
    shared_with: str             # User ID or "public"
    permissions: str             # view, comment, edit
    shared_at: datetime
    expires_at: Optional[datetime]
    access_token: str            # Shareable token
```

### PacketVersion
```python
@dataclass
class PacketVersion:
    id: str
    packet_id: str
    version_number: int
    created_at: datetime
    changes_summary: str
    snapshot_path: str           # Path to version snapshot
```

## Database Schema

The shard uses database schema `arkham_packets`:

```sql
CREATE SCHEMA IF NOT EXISTS arkham_packets;

-- Main packets table
CREATE TABLE arkham_packets.packets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    visibility VARCHAR(50) DEFAULT 'private',
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    contents_count INTEGER DEFAULT 0,
    size_bytes BIGINT DEFAULT 0,
    checksum VARCHAR(64),
    metadata JSONB DEFAULT '{}'
);

-- Packet contents
CREATE TABLE arkham_packets.packet_contents (
    id UUID PRIMARY KEY,
    packet_id UUID REFERENCES arkham_packets.packets(id),
    content_type VARCHAR(50),
    content_id UUID,
    content_title TEXT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_by VARCHAR(100),
    order_num INTEGER DEFAULT 0
);

-- Packet shares
CREATE TABLE arkham_packets.packet_shares (
    id UUID PRIMARY KEY,
    packet_id UUID REFERENCES arkham_packets.packets(id),
    shared_with VARCHAR(100),
    permissions VARCHAR(50) DEFAULT 'view',
    shared_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    access_token VARCHAR(100) UNIQUE
);

-- Packet versions
CREATE TABLE arkham_packets.packet_versions (
    id UUID PRIMARY KEY,
    packet_id UUID REFERENCES arkham_packets.packets(id),
    version_number INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    changes_summary TEXT,
    snapshot_path TEXT
);

-- Indexes
CREATE INDEX idx_packets_status ON arkham_packets.packets(status);
CREATE INDEX idx_packets_creator ON arkham_packets.packets(created_by);
CREATE INDEX idx_contents_packet ON arkham_packets.packet_contents(packet_id);
CREATE INDEX idx_shares_packet ON arkham_packets.packet_shares(packet_id);
CREATE INDEX idx_shares_token ON arkham_packets.packet_shares(access_token);
CREATE INDEX idx_versions_packet ON arkham_packets.packet_versions(packet_id);
```

## Installation

```bash
cd packages/arkham-shard-packets
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Investigative Journalism
- Bundle sources, claims, and evidence for a story
- Share with editors for review
- Export for publication archive
- Maintain version history through story evolution

### Legal Discovery
- Create case packets with exhibits and evidence
- Share with legal team with access controls
- Export for court submission
- Track document chains and provenance

### Academic Research
- Package research materials and findings
- Share with collaborators
- Archive for reproducibility
- Export for publication supplements

### Intelligence Analysis
- Bundle related intelligence materials
- Controlled sharing with analysts
- Export for reporting
- Version tracking through investigation

## Integration with Other Shards

### Claims Shard
- Include claims with full evidence chains
- Package verification workflows

### Provenance Shard
- Track packet lineage and modifications
- Maintain audit trails for legal use

### Timeline Shard
- Include temporal visualizations
- Export timeline snapshots

### Graph Shard
- Package entity relationship graphs
- Include network visualizations

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
packets:
  max_packet_size_mb: 100         # Maximum packet size
  auto_version: true              # Auto-create versions on finalize
  default_share_expiry_days: 30   # Default share expiration
  export_format: zip              # Default export format
```

## License

Part of the SHATTERED architecture, licensed under MIT.
