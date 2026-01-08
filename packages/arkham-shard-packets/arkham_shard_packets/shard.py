"""
Packets Shard - Main Shard Implementation

Investigation packet management for ArkhamFrame - bundle and share
documents, entities, and analyses.
"""

import hashlib
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from arkham_frame import ArkhamShard

# Base URL for internal API calls
INTERNAL_API_BASE = "http://127.0.0.1:8100"

from .models import (
    ContentType,
    Packet,
    PacketContent,
    PacketExportResult,
    PacketFilter,
    PacketImportResult,
    PacketShare,
    PacketStatistics,
    PacketStatus,
    PacketVersion,
    PacketVisibility,
    SharePermission,
    ExportFormat,
)

logger = logging.getLogger(__name__)


class PacketsShard(ArkhamShard):
    """
    Packets Shard - Bundle and share investigation materials.

    This shard provides:
    - Packet creation and management
    - Content bundling (documents, entities, analyses)
    - Access control and sharing
    - Version control and snapshots
    - Export and import capabilities
    """

    name = "packets"
    version = "0.1.0"
    description = "Investigation packet management for bundling and sharing materials"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._storage = None
        self._initialized = False
        self._packets_dir = None

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.get_service("database")
        if not self._db:
            raise RuntimeError("Database service required for Packets shard")

        self._events = frame.get_service("events")
        if not self._events:
            raise RuntimeError("Events service required for Packets shard")

        self._storage = frame.get_service("storage")
        if not self._storage:
            logger.info("Storage service not available - export features limited")

        # Setup packets output directory
        self._packets_dir = os.path.join(tempfile.gettempdir(), "arkham_packets")
        os.makedirs(self._packets_dir, exist_ok=True)

        # Create database schema
        await self._create_schema()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.packets_shard = self

        self._initialized = True
        logger.info(f"PacketsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        self._initialized = False
        logger.info("PacketsShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for packets shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_packets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                visibility TEXT DEFAULT 'private',

                created_by TEXT DEFAULT 'system',
                created_at TEXT,
                updated_at TEXT,

                version INTEGER DEFAULT 1,

                contents_count INTEGER DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                checksum TEXT,

                metadata TEXT DEFAULT '{}'
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_packet_contents (
                id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                content_title TEXT,
                added_at TEXT,
                added_by TEXT DEFAULT 'system',
                order_num INTEGER DEFAULT 0,

                FOREIGN KEY (packet_id) REFERENCES arkham_packets(id)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_packet_shares (
                id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                shared_with TEXT,
                permissions TEXT DEFAULT 'view',
                shared_at TEXT,
                expires_at TEXT,
                access_token TEXT,

                FOREIGN KEY (packet_id) REFERENCES arkham_packets(id)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_packet_versions (
                id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                version_number INTEGER,
                created_at TEXT,
                changes_summary TEXT,
                snapshot_path TEXT,

                FOREIGN KEY (packet_id) REFERENCES arkham_packets(id)
            )
        """)

        # Create indexes for common queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packets_status ON arkham_packets(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packets_creator ON arkham_packets(created_by)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_contents_packet ON arkham_packet_contents(packet_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_shares_packet ON arkham_packet_shares(packet_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_shares_token ON arkham_packet_shares(access_token)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_versions_packet ON arkham_packet_versions(packet_id)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_packets', 'arkham_packet_contents', 'arkham_packet_shares', 'arkham_packet_versions'];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packets_tenant
            ON arkham_packets(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packet_contents_tenant
            ON arkham_packet_contents(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packet_shares_tenant
            ON arkham_packet_shares(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_packet_versions_tenant
            ON arkham_packet_versions(tenant_id)
        """)

        logger.debug("Packets schema created/verified")

    # === Public API Methods ===

    async def create_packet(
        self,
        name: str,
        description: str = "",
        created_by: str = "system",
        visibility: PacketVisibility = PacketVisibility.PRIVATE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Packet:
        """Create a new packet."""
        packet_id = str(uuid4())
        now = datetime.utcnow()

        packet = Packet(
            id=packet_id,
            name=name,
            description=description,
            status=PacketStatus.DRAFT,
            visibility=visibility,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            version=1,
            metadata=metadata or {},
        )

        await self._save_packet(packet)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.created",
                {
                    "packet_id": packet_id,
                    "name": name,
                    "created_by": created_by,
                },
                source=self.name,
            )

        return packet

    async def get_packet(self, packet_id: str) -> Optional[Packet]:
        """Get a packet by ID."""
        if not self._db:
            return None

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_packets WHERE id = :packet_id AND tenant_id = :tenant_id",
                {"packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_packets WHERE id = :packet_id",
                {"packet_id": packet_id},
            )
        return self._row_to_packet(row) if row else None

    async def list_packets(
        self,
        filter: Optional[PacketFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Packet]:
        """List packets with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_packets WHERE 1=1"
        params: Dict[str, Any] = {}

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if filter:
            if filter.status:
                query += " AND status = :status"
                params["status"] = filter.status.value
            if filter.visibility:
                query += " AND visibility = :visibility"
                params["visibility"] = filter.visibility.value
            if filter.created_by:
                query += " AND created_by = :created_by"
                params["created_by"] = filter.created_by
            if filter.search_text:
                query += " AND (name LIKE :search_text OR description LIKE :search_text)"
                params["search_text"] = f"%{filter.search_text}%"
            if filter.has_contents is not None:
                if filter.has_contents:
                    query += " AND contents_count > 0"
                else:
                    query += " AND contents_count = 0"
            if filter.min_version is not None:
                query += " AND version >= :min_version"
                params["min_version"] = filter.min_version

        query += " ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_packet(row) for row in rows]

    async def update_packet(
        self,
        packet_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        visibility: Optional[PacketVisibility] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Packet]:
        """Update packet metadata."""
        packet = await self.get_packet(packet_id)
        if not packet:
            return None

        if packet.status != PacketStatus.DRAFT:
            logger.warning(f"Cannot update finalized packet {packet_id}")
            return packet

        if name:
            packet.name = name
        if description:
            packet.description = description
        if visibility:
            packet.visibility = visibility
        if metadata:
            packet.metadata.update(metadata)

        packet.updated_at = datetime.utcnow()
        await self._save_packet(packet, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.updated",
                {"packet_id": packet_id},
                source=self.name,
            )

        return packet

    async def finalize_packet(self, packet_id: str) -> Optional[Packet]:
        """Finalize a packet (lock for sharing)."""
        packet = await self.get_packet(packet_id)
        if not packet:
            return None

        # Calculate checksum before finalizing
        contents = await self.get_packet_contents(packet_id)
        checksum = await self._calculate_checksum(packet, contents)

        packet.status = PacketStatus.FINALIZED
        packet.checksum = checksum
        packet.updated_at = datetime.utcnow()
        await self._save_packet(packet, update=True)

        # Create version snapshot
        await self._create_version_snapshot(packet_id, "Finalized packet")

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.finalized",
                {"packet_id": packet_id, "version": packet.version, "checksum": checksum},
                source=self.name,
            )

        return packet

    async def _calculate_checksum(
        self,
        packet: Packet,
        contents: List[PacketContent],
    ) -> str:
        """Calculate SHA256 checksum for packet integrity."""
        hasher = hashlib.sha256()

        # Hash packet metadata
        packet_data = json.dumps({
            "id": packet.id,
            "name": packet.name,
            "description": packet.description,
            "version": packet.version,
            "created_at": packet.created_at.isoformat(),
        }, sort_keys=True).encode('utf-8')
        hasher.update(packet_data)

        # Hash contents
        for content in sorted(contents, key=lambda c: c.content_id):
            content_data = json.dumps({
                "content_type": content.content_type.value,
                "content_id": content.content_id,
                "content_title": content.content_title,
                "order": content.order,
            }, sort_keys=True).encode('utf-8')
            hasher.update(content_data)

        return hasher.hexdigest()

    async def archive_packet(self, packet_id: str) -> Optional[Packet]:
        """Archive a packet."""
        packet = await self.get_packet(packet_id)
        if not packet:
            return None

        packet.status = PacketStatus.ARCHIVED
        packet.updated_at = datetime.utcnow()
        await self._save_packet(packet, update=True)

        return packet

    async def add_content(
        self,
        packet_id: str,
        content_type: ContentType,
        content_id: str,
        content_title: str,
        added_by: str = "system",
        order: int = 0,
    ) -> PacketContent:
        """Add content to a packet."""
        packet = await self.get_packet(packet_id)
        if not packet:
            raise ValueError(f"Packet {packet_id} not found")

        if packet.status != PacketStatus.DRAFT:
            raise ValueError(f"Cannot add content to {packet.status} packet")

        content_entry_id = str(uuid4())
        now = datetime.utcnow()

        content = PacketContent(
            id=content_entry_id,
            packet_id=packet_id,
            content_type=content_type,
            content_id=content_id,
            content_title=content_title,
            added_at=now,
            added_by=added_by,
            order=order,
        )

        await self._save_content(content)
        await self._update_packet_counts(packet_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.content.added",
                {
                    "packet_id": packet_id,
                    "content_id": content_id,
                    "content_type": content_type.value,
                },
                source=self.name,
            )

        return content

    async def remove_content(self, packet_id: str, content_entry_id: str) -> bool:
        """Remove content from a packet."""
        packet = await self.get_packet(packet_id)
        if not packet or packet.status != PacketStatus.DRAFT:
            return False

        if not self._db:
            return False

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            await self._db.execute(
                "DELETE FROM arkham_packet_contents WHERE id = :id AND packet_id = :packet_id AND tenant_id = :tenant_id",
                {"id": content_entry_id, "packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            await self._db.execute(
                "DELETE FROM arkham_packet_contents WHERE id = :id AND packet_id = :packet_id",
                {"id": content_entry_id, "packet_id": packet_id},
            )

        await self._update_packet_counts(packet_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.content.removed",
                {"packet_id": packet_id, "content_entry_id": content_entry_id},
                source=self.name,
            )

        return True

    async def get_packet_contents(self, packet_id: str) -> List[PacketContent]:
        """Get all contents for a packet."""
        if not self._db:
            return []

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_contents WHERE packet_id = :packet_id AND tenant_id = :tenant_id ORDER BY order_num, added_at",
                {"packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_contents WHERE packet_id = :packet_id ORDER BY order_num, added_at",
                {"packet_id": packet_id},
            )
        return [self._row_to_content(row) for row in rows]

    async def share_packet(
        self,
        packet_id: str,
        shared_with: str,
        permissions: SharePermission = SharePermission.VIEW,
        expires_at: Optional[datetime] = None,
    ) -> PacketShare:
        """Create a share for a packet."""
        packet = await self.get_packet(packet_id)
        if not packet:
            raise ValueError(f"Packet {packet_id} not found")

        share_id = str(uuid4())
        access_token = str(uuid4())
        now = datetime.utcnow()

        share = PacketShare(
            id=share_id,
            packet_id=packet_id,
            shared_with=shared_with,
            permissions=permissions,
            shared_at=now,
            expires_at=expires_at,
            access_token=access_token,
        )

        await self._save_share(share)

        # Update packet status if first share
        if packet.status == PacketStatus.FINALIZED:
            packet.status = PacketStatus.SHARED
            await self._save_packet(packet, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.shared",
                {
                    "packet_id": packet_id,
                    "shared_with": shared_with,
                    "permissions": permissions.value,
                },
                source=self.name,
            )

        return share

    async def get_packet_shares(self, packet_id: str) -> List[PacketShare]:
        """Get all shares for a packet."""
        if not self._db:
            return []

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_shares WHERE packet_id = :packet_id AND tenant_id = :tenant_id ORDER BY shared_at DESC",
                {"packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_shares WHERE packet_id = :packet_id ORDER BY shared_at DESC",
                {"packet_id": packet_id},
            )
        return [self._row_to_share(row) for row in rows]

    async def revoke_share(self, share_id: str) -> bool:
        """Revoke a packet share."""
        if not self._db:
            return False

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            await self._db.execute(
                "DELETE FROM arkham_packet_shares WHERE id = :id AND tenant_id = :tenant_id",
                {"id": share_id, "tenant_id": str(tenant_id)},
            )
        else:
            await self._db.execute(
                "DELETE FROM arkham_packet_shares WHERE id = :id",
                {"id": share_id},
            )
        return True

    async def export_packet(
        self,
        packet_id: str,
        format: ExportFormat = ExportFormat.ZIP,
    ) -> PacketExportResult:
        """Export a packet to a file bundle."""
        packet = await self.get_packet(packet_id)
        if not packet:
            raise ValueError(f"Packet {packet_id} not found")

        contents = await self.get_packet_contents(packet_id)
        errors: List[str] = []

        # Create output file
        filename = f"packet_{packet_id[:8]}.{format.value}"
        file_path = os.path.join(self._packets_dir, filename)

        if format == ExportFormat.ZIP:
            file_size, contents_exported = await self._export_to_zip(
                packet, contents, file_path, errors
            )
        elif format == ExportFormat.JSON:
            file_size, contents_exported = await self._export_to_json(
                packet, contents, file_path, errors
            )
        else:
            # Fallback to ZIP
            file_size, contents_exported = await self._export_to_zip(
                packet, contents, file_path, errors
            )

        result = PacketExportResult(
            packet_id=packet_id,
            export_format=format,
            file_path=file_path,
            file_size_bytes=file_size,
            contents_exported=contents_exported,
            errors=errors,
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.exported",
                {
                    "packet_id": packet_id,
                    "format": format.value,
                    "file_path": file_path,
                    "file_size": file_size,
                    "contents_exported": contents_exported,
                },
                source=self.name,
            )

        return result

    async def _export_to_zip(
        self,
        packet: Packet,
        contents: List[PacketContent],
        file_path: str,
        errors: List[str],
    ) -> tuple[int, int]:
        """Export packet to ZIP file with manifest and content data."""
        contents_exported = 0

        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Create manifest
            manifest = {
                "packet": {
                    "id": packet.id,
                    "name": packet.name,
                    "description": packet.description,
                    "status": packet.status.value,
                    "visibility": packet.visibility.value,
                    "version": packet.version,
                    "created_by": packet.created_by,
                    "created_at": packet.created_at.isoformat(),
                    "updated_at": packet.updated_at.isoformat(),
                    "checksum": packet.checksum,
                    "metadata": packet.metadata,
                },
                "contents": [],
                "exported_at": datetime.utcnow().isoformat(),
                "export_version": "1.0",
            }

            # Fetch and bundle each content item
            async with httpx.AsyncClient(timeout=60.0) as client:
                for content in contents:
                    content_data = await self._fetch_content_data(
                        client, content.content_type, content.content_id
                    )

                    if content_data:
                        # Add to manifest
                        content_entry = {
                            "id": content.id,
                            "content_type": content.content_type.value,
                            "content_id": content.content_id,
                            "content_title": content.content_title,
                            "order": content.order,
                            "added_at": content.added_at.isoformat(),
                            "added_by": content.added_by,
                            "filename": f"contents/{content.content_type.value}_{content.content_id}.json",
                        }
                        manifest["contents"].append(content_entry)

                        # Add content file to ZIP
                        content_json = json.dumps(content_data, indent=2, default=str)
                        zf.writestr(content_entry["filename"], content_json)
                        contents_exported += 1
                    else:
                        errors.append(f"Failed to fetch {content.content_type.value}:{content.content_id}")

            # Write manifest
            manifest_json = json.dumps(manifest, indent=2, default=str)
            zf.writestr("manifest.json", manifest_json)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        return file_size, contents_exported

    async def _export_to_json(
        self,
        packet: Packet,
        contents: List[PacketContent],
        file_path: str,
        errors: List[str],
    ) -> tuple[int, int]:
        """Export packet to single JSON file."""
        contents_exported = 0

        export_data = {
            "packet": {
                "id": packet.id,
                "name": packet.name,
                "description": packet.description,
                "status": packet.status.value,
                "visibility": packet.visibility.value,
                "version": packet.version,
                "created_by": packet.created_by,
                "created_at": packet.created_at.isoformat(),
                "updated_at": packet.updated_at.isoformat(),
                "checksum": packet.checksum,
                "metadata": packet.metadata,
            },
            "contents": [],
            "exported_at": datetime.utcnow().isoformat(),
            "export_version": "1.0",
        }

        # Fetch each content item
        async with httpx.AsyncClient(timeout=60.0) as client:
            for content in contents:
                content_data = await self._fetch_content_data(
                    client, content.content_type, content.content_id
                )

                content_entry = {
                    "id": content.id,
                    "content_type": content.content_type.value,
                    "content_id": content.content_id,
                    "content_title": content.content_title,
                    "order": content.order,
                    "added_at": content.added_at.isoformat(),
                    "added_by": content.added_by,
                    "data": content_data,
                }
                export_data["contents"].append(content_entry)

                if content_data:
                    contents_exported += 1
                else:
                    errors.append(f"Failed to fetch {content.content_type.value}:{content.content_id}")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        return file_size, contents_exported

    async def _fetch_content_data(
        self,
        client: httpx.AsyncClient,
        content_type: ContentType,
        content_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch content data from appropriate shard API."""
        try:
            endpoint_map = {
                ContentType.DOCUMENT: f"/api/documents/{content_id}",
                ContentType.ENTITY: f"/api/entities/{content_id}",
                ContentType.CLAIM: f"/api/claims/{content_id}",
                ContentType.ACH_MATRIX: f"/api/ach/matrix/{content_id}",
                ContentType.TIMELINE: f"/api/timeline/events?id={content_id}",
                ContentType.CONTRADICTION: f"/api/contradictions/{content_id}",
                ContentType.PATTERN: f"/api/patterns/{content_id}",
                ContentType.REPORT: f"/api/reports/{content_id}",
                ContentType.GRAPH: f"/api/graph/{content_id}",
            }

            endpoint = endpoint_map.get(content_type)
            if not endpoint:
                logger.warning(f"Unknown content type: {content_type}")
                return None

            response = await client.get(f"{INTERNAL_API_BASE}{endpoint}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch {content_type.value}:{content_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching {content_type.value}:{content_id}: {e}")
            return None

    async def import_packet(
        self,
        file_path: str,
        merge_mode: str = "replace",
    ) -> PacketImportResult:
        """Import a packet from a file bundle."""
        errors: List[str] = []
        contents_imported = 0
        packet_id = None

        # Determine format from file extension
        if file_path.endswith('.zip'):
            packet_id, contents_imported = await self._import_from_zip(
                file_path, merge_mode, errors
            )
        elif file_path.endswith('.json'):
            packet_id, contents_imported = await self._import_from_json(
                file_path, merge_mode, errors
            )
        else:
            errors.append(f"Unsupported file format: {file_path}")
            packet_id = str(uuid4())

        result = PacketImportResult(
            packet_id=packet_id or str(uuid4()),
            import_source=file_path,
            contents_imported=contents_imported,
            merge_mode=merge_mode,
            errors=errors,
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.imported",
                {
                    "packet_id": result.packet_id,
                    "import_source": file_path,
                    "contents_imported": contents_imported,
                    "merge_mode": merge_mode,
                },
                source=self.name,
            )

        return result

    async def _import_from_zip(
        self,
        file_path: str,
        merge_mode: str,
        errors: List[str],
    ) -> tuple[Optional[str], int]:
        """Import packet from ZIP file."""
        contents_imported = 0

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Read manifest
                if 'manifest.json' not in zf.namelist():
                    errors.append("Missing manifest.json in ZIP file")
                    return None, 0

                manifest_data = zf.read('manifest.json')
                manifest = json.loads(manifest_data)

                packet_data = manifest.get("packet", {})

                # Create or update packet based on merge mode
                if merge_mode == "replace":
                    # Generate new ID for imported packet
                    packet_id = str(uuid4())
                else:
                    # Use original ID (merge mode)
                    packet_id = packet_data.get("id", str(uuid4()))

                # Create packet
                packet = await self.create_packet(
                    name=packet_data.get("name", "Imported Packet"),
                    description=packet_data.get("description", ""),
                    created_by=packet_data.get("created_by", "import"),
                    metadata=packet_data.get("metadata", {}),
                )
                packet_id = packet.id

                # Import contents
                for content_entry in manifest.get("contents", []):
                    try:
                        content_type = ContentType(content_entry.get("content_type", "document"))

                        # Note: We just recreate the content entries, not the actual data
                        # The data would need to be imported via the respective shards
                        await self.add_content(
                            packet_id=packet_id,
                            content_type=content_type,
                            content_id=content_entry.get("content_id", str(uuid4())),
                            content_title=content_entry.get("content_title", "Imported"),
                            added_by="import",
                            order=content_entry.get("order", 0),
                        )
                        contents_imported += 1
                    except Exception as e:
                        errors.append(f"Failed to import content: {e}")

                return packet_id, contents_imported

        except Exception as e:
            errors.append(f"Failed to read ZIP file: {e}")
            return None, 0

    async def _import_from_json(
        self,
        file_path: str,
        merge_mode: str,
        errors: List[str],
    ) -> tuple[Optional[str], int]:
        """Import packet from JSON file."""
        contents_imported = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                export_data = json.load(f)

            packet_data = export_data.get("packet", {})

            # Create packet
            packet = await self.create_packet(
                name=packet_data.get("name", "Imported Packet"),
                description=packet_data.get("description", ""),
                created_by=packet_data.get("created_by", "import"),
                metadata=packet_data.get("metadata", {}),
            )
            packet_id = packet.id

            # Import contents
            for content_entry in export_data.get("contents", []):
                try:
                    content_type = ContentType(content_entry.get("content_type", "document"))

                    await self.add_content(
                        packet_id=packet_id,
                        content_type=content_type,
                        content_id=content_entry.get("content_id", str(uuid4())),
                        content_title=content_entry.get("content_title", "Imported"),
                        added_by="import",
                        order=content_entry.get("order", 0),
                    )
                    contents_imported += 1
                except Exception as e:
                    errors.append(f"Failed to import content: {e}")

            return packet_id, contents_imported

        except Exception as e:
            errors.append(f"Failed to read JSON file: {e}")
            return None, 0

    async def get_packet_versions(self, packet_id: str) -> List[PacketVersion]:
        """Get version history for a packet."""
        if not self._db:
            return []

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_versions WHERE packet_id = :packet_id AND tenant_id = :tenant_id ORDER BY version_number DESC",
                {"packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT * FROM arkham_packet_versions WHERE packet_id = :packet_id ORDER BY version_number DESC",
                {"packet_id": packet_id},
            )
        return [self._row_to_version(row) for row in rows]

    async def get_statistics(self) -> PacketStatistics:
        """Get statistics about packets in the system."""
        if not self._db:
            return PacketStatistics()

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        tenant_filter_and = " AND tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        # Total packets
        total = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_packets{tenant_filter}",
            params,
        )
        total_packets = total["count"] if total else 0

        # By status
        status_rows = await self._db.fetch_all(
            f"SELECT status, COUNT(*) as count FROM arkham_packets{tenant_filter} GROUP BY status",
            params,
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By visibility
        vis_rows = await self._db.fetch_all(
            f"SELECT visibility, COUNT(*) as count FROM arkham_packets{tenant_filter} GROUP BY visibility",
            params,
        )
        by_visibility = {row["visibility"]: row["count"] for row in vis_rows}

        # Total contents
        total_contents_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_packet_contents{tenant_filter}",
            params,
        )
        total_contents = total_contents_row["count"] if total_contents_row else 0

        # By content type
        content_type_rows = await self._db.fetch_all(
            f"SELECT content_type, COUNT(*) as count FROM arkham_packet_contents{tenant_filter} GROUP BY content_type",
            params,
        )
        by_content_type = {row["content_type"]: row["count"] for row in content_type_rows}

        # Shares
        total_shares_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_packet_shares{tenant_filter}",
            params,
        )
        total_shares = total_shares_row["count"] if total_shares_row else 0

        # Averages
        avg_contents = await self._db.fetch_one(
            f"SELECT AVG(contents_count) as avg FROM arkham_packets{tenant_filter}",
            params,
        )
        avg_size = await self._db.fetch_one(
            f"SELECT AVG(size_bytes) as avg FROM arkham_packets{tenant_filter}",
            params,
        )

        return PacketStatistics(
            total_packets=total_packets,
            by_status=by_status,
            by_visibility=by_visibility,
            total_contents=total_contents,
            by_content_type=by_content_type,
            total_shares=total_shares,
            active_shares=total_shares,  # Stub
            expired_shares=0,  # Stub
            total_versions=0,  # Stub
            avg_contents_per_packet=avg_contents["avg"] if avg_contents and avg_contents["avg"] else 0.0,
            avg_size_bytes=avg_size["avg"] if avg_size and avg_size["avg"] else 0.0,
        )

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of packets, optionally filtered by status."""
        if not self._db:
            return 0

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()

        if status:
            if tenant_id:
                result = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_packets WHERE status = :status AND tenant_id = :tenant_id",
                    {"status": status, "tenant_id": str(tenant_id)},
                )
            else:
                result = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_packets WHERE status = :status",
                    {"status": status},
                )
        else:
            if tenant_id:
                result = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_packets WHERE tenant_id = :tenant_id",
                    {"tenant_id": str(tenant_id)},
                )
            else:
                result = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_packets"
                )

        return result["count"] if result else 0

    # === Private Helper Methods ===

    async def _save_packet(self, packet: Packet, update: bool = False) -> None:
        """Save a packet to the database."""
        if not self._db:
            return

        import json
        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        params = {
            "id": packet.id,
            "name": packet.name,
            "description": packet.description,
            "status": packet.status.value,
            "visibility": packet.visibility.value,
            "created_by": packet.created_by,
            "created_at": packet.created_at.isoformat(),
            "updated_at": packet.updated_at.isoformat(),
            "version": packet.version,
            "contents_count": packet.contents_count,
            "size_bytes": packet.size_bytes,
            "checksum": packet.checksum,
            "metadata": json.dumps(packet.metadata),
            "tenant_id": str(tenant_id) if tenant_id else None,
        }

        if update:
            if tenant_id:
                await self._db.execute("""
                    UPDATE arkham_packets SET
                        name=:name, description=:description, status=:status, visibility=:visibility,
                        created_by=:created_by, created_at=:created_at, updated_at=:updated_at,
                        version=:version, contents_count=:contents_count, size_bytes=:size_bytes,
                        checksum=:checksum, metadata=:metadata, tenant_id=:tenant_id
                    WHERE id=:id AND tenant_id=:tenant_id
                """, params)
            else:
                await self._db.execute("""
                    UPDATE arkham_packets SET
                        name=:name, description=:description, status=:status, visibility=:visibility,
                        created_by=:created_by, created_at=:created_at, updated_at=:updated_at,
                        version=:version, contents_count=:contents_count, size_bytes=:size_bytes,
                        checksum=:checksum, metadata=:metadata
                    WHERE id=:id
                """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_packets (
                    id, name, description, status, visibility,
                    created_by, created_at, updated_at,
                    version, contents_count, size_bytes, checksum, metadata, tenant_id
                ) VALUES (:id, :name, :description, :status, :visibility,
                    :created_by, :created_at, :updated_at,
                    :version, :contents_count, :size_bytes, :checksum, :metadata, :tenant_id)
            """, params)

    async def _save_content(self, content: PacketContent) -> None:
        """Save packet content to the database."""
        if not self._db:
            return

        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        await self._db.execute("""
            INSERT INTO arkham_packet_contents (
                id, packet_id, content_type, content_id, content_title,
                added_at, added_by, order_num, tenant_id
            ) VALUES (:id, :packet_id, :content_type, :content_id, :content_title,
                :added_at, :added_by, :order_num, :tenant_id)
        """, {
            "id": content.id,
            "packet_id": content.packet_id,
            "content_type": content.content_type.value,
            "content_id": content.content_id,
            "content_title": content.content_title,
            "added_at": content.added_at.isoformat(),
            "added_by": content.added_by,
            "order_num": content.order,
            "tenant_id": str(tenant_id) if tenant_id else None,
        })

    async def _save_share(self, share: PacketShare) -> None:
        """Save packet share to the database."""
        if not self._db:
            return

        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        await self._db.execute("""
            INSERT INTO arkham_packet_shares (
                id, packet_id, shared_with, permissions,
                shared_at, expires_at, access_token, tenant_id
            ) VALUES (:id, :packet_id, :shared_with, :permissions,
                :shared_at, :expires_at, :access_token, :tenant_id)
        """, {
            "id": share.id,
            "packet_id": share.packet_id,
            "shared_with": share.shared_with,
            "permissions": share.permissions.value,
            "shared_at": share.shared_at.isoformat(),
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
            "access_token": share.access_token,
            "tenant_id": str(tenant_id) if tenant_id else None,
        })

    async def _save_version(self, version: PacketVersion) -> None:
        """Save packet version to the database."""
        if not self._db:
            return

        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        await self._db.execute("""
            INSERT INTO arkham_packet_versions (
                id, packet_id, version_number, created_at,
                changes_summary, snapshot_path, tenant_id
            ) VALUES (:id, :packet_id, :version_number, :created_at,
                :changes_summary, :snapshot_path, :tenant_id)
        """, {
            "id": version.id,
            "packet_id": version.packet_id,
            "version_number": version.version_number,
            "created_at": version.created_at.isoformat(),
            "changes_summary": version.changes_summary,
            "snapshot_path": version.snapshot_path,
            "tenant_id": str(tenant_id) if tenant_id else None,
        })

    async def _update_packet_counts(self, packet_id: str) -> None:
        """Update content counts on a packet."""
        if not self._db:
            return

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            count_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_packet_contents WHERE packet_id = :packet_id AND tenant_id = :tenant_id",
                {"packet_id": packet_id, "tenant_id": str(tenant_id)},
            )
        else:
            count_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_packet_contents WHERE packet_id = :packet_id",
                {"packet_id": packet_id},
            )
        count = count_row["count"] if count_row else 0

        if tenant_id:
            await self._db.execute("""
                UPDATE arkham_packets SET
                    contents_count = :contents_count,
                    updated_at = :updated_at
                WHERE id = :id AND tenant_id = :tenant_id
            """, {"contents_count": count, "updated_at": datetime.utcnow().isoformat(), "id": packet_id, "tenant_id": str(tenant_id)})
        else:
            await self._db.execute("""
                UPDATE arkham_packets SET
                    contents_count = :contents_count,
                    updated_at = :updated_at
                WHERE id = :id
            """, {"contents_count": count, "updated_at": datetime.utcnow().isoformat(), "id": packet_id})

    async def _create_version_snapshot(
        self,
        packet_id: str,
        changes_summary: str,
    ) -> PacketVersion:
        """Create a version snapshot."""
        packet = await self.get_packet(packet_id)
        if not packet:
            raise ValueError(f"Packet {packet_id} not found")

        version_id = str(uuid4())
        snapshot_path = f"/snapshots/{packet_id}_v{packet.version}.json"

        version = PacketVersion(
            id=version_id,
            packet_id=packet_id,
            version_number=packet.version,
            created_at=datetime.utcnow(),
            changes_summary=changes_summary,
            snapshot_path=snapshot_path,
        )

        await self._save_version(version)

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.version.created",
                {
                    "packet_id": packet_id,
                    "version_number": packet.version,
                },
                source=self.name,
            )

        return version

    def _row_to_packet(self, row: Dict[str, Any]) -> Packet:
        """Convert database row to Packet object."""
        import json
        return Packet(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=PacketStatus(row["status"]),
            visibility=PacketVisibility(row["visibility"]),
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            version=row["version"],
            contents_count=row["contents_count"],
            size_bytes=row["size_bytes"],
            checksum=row["checksum"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _row_to_content(self, row: Dict[str, Any]) -> PacketContent:
        """Convert database row to PacketContent object."""
        return PacketContent(
            id=row["id"],
            packet_id=row["packet_id"],
            content_type=ContentType(row["content_type"]),
            content_id=row["content_id"],
            content_title=row["content_title"],
            added_at=datetime.fromisoformat(row["added_at"]) if row["added_at"] else datetime.utcnow(),
            added_by=row["added_by"],
            order=row["order_num"],
        )

    def _row_to_share(self, row: Dict[str, Any]) -> PacketShare:
        """Convert database row to PacketShare object."""
        return PacketShare(
            id=row["id"],
            packet_id=row["packet_id"],
            shared_with=row["shared_with"],
            permissions=SharePermission(row["permissions"]),
            shared_at=datetime.fromisoformat(row["shared_at"]) if row["shared_at"] else datetime.utcnow(),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
            access_token=row["access_token"],
        )

    def _row_to_version(self, row: Dict[str, Any]) -> PacketVersion:
        """Convert database row to PacketVersion object."""
        return PacketVersion(
            id=row["id"],
            packet_id=row["packet_id"],
            version_number=row["version_number"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            changes_summary=row["changes_summary"],
            snapshot_path=row["snapshot_path"],
        )
