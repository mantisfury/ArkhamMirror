# arkham-shard-packets

> Investigation packet creation and sharing for bundled analyses

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

## Overview

The Packets shard manages investigation packets - bundles of documents, entities, and analyses that can be archived and shared. It supports packet creation, content management, sharing with access control, versioning, and import/export capabilities.

### Key Capabilities

1. **Packet Creation** - Create investigation packets
2. **Packet Sharing** - Share with access control
3. **Packet Import** - Import packets from files
4. **Packet Versioning** - Version control for packets
5. **Access Control** - Manage packet permissions

## Features

### Packet Status
- `draft` - Work in progress
- `finalized` - Completed and locked
- `archived` - Archived for storage

### Content Types
Packets can contain:
- Documents
- Entities
- Claims
- Timeline events
- ACH matrices
- Contradictions
- Anomalies
- Custom notes

### Sharing
- Share with specific users
- Generate share links
- Access level control (view, comment, edit)
- Expiration dates

### Versioning
- Create version snapshots
- Track changes over time
- Restore previous versions

## Installation

```bash
pip install -e packages/arkham-shard-packets
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/health` | Health check |
| GET | `/api/packets/count` | Packet count (badge) |

### Packet CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/` | List packets |
| POST | `/api/packets/` | Create packet |
| GET | `/api/packets/{id}` | Get packet |
| PUT | `/api/packets/{id}` | Update packet |
| DELETE | `/api/packets/{id}` | Delete packet |
| POST | `/api/packets/{id}/finalize` | Finalize packet |
| POST | `/api/packets/{id}/archive` | Archive packet |

### Contents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/{id}/contents` | List contents |
| POST | `/api/packets/{id}/contents` | Add content |
| DELETE | `/api/packets/{id}/contents/{cid}` | Remove content |

### Sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/packets/{id}/share` | Share packet |
| GET | `/api/packets/{id}/shares` | List shares |
| DELETE | `/api/packets/{id}/shares/{sid}` | Revoke share |

### Import/Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/packets/{id}/export` | Export packet |
| POST | `/api/packets/import` | Import packet |

### Versions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/{id}/versions` | List versions |
| POST | `/api/packets/{id}/versions` | Create version |

### Status Filtered

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/status/draft` | Draft packets |
| GET | `/api/packets/status/finalized` | Finalized packets |
| GET | `/api/packets/status/shared` | Shared packets |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packets/stats/overview` | Statistics |

## API Examples

### Create Packet

```json
POST /api/packets/
{
  "name": "Investigation Case #123",
  "description": "Complete investigation packet for Case #123",
  "project_id": "proj_abc",
  "tags": ["urgent", "fraud"]
}
```

### Add Content to Packet

```json
POST /api/packets/{packet_id}/contents
{
  "content_type": "document",
  "content_id": "doc_abc123",
  "notes": "Primary evidence document"
}
```

### Share Packet

```json
POST /api/packets/{packet_id}/share
{
  "share_type": "user",
  "target_id": "user_xyz",
  "access_level": "view",
  "expires_at": "2025-01-31T23:59:59Z",
  "message": "Please review this investigation packet"
}
```

Response:
```json
{
  "id": "share_abc123",
  "packet_id": "pkt_xyz",
  "share_type": "user",
  "target_id": "user_xyz",
  "access_level": "view",
  "share_url": "https://app.example.com/packets/share/abc123",
  "created_at": "2024-12-15T10:30:00Z",
  "expires_at": "2025-01-31T23:59:59Z"
}
```

### Finalize Packet

```bash
POST /api/packets/{packet_id}/finalize
```

Locks the packet and prevents further modifications.

### Export Packet

```json
POST /api/packets/{packet_id}/export
{
  "format": "zip",
  "include_documents": true,
  "include_metadata": true
}
```

### Import Packet

```json
POST /api/packets/import
{
  "file_path": "/imports/packet_backup.zip",
  "project_id": "proj_new",
  "merge_mode": "create_new"
}
```

### Create Version Snapshot

```json
POST /api/packets/{packet_id}/versions
{
  "description": "Version after adding timeline analysis",
  "tags": ["milestone"]
}
```

### Get Statistics

```bash
GET /api/packets/stats/overview
```

Response:
```json
{
  "total_packets": 45,
  "by_status": {
    "draft": 15,
    "finalized": 25,
    "archived": 5
  },
  "total_contents": 350,
  "avg_contents_per_packet": 7.8,
  "shared_packets": 12,
  "versions_created": 89
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `packets.packet.created` | New packet created |
| `packets.packet.updated` | Packet metadata updated |
| `packets.packet.finalized` | Packet finalized |
| `packets.packet.shared` | Packet shared |
| `packets.packet.exported` | Packet exported |
| `packets.packet.imported` | Packet imported |
| `packets.content.added` | Content added |
| `packets.content.removed` | Content removed |
| `packets.version.created` | Version snapshot created |

### Subscribed Events

No subscribed events - API-triggered.

## UI Routes

| Route | Description |
|-------|-------------|
| `/packets` | All packets |
| `/packets/draft` | Draft packets |
| `/packets/finalized` | Finalized packets |
| `/packets/shared` | Shared packets |

## Dependencies

### Required Services
- **database** - Packet and content storage
- **events** - Event publishing

### Optional Services
- **storage** - File storage for exports

## URL State

| Parameter | Description |
|-----------|-------------|
| `packetId` | Selected packet |
| `view` | Display mode |
| `filter` | Status/visibility filter |

### Local Storage Keys
- `show_contents` - Expand content list
- `sort_order` - Packet list sort preference
- `view_mode` - Grid/list view toggle

## Development

```bash
# Run tests
pytest packages/arkham-shard-packets/tests/

# Type checking
mypy packages/arkham-shard-packets/
```

## License

MIT
