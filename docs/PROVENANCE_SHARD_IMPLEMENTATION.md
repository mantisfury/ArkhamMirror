# Provenance Shard Implementation Tasks

**Priority:** HIGHEST — This is the most upstream shard. Everything else depends on lineage tracking.

**Reference Implementation:** Use `arkham-shard-ach` as your gold standard for patterns.

**File Locations:**
- Backend: `packages/arkham-shard-provenance/arkham_shard_provenance/`
- Frontend: `packages/arkham-shard-shell/src/pages/provenance/`
- Manifest: `packages/arkham-shard-provenance/shard.yaml`

---

## Current State

**What Exists:**
- 3 tables: `arkham_provenance_records`, `arkham_provenance_transformations`, `arkham_provenance_audit`
- Basic shard structure with stubs
- Frontend page with placeholder UI

**What's Broken:**
- 4 core tables missing (chains, links, artifacts, lineage)
- All chain/link methods return hardcoded stubs
- API endpoints raise 501 or return empty
- Event handlers subscribed but do nothing

---

## Task 1: Database Schema

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

**Location:** Find `_create_schema()` method (or `initialize()` if schema is inline)

**Add these tables:**

```sql
-- Chains: Groups of linked provenance records
CREATE TABLE IF NOT EXISTS arkham_provenance_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID,
    title TEXT NOT NULL,
    description TEXT,
    chain_type VARCHAR(50) DEFAULT 'evidence',  -- evidence, document, entity, claim
    status VARCHAR(50) DEFAULT 'active',        -- active, verified, disputed, archived
    root_artifact_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_provenance_chains_project 
    ON arkham_provenance_chains(project_id);
CREATE INDEX IF NOT EXISTS idx_provenance_chains_status 
    ON arkham_provenance_chains(status);
CREATE INDEX IF NOT EXISTS idx_provenance_chains_type 
    ON arkham_provenance_chains(chain_type);

-- Links: Connections between artifacts in a chain
CREATE TABLE IF NOT EXISTS arkham_provenance_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id UUID NOT NULL REFERENCES arkham_provenance_chains(id) ON DELETE CASCADE,
    source_artifact_id UUID NOT NULL,
    target_artifact_id UUID NOT NULL,
    link_type VARCHAR(50) NOT NULL,  -- derived_from, extracted_from, references, contradicts, supports
    confidence FLOAT DEFAULT 1.0,
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_provenance_links_chain 
    ON arkham_provenance_links(chain_id);
CREATE INDEX IF NOT EXISTS idx_provenance_links_source 
    ON arkham_provenance_links(source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_provenance_links_target 
    ON arkham_provenance_links(target_artifact_id);

-- Artifacts: Any tracked item (documents, entities, claims, etc.)
CREATE TABLE IF NOT EXISTS arkham_provenance_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type VARCHAR(50) NOT NULL,  -- document, entity, claim, chunk, extraction
    entity_id UUID NOT NULL,             -- ID in the source table
    entity_table VARCHAR(100) NOT NULL,  -- e.g., arkham_documents, arkham_entities
    title TEXT,
    hash VARCHAR(64),                    -- SHA-256 of content for integrity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_provenance_artifacts_type 
    ON arkham_provenance_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_provenance_artifacts_entity 
    ON arkham_provenance_artifacts(entity_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_provenance_artifacts_unique_entity 
    ON arkham_provenance_artifacts(entity_id, entity_table);

-- Lineage cache: Pre-computed paths for fast traversal
CREATE TABLE IF NOT EXISTS arkham_provenance_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES arkham_provenance_artifacts(id) ON DELETE CASCADE,
    ancestor_id UUID NOT NULL REFERENCES arkham_provenance_artifacts(id) ON DELETE CASCADE,
    depth INTEGER NOT NULL,
    path UUID[] NOT NULL,  -- Array of artifact IDs from ancestor to artifact
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provenance_lineage_artifact 
    ON arkham_provenance_lineage(artifact_id);
CREATE INDEX IF NOT EXISTS idx_provenance_lineage_ancestor 
    ON arkham_provenance_lineage(ancestor_id);
```

**Acceptance Criteria:**
- [ ] All 4 tables created on shard initialization
- [ ] Indexes created for query performance
- [ ] No errors on startup
- [ ] Tables visible via `\dt arkham_provenance*` in psql

---

## Task 2: Artifact CRUD

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

**Replace stub methods with real implementations:**

### 2.1 Create Artifact

```python
async def create_artifact(
    self,
    artifact_type: str,
    entity_id: str,
    entity_table: str,
    title: str = None,
    content_hash: str = None,
    metadata: dict = None
) -> dict:
    """Register an artifact for provenance tracking."""
    query = """
        INSERT INTO arkham_provenance_artifacts 
            (artifact_type, entity_id, entity_table, title, hash, metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (entity_id, entity_table) DO UPDATE SET
            title = COALESCE(EXCLUDED.title, arkham_provenance_artifacts.title),
            hash = COALESCE(EXCLUDED.hash, arkham_provenance_artifacts.hash),
            metadata = arkham_provenance_artifacts.metadata || EXCLUDED.metadata
        RETURNING id, artifact_type, entity_id, entity_table, title, hash, created_at, metadata
    """
    row = await self.db.fetchrow(
        query,
        artifact_type,
        entity_id,
        entity_table,
        title,
        content_hash,
        json.dumps(metadata or {})
    )
    
    artifact = dict(row)
    
    # Emit event
    await self.events.emit(
        "provenance.artifact.created",
        {"id": str(artifact["id"]), "type": artifact_type, "entity_id": entity_id},
        source="provenance-shard"
    )
    
    return artifact
```

### 2.2 Get Artifact

```python
async def get_artifact(self, artifact_id: str) -> dict | None:
    """Get artifact by ID."""
    query = """
        SELECT id, artifact_type, entity_id, entity_table, title, hash, created_at, metadata
        FROM arkham_provenance_artifacts
        WHERE id = $1
    """
    row = await self.db.fetchrow(query, artifact_id)
    return dict(row) if row else None

async def get_artifact_by_entity(self, entity_id: str, entity_table: str) -> dict | None:
    """Get artifact by the entity it tracks."""
    query = """
        SELECT id, artifact_type, entity_id, entity_table, title, hash, created_at, metadata
        FROM arkham_provenance_artifacts
        WHERE entity_id = $1 AND entity_table = $2
    """
    row = await self.db.fetchrow(query, entity_id, entity_table)
    return dict(row) if row else None
```

### 2.3 List Artifacts

```python
async def list_artifacts(
    self,
    artifact_type: str = None,
    limit: int = 50,
    offset: int = 0
) -> list[dict]:
    """List artifacts with optional type filter."""
    if artifact_type:
        query = """
            SELECT id, artifact_type, entity_id, entity_table, title, hash, created_at, metadata
            FROM arkham_provenance_artifacts
            WHERE artifact_type = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        rows = await self.db.fetch(query, artifact_type, limit, offset)
    else:
        query = """
            SELECT id, artifact_type, entity_id, entity_table, title, hash, created_at, metadata
            FROM arkham_provenance_artifacts
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        rows = await self.db.fetch(query, limit, offset)
    
    return [dict(row) for row in rows]
```

**Acceptance Criteria:**
- [ ] `create_artifact()` inserts and returns full artifact dict
- [ ] `create_artifact()` handles upsert (same entity_id + entity_table)
- [ ] `get_artifact()` returns artifact or None
- [ ] `get_artifact_by_entity()` finds by source entity
- [ ] `list_artifacts()` supports filtering and pagination
- [ ] Events emitted on create

---

## Task 3: Chain CRUD

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

### 3.1 Create Chain

```python
async def create_chain(
    self,
    title: str,
    description: str = None,
    chain_type: str = "evidence",
    project_id: str = None,
    root_artifact_id: str = None,
    metadata: dict = None
) -> dict:
    """Create a new provenance chain."""
    query = """
        INSERT INTO arkham_provenance_chains 
            (title, description, chain_type, project_id, root_artifact_id, metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, title, description, chain_type, status, project_id, 
                  root_artifact_id, created_at, updated_at, metadata
    """
    row = await self.db.fetchrow(
        query,
        title,
        description,
        chain_type,
        project_id,
        root_artifact_id,
        json.dumps(metadata or {})
    )
    
    chain = dict(row)
    
    await self.events.emit(
        "provenance.chain.created",
        {"id": str(chain["id"]), "title": title, "type": chain_type},
        source="provenance-shard"
    )
    
    return chain
```

### 3.2 Get Chain

```python
async def get_chain(self, chain_id: str) -> dict | None:
    """Get chain with link count."""
    query = """
        SELECT c.*, 
               COUNT(l.id) as link_count
        FROM arkham_provenance_chains c
        LEFT JOIN arkham_provenance_links l ON l.chain_id = c.id
        WHERE c.id = $1
        GROUP BY c.id
    """
    row = await self.db.fetchrow(query, chain_id)
    return dict(row) if row else None
```

### 3.3 List Chains

```python
async def list_chains(
    self,
    project_id: str = None,
    chain_type: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0
) -> list[dict]:
    """List chains with filters."""
    conditions = []
    params = []
    param_idx = 1
    
    if project_id:
        conditions.append(f"project_id = ${param_idx}")
        params.append(project_id)
        param_idx += 1
    
    if chain_type:
        conditions.append(f"chain_type = ${param_idx}")
        params.append(chain_type)
        param_idx += 1
    
    if status:
        conditions.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
        SELECT c.*, COUNT(l.id) as link_count
        FROM arkham_provenance_chains c
        LEFT JOIN arkham_provenance_links l ON l.chain_id = c.id
        {where_clause}
        GROUP BY c.id
        ORDER BY c.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])
    
    rows = await self.db.fetch(query, *params)
    return [dict(row) for row in rows]
```

### 3.4 Update Chain

```python
async def update_chain(
    self,
    chain_id: str,
    title: str = None,
    description: str = None,
    status: str = None,
    metadata: dict = None
) -> dict | None:
    """Update chain properties."""
    updates = ["updated_at = NOW()"]
    params = []
    param_idx = 1
    
    if title is not None:
        updates.append(f"title = ${param_idx}")
        params.append(title)
        param_idx += 1
    
    if description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(description)
        param_idx += 1
    
    if status is not None:
        updates.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    
    if metadata is not None:
        updates.append(f"metadata = metadata || ${param_idx}::jsonb")
        params.append(json.dumps(metadata))
        param_idx += 1
    
    params.append(chain_id)
    
    query = f"""
        UPDATE arkham_provenance_chains
        SET {', '.join(updates)}
        WHERE id = ${param_idx}
        RETURNING *
    """
    
    row = await self.db.fetchrow(query, *params)
    
    if row:
        await self.events.emit(
            "provenance.chain.updated",
            {"id": chain_id, "status": status},
            source="provenance-shard"
        )
    
    return dict(row) if row else None
```

### 3.5 Verify Chain

```python
async def verify_chain(self, chain_id: str, verified_by: str = None) -> dict:
    """Verify all links in a chain and update status."""
    # Get all links
    links = await self.db.fetch(
        "SELECT * FROM arkham_provenance_links WHERE chain_id = $1",
        chain_id
    )
    
    issues = []
    
    for link in links:
        # Check source artifact exists
        source = await self.get_artifact(str(link["source_artifact_id"]))
        if not source:
            issues.append({
                "link_id": str(link["id"]),
                "issue": "source_artifact_missing",
                "artifact_id": str(link["source_artifact_id"])
            })
        
        # Check target artifact exists
        target = await self.get_artifact(str(link["target_artifact_id"]))
        if not target:
            issues.append({
                "link_id": str(link["id"]),
                "issue": "target_artifact_missing", 
                "artifact_id": str(link["target_artifact_id"])
            })
    
    verified = len(issues) == 0
    new_status = "verified" if verified else "disputed"
    
    # Update chain status
    await self.update_chain(chain_id, status=new_status)
    
    # Mark all links as verified if no issues
    if verified:
        await self.db.execute(
            """
            UPDATE arkham_provenance_links 
            SET verified = TRUE, verified_by = $1, verified_at = NOW()
            WHERE chain_id = $2
            """,
            verified_by,
            chain_id
        )
    
    await self.events.emit(
        "provenance.chain.verified",
        {"id": chain_id, "verified": verified, "issue_count": len(issues)},
        source="provenance-shard"
    )
    
    return {
        "chain_id": chain_id,
        "verified": verified,
        "status": new_status,
        "issues": issues,
        "link_count": len(links)
    }
```

**Acceptance Criteria:**
- [ ] `create_chain()` creates and returns chain
- [ ] `get_chain()` returns chain with link count
- [ ] `list_chains()` supports project, type, status filters
- [ ] `update_chain()` handles partial updates
- [ ] `verify_chain()` checks artifact integrity
- [ ] Events emitted on create, update, verify

---

## Task 4: Link CRUD

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

### 4.1 Add Link

```python
async def add_link(
    self,
    chain_id: str,
    source_artifact_id: str,
    target_artifact_id: str,
    link_type: str,
    confidence: float = 1.0,
    metadata: dict = None
) -> dict:
    """Add a link between artifacts in a chain."""
    # Validate artifacts exist
    source = await self.get_artifact(source_artifact_id)
    target = await self.get_artifact(target_artifact_id)
    
    if not source:
        raise ValueError(f"Source artifact {source_artifact_id} not found")
    if not target:
        raise ValueError(f"Target artifact {target_artifact_id} not found")
    
    query = """
        INSERT INTO arkham_provenance_links
            (chain_id, source_artifact_id, target_artifact_id, link_type, confidence, metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
    """
    row = await self.db.fetchrow(
        query,
        chain_id,
        source_artifact_id,
        target_artifact_id,
        link_type,
        confidence,
        json.dumps(metadata or {})
    )
    
    link = dict(row)
    
    # Update lineage cache
    await self._update_lineage_cache(target_artifact_id)
    
    await self.events.emit(
        "provenance.link.created",
        {
            "id": str(link["id"]),
            "chain_id": chain_id,
            "source": source_artifact_id,
            "target": target_artifact_id,
            "type": link_type
        },
        source="provenance-shard"
    )
    
    return link
```

### 4.2 Get Links

```python
async def get_chain_links(self, chain_id: str) -> list[dict]:
    """Get all links in a chain with artifact details."""
    query = """
        SELECT 
            l.*,
            sa.title as source_title,
            sa.artifact_type as source_type,
            ta.title as target_title,
            ta.artifact_type as target_type
        FROM arkham_provenance_links l
        JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
        JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
        WHERE l.chain_id = $1
        ORDER BY l.created_at
    """
    rows = await self.db.fetch(query, chain_id)
    return [dict(row) for row in rows]
```

### 4.3 Remove Link

```python
async def remove_link(self, link_id: str) -> bool:
    """Remove a link from a chain."""
    # Get link details for event
    link = await self.db.fetchrow(
        "SELECT * FROM arkham_provenance_links WHERE id = $1",
        link_id
    )
    
    if not link:
        return False
    
    await self.db.execute(
        "DELETE FROM arkham_provenance_links WHERE id = $1",
        link_id
    )
    
    # Update lineage cache for affected artifact
    await self._update_lineage_cache(str(link["target_artifact_id"]))
    
    await self.events.emit(
        "provenance.link.deleted",
        {"id": link_id, "chain_id": str(link["chain_id"])},
        source="provenance-shard"
    )
    
    return True
```

**Acceptance Criteria:**
- [ ] `add_link()` validates artifacts exist before linking
- [ ] `add_link()` updates lineage cache
- [ ] `get_chain_links()` returns links with artifact details
- [ ] `remove_link()` cleans up and emits event

---

## Task 5: Lineage Traversal

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

### 5.1 Update Lineage Cache

```python
async def _update_lineage_cache(self, artifact_id: str) -> None:
    """Rebuild lineage cache for an artifact using BFS."""
    # Clear existing lineage for this artifact
    await self.db.execute(
        "DELETE FROM arkham_provenance_lineage WHERE artifact_id = $1",
        artifact_id
    )
    
    # BFS to find all ancestors
    visited = set()
    queue = [(artifact_id, 0, [artifact_id])]  # (current_id, depth, path)
    lineage_rows = []
    
    while queue:
        current_id, depth, path = queue.pop(0)
        
        if current_id in visited:
            continue
        visited.add(current_id)
        
        # Find all sources (artifacts that link TO this one)
        sources = await self.db.fetch(
            """
            SELECT DISTINCT source_artifact_id 
            FROM arkham_provenance_links 
            WHERE target_artifact_id = $1
            """,
            current_id
        )
        
        for row in sources:
            source_id = str(row["source_artifact_id"])
            new_path = [source_id] + path
            
            # Store lineage record
            lineage_rows.append({
                "artifact_id": artifact_id,
                "ancestor_id": source_id,
                "depth": depth + 1,
                "path": new_path
            })
            
            queue.append((source_id, depth + 1, new_path))
    
    # Batch insert lineage
    if lineage_rows:
        await self.db.executemany(
            """
            INSERT INTO arkham_provenance_lineage (artifact_id, ancestor_id, depth, path)
            VALUES ($1, $2, $3, $4)
            """,
            [(r["artifact_id"], r["ancestor_id"], r["depth"], r["path"]) for r in lineage_rows]
        )
```

### 5.2 Get Lineage

```python
async def get_lineage(self, artifact_id: str) -> dict:
    """Get full lineage graph for an artifact."""
    # Get the artifact
    artifact = await self.get_artifact(artifact_id)
    if not artifact:
        return {"nodes": [], "edges": [], "root": None}
    
    # Get all ancestors from cache
    ancestors = await self.db.fetch(
        """
        SELECT l.*, a.title, a.artifact_type, a.entity_id
        FROM arkham_provenance_lineage l
        JOIN arkham_provenance_artifacts a ON a.id = l.ancestor_id
        WHERE l.artifact_id = $1
        ORDER BY l.depth
        """,
        artifact_id
    )
    
    # Get all descendants (artifacts that have this one as ancestor)
    descendants = await self.db.fetch(
        """
        SELECT l.artifact_id, l.depth, a.title, a.artifact_type, a.entity_id
        FROM arkham_provenance_lineage l
        JOIN arkham_provenance_artifacts a ON a.id = l.artifact_id
        WHERE l.ancestor_id = $1
        ORDER BY l.depth
        """,
        artifact_id
    )
    
    # Build nodes
    nodes = [{
        "id": artifact_id,
        "title": artifact.get("title"),
        "type": artifact.get("artifact_type"),
        "is_focus": True
    }]
    
    for row in ancestors:
        nodes.append({
            "id": str(row["ancestor_id"]),
            "title": row["title"],
            "type": row["artifact_type"],
            "depth": -row["depth"]  # Negative for ancestors
        })
    
    for row in descendants:
        nodes.append({
            "id": str(row["artifact_id"]),
            "title": row["title"],
            "type": row["artifact_type"],
            "depth": row["depth"]  # Positive for descendants
        })
    
    # Get edges (links between all these artifacts)
    artifact_ids = [n["id"] for n in nodes]
    edges = await self.db.fetch(
        """
        SELECT id, source_artifact_id, target_artifact_id, link_type, confidence
        FROM arkham_provenance_links
        WHERE source_artifact_id = ANY($1) AND target_artifact_id = ANY($1)
        """,
        artifact_ids
    )
    
    return {
        "nodes": nodes,
        "edges": [dict(e) for e in edges],
        "root": artifact_id,
        "ancestor_count": len(ancestors),
        "descendant_count": len(descendants)
    }
```

**Acceptance Criteria:**
- [ ] `_update_lineage_cache()` performs BFS traversal
- [ ] Lineage cache is updated when links are added/removed
- [ ] `get_lineage()` returns graph structure with nodes and edges
- [ ] Handles circular references gracefully

---

## Task 6: Event Handlers

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/shard.py`

**Location:** Find `initialize()` method and event subscriptions

### 6.1 Subscribe to Events

```python
async def initialize(self, frame) -> None:
    self.frame = frame
    self.db = frame.db
    self.events = frame.events
    
    await self._create_schema()
    
    # Subscribe to events from other shards
    self.events.subscribe("documents.document.created", self._on_document_created)
    self.events.subscribe("documents.document.deleted", self._on_document_deleted)
    self.events.subscribe("entities.entity.created", self._on_entity_created)
    self.events.subscribe("claims.claim.created", self._on_claim_created)
    self.events.subscribe("parse.chunk.created", self._on_chunk_created)
```

### 6.2 Implement Handlers

```python
async def _on_document_created(self, event: dict) -> None:
    """Auto-create artifact when document is created."""
    try:
        doc_id = event.get("data", {}).get("id") or event.get("id")
        title = event.get("data", {}).get("title") or event.get("title", "Untitled")
        
        await self.create_artifact(
            artifact_type="document",
            entity_id=doc_id,
            entity_table="arkham_documents",
            title=title,
            metadata={"source": "auto", "event": "documents.document.created"}
        )
    except Exception as e:
        # Log but don't crash
        print(f"[provenance] Error handling document.created: {e}")

async def _on_document_deleted(self, event: dict) -> None:
    """Handle document deletion - mark artifacts but don't delete (preserve history)."""
    try:
        doc_id = event.get("data", {}).get("id") or event.get("id")
        
        artifact = await self.get_artifact_by_entity(doc_id, "arkham_documents")
        if artifact:
            await self.db.execute(
                """
                UPDATE arkham_provenance_artifacts 
                SET metadata = metadata || '{"deleted": true}'::jsonb
                WHERE id = $1
                """,
                artifact["id"]
            )
    except Exception as e:
        print(f"[provenance] Error handling document.deleted: {e}")

async def _on_entity_created(self, event: dict) -> None:
    """Auto-create artifact when entity is created."""
    try:
        entity_id = event.get("data", {}).get("id") or event.get("id")
        name = event.get("data", {}).get("name") or event.get("name", "Unknown")
        
        # Link to source document if available
        source_doc_id = event.get("data", {}).get("document_id")
        
        artifact = await self.create_artifact(
            artifact_type="entity",
            entity_id=entity_id,
            entity_table="arkham_entities",
            title=name,
            metadata={"source": "auto", "event": "entities.entity.created"}
        )
        
        # Create link to source document
        if source_doc_id:
            doc_artifact = await self.get_artifact_by_entity(source_doc_id, "arkham_documents")
            if doc_artifact:
                # Find or create default chain for this project
                chain = await self._get_or_create_default_chain(event.get("project_id"))
                await self.add_link(
                    chain_id=str(chain["id"]),
                    source_artifact_id=str(doc_artifact["id"]),
                    target_artifact_id=str(artifact["id"]),
                    link_type="extracted_from"
                )
    except Exception as e:
        print(f"[provenance] Error handling entity.created: {e}")

async def _on_claim_created(self, event: dict) -> None:
    """Auto-create artifact when claim is created."""
    try:
        claim_id = event.get("data", {}).get("id") or event.get("id")
        content = event.get("data", {}).get("content") or event.get("content", "")
        
        await self.create_artifact(
            artifact_type="claim",
            entity_id=claim_id,
            entity_table="arkham_claims",
            title=content[:100] if content else "Claim",
            metadata={"source": "auto", "event": "claims.claim.created"}
        )
    except Exception as e:
        print(f"[provenance] Error handling claim.created: {e}")

async def _on_chunk_created(self, event: dict) -> None:
    """Auto-create artifact when chunk is created."""
    try:
        chunk_id = event.get("data", {}).get("id") or event.get("id")
        doc_id = event.get("data", {}).get("document_id")
        
        artifact = await self.create_artifact(
            artifact_type="chunk",
            entity_id=chunk_id,
            entity_table="arkham_chunks",
            title=f"Chunk from {doc_id}",
            metadata={"source": "auto", "document_id": doc_id}
        )
        
        # Link to parent document
        if doc_id:
            doc_artifact = await self.get_artifact_by_entity(doc_id, "arkham_documents")
            if doc_artifact:
                chain = await self._get_or_create_default_chain()
                await self.add_link(
                    chain_id=str(chain["id"]),
                    source_artifact_id=str(doc_artifact["id"]),
                    target_artifact_id=str(artifact["id"]),
                    link_type="derived_from"
                )
    except Exception as e:
        print(f"[provenance] Error handling chunk.created: {e}")

async def _get_or_create_default_chain(self, project_id: str = None) -> dict:
    """Get or create a default auto-tracking chain."""
    chain_title = "Auto-tracked Provenance"
    
    # Check for existing
    existing = await self.db.fetchrow(
        """
        SELECT * FROM arkham_provenance_chains 
        WHERE title = $1 AND (project_id = $2 OR ($2 IS NULL AND project_id IS NULL))
        """,
        chain_title,
        project_id
    )
    
    if existing:
        return dict(existing)
    
    return await self.create_chain(
        title=chain_title,
        description="Automatically tracked provenance links",
        chain_type="auto",
        project_id=project_id
    )
```

**Acceptance Criteria:**
- [ ] Events subscribed in `initialize()`
- [ ] `_on_document_created` creates artifact
- [ ] `_on_entity_created` creates artifact + links to source doc
- [ ] `_on_claim_created` creates artifact
- [ ] `_on_chunk_created` creates artifact + links to parent doc
- [ ] Errors logged but don't crash the system
- [ ] Default chain auto-created for automatic tracking

---

## Task 7: API Endpoints

**File:** `packages/arkham-shard-provenance/arkham_shard_provenance/api.py`

**Replace 501 stubs with real endpoints:**

```python
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from .shard import ProvenanceShard

router = APIRouter()

def get_shard():
    from arkham_frame import get_frame
    frame = get_frame()
    return frame.get_shard("provenance")

# ============ ARTIFACTS ============

@router.post("/artifacts")
async def create_artifact(
    artifact_type: str,
    entity_id: str,
    entity_table: str,
    title: Optional[str] = None,
    shard: ProvenanceShard = Depends(get_shard)
):
    return await shard.create_artifact(artifact_type, entity_id, entity_table, title)

@router.get("/artifacts")
async def list_artifacts(
    artifact_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    shard: ProvenanceShard = Depends(get_shard)
):
    return await shard.list_artifacts(artifact_type, limit, offset)

@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, shard: ProvenanceShard = Depends(get_shard)):
    result = await shard.get_artifact(artifact_id)
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return result

@router.get("/artifacts/{artifact_id}/lineage")
async def get_artifact_lineage(artifact_id: str, shard: ProvenanceShard = Depends(get_shard)):
    return await shard.get_lineage(artifact_id)

# ============ CHAINS ============

@router.post("/chains")
async def create_chain(
    title: str,
    description: Optional[str] = None,
    chain_type: str = "evidence",
    project_id: Optional[str] = None,
    shard: ProvenanceShard = Depends(get_shard)
):
    return await shard.create_chain(title, description, chain_type, project_id)

@router.get("/chains")
async def list_chains(
    project_id: Optional[str] = None,
    chain_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    shard: ProvenanceShard = Depends(get_shard)
):
    return await shard.list_chains(project_id, chain_type, status, limit, offset)

@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str, shard: ProvenanceShard = Depends(get_shard)):
    result = await shard.get_chain(chain_id)
    if not result:
        raise HTTPException(status_code=404, detail="Chain not found")
    return result

@router.patch("/chains/{chain_id}")
async def update_chain(
    chain_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    shard: ProvenanceShard = Depends(get_shard)
):
    result = await shard.update_chain(chain_id, title, description, status)
    if not result:
        raise HTTPException(status_code=404, detail="Chain not found")
    return result

@router.post("/chains/{chain_id}/verify")
async def verify_chain(
    chain_id: str,
    verified_by: Optional[str] = None,
    shard: ProvenanceShard = Depends(get_shard)
):
    return await shard.verify_chain(chain_id, verified_by)

# ============ LINKS ============

@router.post("/chains/{chain_id}/links")
async def add_link(
    chain_id: str,
    source_artifact_id: str,
    target_artifact_id: str,
    link_type: str,
    confidence: float = 1.0,
    shard: ProvenanceShard = Depends(get_shard)
):
    try:
        return await shard.add_link(chain_id, source_artifact_id, target_artifact_id, link_type, confidence)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/chains/{chain_id}/links")
async def get_chain_links(chain_id: str, shard: ProvenanceShard = Depends(get_shard)):
    return await shard.get_chain_links(chain_id)

@router.delete("/links/{link_id}")
async def remove_link(link_id: str, shard: ProvenanceShard = Depends(get_shard)):
    success = await shard.remove_link(link_id)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"deleted": True}

# ============ COUNT (for navigation badge) ============

@router.get("/count")
async def get_count(shard: ProvenanceShard = Depends(get_shard)):
    count = await shard.db.fetchval("SELECT COUNT(*) FROM arkham_provenance_chains")
    return {"count": count}
```

**Acceptance Criteria:**
- [ ] All 501 responses replaced with real implementations
- [ ] Proper error handling (404, 400)
- [ ] Query parameters for filtering/pagination
- [ ] `/count` endpoint for navigation badge
- [ ] Swagger docs generate correctly

---

## Task 8: Frontend Integration

**File:** `packages/arkham-shard-shell/src/pages/provenance/ProvenancePage.tsx`

**Key Changes:**

1. Replace mock data with API calls:
```tsx
const { data: chains, loading, refetch } = useFetch<Chain[]>('/api/provenance/chains');
```

2. Add chain creation form:
```tsx
const handleCreateChain = async () => {
  await fetch('/api/provenance/chains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description, chain_type: chainType })
  });
  refetch();
};
```

3. Add lineage visualization (can use existing graph component or simple tree):
```tsx
const { data: lineage } = useFetch<LineageGraph>(`/api/provenance/artifacts/${artifactId}/lineage`);
```

4. Wire up link creation UI

**Acceptance Criteria:**
- [ ] Chain list loads from API
- [ ] Create chain form works
- [ ] Chain detail page shows links
- [ ] Lineage view shows graph/tree
- [ ] Add/remove link UI functional
- [ ] Verify chain button works

---

## Task 9: Testing

### Manual Testing Checklist

```bash
# 1. Start system
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# 2. Check shard loaded
curl http://127.0.0.1:8100/health | jq '.shards.provenance'

# 3. Check tables created
# In psql:
\dt arkham_provenance*
# Should see: chains, links, artifacts, lineage, records, transformations, audit

# 4. Create artifact
curl -X POST "http://127.0.0.1:8100/api/provenance/artifacts" \
  -H "Content-Type: application/json" \
  -d '{"artifact_type": "document", "entity_id": "test-123", "entity_table": "arkham_documents", "title": "Test Doc"}'

# 5. Create chain
curl -X POST "http://127.0.0.1:8100/api/provenance/chains" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Chain", "chain_type": "evidence"}'

# 6. Add link (use IDs from above)
curl -X POST "http://127.0.0.1:8100/api/provenance/chains/{chain_id}/links" \
  -H "Content-Type: application/json" \
  -d '{"source_artifact_id": "...", "target_artifact_id": "...", "link_type": "derived_from"}'

# 7. Get lineage
curl "http://127.0.0.1:8100/api/provenance/artifacts/{artifact_id}/lineage"

# 8. Verify chain
curl -X POST "http://127.0.0.1:8100/api/provenance/chains/{chain_id}/verify"

# 9. Test event handling
# Upload a document through ingest shard
# Check that artifact was auto-created in provenance
```

---

## Summary

| Task | Effort | Dependencies |
|------|--------|--------------|
| 1. Database Schema | 30 min | None |
| 2. Artifact CRUD | 1 hr | Task 1 |
| 3. Chain CRUD | 1.5 hr | Task 1 |
| 4. Link CRUD | 1 hr | Tasks 2, 3 |
| 5. Lineage Traversal | 1.5 hr | Task 4 |
| 6. Event Handlers | 1 hr | Tasks 2, 4 |
| 7. API Endpoints | 1 hr | Tasks 2-5 |
| 8. Frontend | 2 hr | Task 7 |
| 9. Testing | 1 hr | All above |

**Total Estimated Effort:** ~10 hours

---

*Hand this to your agent. Reference ACH shard for patterns. Good luck.*
