# Projects Shard

**Version:** 0.1.0
**Category:** System
**Frame Requirement:** >=0.1.0

Project workspace management shard for ArkhamFrame. Organizes documents, entities, and analyses into collaborative workspaces with role-based access control.

## Overview

The Projects shard provides workspace management capabilities:

1. **Project Management** - Create and configure project workspaces
2. **Document Grouping** - Associate documents with projects
3. **Permission Control** - Role-based access to project resources
4. **Activity Tracking** - Monitor project changes and member activity
5. **Project Templates** - Quick-start projects with predefined structure

## Key Features

### Project Workspaces
- Create projects with metadata (name, description, status)
- Project lifecycle management (active, archived, completed, on_hold)
- Project settings and custom metadata
- Project templates for common workflows

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

### Document Association
- Link documents to projects
- Track when documents were added
- Track who added documents
- Remove documents from projects

### Member Management
- Add/remove project members
- Assign roles to members
- Track member activity
- Change member roles

### Activity Tracking
- Comprehensive activity log
- Track all project changes
- Filter by action type
- Filter by member

## Dependencies

### Required Frame Services
- **database** - Stores projects, members, and associations
- **events** - Publishes project lifecycle events

### Optional Frame Services
- **storage** - Project-specific file storage and attachments

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

## API Endpoints

### Projects CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/` | List projects with pagination |
| GET | `/api/projects/{id}` | Get project details |
| POST | `/api/projects/` | Create new project |
| PUT | `/api/projects/{id}` | Update project |
| DELETE | `/api/projects/{id}` | Delete project |

### Project Lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects/{id}/archive` | Archive project |
| POST | `/api/projects/{id}/restore` | Restore archived project |

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
| POST | `/api/projects/{id}/members` | Add member to project |
| DELETE | `/api/projects/{id}/members/{user_id}` | Remove member |
| PATCH | `/api/projects/{id}/members/{user_id}` | Update member role |

### Activity & Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/activity` | Get project activity log |
| GET | `/api/projects/count` | Badge endpoint |
| GET | `/api/projects/stats` | Project statistics |

### Filtered Lists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/active` | List active projects |
| GET | `/api/projects/archived` | List archived projects |
| GET | `/api/projects/by-owner/{user_id}` | Projects by owner |

## Data Models

### Project
```python
@dataclass
class Project:
    id: str
    name: str
    description: str
    status: ProjectStatus             # active, archived, completed, on_hold
    owner_id: str
    created_at: datetime
    updated_at: datetime
    settings: Dict[str, Any]          # Project-specific settings
    metadata: Dict[str, Any]          # Custom metadata
```

### ProjectMember
```python
@dataclass
class ProjectMember:
    id: str
    project_id: str
    user_id: str
    role: ProjectRole                 # owner, admin, editor, viewer
    added_at: datetime
    added_by: str
```

### ProjectDocument
```python
@dataclass
class ProjectDocument:
    id: str
    project_id: str
    document_id: str
    added_at: datetime
    added_by: str
```

### ProjectActivity
```python
@dataclass
class ProjectActivity:
    id: str
    project_id: str
    action: str                       # created, updated, member_added, etc.
    actor_id: str
    target_type: str                  # project, member, document
    target_id: str
    timestamp: datetime
    details: Dict[str, Any]
```

## Database Schema

The shard uses PostgreSQL schema `arkham_projects`:

```sql
CREATE SCHEMA IF NOT EXISTS arkham_projects;

-- Main projects table
CREATE TABLE arkham_projects.projects (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    owner_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Project members
CREATE TABLE arkham_projects.members (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES arkham_projects.projects(id),
    user_id VARCHAR(100) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_by VARCHAR(100),
    UNIQUE(project_id, user_id)
);

-- Project documents
CREATE TABLE arkham_projects.documents (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES arkham_projects.projects(id),
    document_id UUID NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    added_by VARCHAR(100),
    UNIQUE(project_id, document_id)
);

-- Project activity log
CREATE TABLE arkham_projects.activity (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES arkham_projects.projects(id),
    action VARCHAR(100) NOT NULL,
    actor_id VARCHAR(100),
    target_type VARCHAR(50),
    target_id VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    details JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_projects_status ON arkham_projects.projects(status);
CREATE INDEX idx_projects_owner ON arkham_projects.projects(owner_id);
CREATE INDEX idx_members_project ON arkham_projects.members(project_id);
CREATE INDEX idx_members_user ON arkham_projects.members(user_id);
CREATE INDEX idx_documents_project ON arkham_projects.documents(project_id);
CREATE INDEX idx_activity_project ON arkham_projects.activity(project_id);
```

## Installation

```bash
cd packages/arkham-shard-projects
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Investigative Journalism
- Organize documents by investigation
- Track team member roles and contributions
- Archive completed investigations
- Monitor investigation progress

### Legal Research
- Group case-related documents
- Manage research team access
- Track document associations
- Archive closed cases

### Academic Research
- Organize research projects
- Collaborate with research team
- Track project milestones
- Manage project resources

## Integration with Other Shards

### Document Shards (Ingest, Parse, etc.)
- Auto-associate new documents with active project
- Track document processing in project context

### Entity Shards
- Link entities to project context
- Track entity relationships within projects

### Analysis Shards (ACH, Claims, etc.)
- Associate analyses with projects
- Track analytical work by project

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
projects:
  auto_associate_documents: true      # Auto-link documents to active project
  max_members_per_project: 100        # Member limit
  enable_activity_log: true           # Track all project activity
  default_member_role: viewer         # Default role for new members
```

## License

Part of the SHATTERED architecture, licensed under MIT.
