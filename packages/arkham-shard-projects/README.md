# arkham-shard-projects

> Project workspace management with vector collection isolation

**Version:** 0.1.0
**Category:** System
**Frame Requirement:** >=0.1.0

## Overview

The Projects shard provides workspace management capabilities for SHATTERED, allowing users to organize documents, entities, and analyses into isolated workspaces. Each project can have its own vector collections with configurable embedding models, enabling project-scoped semantic search.

### Key Capabilities

1. **Project Management** - Create and configure project workspaces
2. **Vector Collection Isolation** - Project-scoped Qdrant collections with configurable embedding models
3. **Document Grouping** - Associate documents with projects
4. **Permission Control** - Role-based access to project resources
5. **Activity Tracking** - Monitor project changes and member activity

## Features

### Project Workspaces
- Create projects with metadata (name, description, status)
- Project lifecycle management (active, archived, completed, on_hold)
- Project settings and custom metadata
- Member and document counts tracked automatically

### Vector Collection Isolation
- **Project-scoped collections**: Each project gets isolated vector collections
  - `project_{id}_documents` - Document embeddings
  - `project_{id}_chunks` - Chunk embeddings
  - `project_{id}_entities` - Entity embeddings
- **Configurable embedding models** per project
- **Automatic collection creation** on project creation
- **Safe model switching** with dimension validation

### Supported Embedding Models

| Model | Dimensions | Description |
|-------|------------|-------------|
| `all-MiniLM-L6-v2` | 384 | Default, fast general-purpose |
| `all-mpnet-base-v2` | 768 | Higher quality, slower |
| `BAAI/bge-m3` | 1024 | Multilingual, highest quality |
| `paraphrase-MiniLM-L6-v2` | 384 | Optimized for paraphrase detection |

### Project Roles
- **Owner** - Full control over project
- **Admin** - Manage members and settings
- **Editor** - Add/edit content
- **Viewer** - Read-only access

### Project Status
- **Active** - Currently in progress
- **Archived** - Completed or inactive
- **Completed** - Successfully finished
- **On Hold** - Temporarily paused

## Installation

```bash
pip install -e packages/arkham-shard-projects
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/health` | Health check |
| GET | `/api/projects/count` | Project count (badge) |

### Projects CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/` | List projects with filtering |
| POST | `/api/projects/` | Create project (with optional collections) |
| GET | `/api/projects/{id}` | Get project details |
| PUT | `/api/projects/{id}` | Update project |
| DELETE | `/api/projects/{id}` | Delete project |

### Project Lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects/{id}/archive` | Archive project |
| POST | `/api/projects/{id}/restore` | Restore archived project |

### Embedding Model Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/embedding-models` | List available models |
| GET | `/api/projects/{id}/embedding-model` | Get project model config |
| PUT | `/api/projects/{id}/embedding-model` | Update embedding model |

### Vector Collections

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/collections` | Get collection statistics |
| POST | `/api/projects/{id}/collections/create` | Create collections |
| DELETE | `/api/projects/{id}/collections` | Delete all collections |

### Document Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/documents` | Get project documents |
| POST | `/api/projects/{id}/documents` | Add document to project |
| DELETE | `/api/projects/{id}/documents/{doc_id}` | Remove document |

### Member Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/members` | Get project members |
| POST | `/api/projects/{id}/members` | Add member |
| DELETE | `/api/projects/{id}/members/{user_id}` | Remove member |

### Activity

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/activity` | Get activity log |

## API Examples

### Create Project with Vector Collections

```json
POST /api/projects/
{
  "name": "Investigation Alpha",
  "description": "Document analysis project",
  "embedding_model": "all-MiniLM-L6-v2",
  "create_collections": true
}
```

### Update Project Embedding Model

```json
PUT /api/projects/{id}/embedding-model
{
  "model": "all-mpnet-base-v2",
  "wipe_collections": true
}
```

Note: If the new model has different dimensions, `wipe_collections: true` is required.

### Get Collection Statistics Response

```json
{
  "available": true,
  "collections": {
    "project_abc123_documents": {"vectors_count": 150, "status": "green"},
    "project_abc123_chunks": {"vectors_count": 3200, "status": "green"},
    "project_abc123_entities": {"vectors_count": 89, "status": "green"}
  }
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `projects.project.created` | New project created |
| `projects.project.updated` | Project metadata updated |
| `projects.project.deleted` | Project deleted |
| `projects.project.archived` | Project archived |
| `projects.project.restored` | Project restored from archive |
| `projects.member.added` | Member added to project |
| `projects.member.removed` | Member removed from project |
| `projects.member.role_changed` | Member role updated |
| `projects.document.added` | Document associated with project |
| `projects.document.removed` | Document removed from project |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.created` | Auto-associate with active project context |
| `entity.created` | Track entities created in project context |

## UI Routes

| Route | Description |
|-------|-------------|
| `/projects` | All projects list |
| `/projects/active` | Active projects |
| `/projects/archived` | Archived projects |

## Dependencies

### Required Services
- **database** - Stores projects, members, associations
- **events** - Publishes project lifecycle events

### Optional Services
- **storage** - Project-specific file storage
- **vectors** - For project-scoped collections (Qdrant)

## URL State

| Parameter | Description |
|-----------|-------------|
| `projectId` | Selected project |
| `view` | Display mode (grid, list, kanban) |
| `filter` | Status filter |

## Development

```bash
# Run tests
pytest packages/arkham-shard-projects/tests/

# Type checking
mypy packages/arkham-shard-projects/
```

## License

MIT
