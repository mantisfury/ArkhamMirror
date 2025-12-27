"""
Packets Shard - Main Shard Implementation

Investigation packet management for ArkhamFrame - bundle and share
documents, entities, and analyses.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

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
        self.frame = None
        self._db = None
        self._events = None
        self._storage = None
        self._initialized = False

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

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_packets WHERE id = ?",
            [packet_id],
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
        params = []

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.visibility:
                query += " AND visibility = ?"
                params.append(filter.visibility.value)
            if filter.created_by:
                query += " AND created_by = ?"
                params.append(filter.created_by)
            if filter.search_text:
                query += " AND (name LIKE ? OR description LIKE ?)"
                params.extend([f"%{filter.search_text}%", f"%{filter.search_text}%"])
            if filter.has_contents is not None:
                if filter.has_contents:
                    query += " AND contents_count > 0"
                else:
                    query += " AND contents_count = 0"
            if filter.min_version is not None:
                query += " AND version >= ?"
                params.append(filter.min_version)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

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

        packet.status = PacketStatus.FINALIZED
        packet.updated_at = datetime.utcnow()
        await self._save_packet(packet, update=True)

        # Create version snapshot
        await self._create_version_snapshot(packet_id, "Finalized packet")

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.finalized",
                {"packet_id": packet_id, "version": packet.version},
                source=self.name,
            )

        return packet

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

        await self._db.execute(
            "DELETE FROM arkham_packet_contents WHERE id = ? AND packet_id = ?",
            [content_entry_id, packet_id],
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

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_packet_contents WHERE packet_id = ? ORDER BY order_num, added_at",
            [packet_id],
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

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_packet_shares WHERE packet_id = ? ORDER BY shared_at DESC",
            [packet_id],
        )
        return [self._row_to_share(row) for row in rows]

    async def revoke_share(self, share_id: str) -> bool:
        """Revoke a packet share."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_packet_shares WHERE id = ?",
            [share_id],
        )
        return True

    async def export_packet(
        self,
        packet_id: str,
        format: ExportFormat = ExportFormat.ZIP,
    ) -> PacketExportResult:
        """Export a packet to a file."""
        packet = await self.get_packet(packet_id)
        if not packet:
            raise ValueError(f"Packet {packet_id} not found")

        contents = await self.get_packet_contents(packet_id)

        # Stub implementation - would actually bundle contents
        file_path = f"/exports/{packet_id}.{format.value}"
        file_size = 1024  # Placeholder

        result = PacketExportResult(
            packet_id=packet_id,
            export_format=format,
            file_path=file_path,
            file_size_bytes=file_size,
            contents_exported=len(contents),
            errors=[],
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.exported",
                {
                    "packet_id": packet_id,
                    "format": format.value,
                    "file_path": file_path,
                },
                source=self.name,
            )

        return result

    async def import_packet(
        self,
        file_path: str,
        merge_mode: str = "replace",
    ) -> PacketImportResult:
        """Import a packet from a file."""
        # Stub implementation
        packet_id = str(uuid4())

        result = PacketImportResult(
            packet_id=packet_id,
            import_source=file_path,
            contents_imported=0,
            merge_mode=merge_mode,
            errors=[],
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "packets.packet.imported",
                {
                    "packet_id": packet_id,
                    "import_source": file_path,
                },
                source=self.name,
            )

        return result

    async def get_packet_versions(self, packet_id: str) -> List[PacketVersion]:
        """Get version history for a packet."""
        if not self._db:
            return []

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_packet_versions WHERE packet_id = ? ORDER BY version_number DESC",
            [packet_id],
        )
        return [self._row_to_version(row) for row in rows]

    async def get_statistics(self) -> PacketStatistics:
        """Get statistics about packets in the system."""
        if not self._db:
            return PacketStatistics()

        # Total packets
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_packets"
        )
        total_packets = total["count"] if total else 0

        # By status
        status_rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) as count FROM arkham_packets GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By visibility
        vis_rows = await self._db.fetch_all(
            "SELECT visibility, COUNT(*) as count FROM arkham_packets GROUP BY visibility"
        )
        by_visibility = {row["visibility"]: row["count"] for row in vis_rows}

        # Total contents
        total_contents_row = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_packet_contents"
        )
        total_contents = total_contents_row["count"] if total_contents_row else 0

        # By content type
        content_type_rows = await self._db.fetch_all(
            "SELECT content_type, COUNT(*) as count FROM arkham_packet_contents GROUP BY content_type"
        )
        by_content_type = {row["content_type"]: row["count"] for row in content_type_rows}

        # Shares
        total_shares_row = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_packet_shares"
        )
        total_shares = total_shares_row["count"] if total_shares_row else 0

        # Averages
        avg_contents = await self._db.fetch_one(
            "SELECT AVG(contents_count) as avg FROM arkham_packets"
        )
        avg_size = await self._db.fetch_one(
            "SELECT AVG(size_bytes) as avg FROM arkham_packets"
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

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_packets WHERE status = ?",
                [status],
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
        data = (
            packet.id,
            packet.name,
            packet.description,
            packet.status.value,
            packet.visibility.value,
            packet.created_by,
            packet.created_at.isoformat(),
            packet.updated_at.isoformat(),
            packet.version,
            packet.contents_count,
            packet.size_bytes,
            packet.checksum,
            json.dumps(packet.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_packets SET
                    name=?, description=?, status=?, visibility=?,
                    created_by=?, created_at=?, updated_at=?,
                    version=?, contents_count=?, size_bytes=?, checksum=?, metadata=?
                WHERE id=?
            """, data[1:] + (packet.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_packets (
                    id, name, description, status, visibility,
                    created_by, created_at, updated_at,
                    version, contents_count, size_bytes, checksum, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_content(self, content: PacketContent) -> None:
        """Save packet content to the database."""
        if not self._db:
            return

        await self._db.execute("""
            INSERT INTO arkham_packet_contents (
                id, packet_id, content_type, content_id, content_title,
                added_at, added_by, order_num
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content.id,
            content.packet_id,
            content.content_type.value,
            content.content_id,
            content.content_title,
            content.added_at.isoformat(),
            content.added_by,
            content.order,
        ))

    async def _save_share(self, share: PacketShare) -> None:
        """Save packet share to the database."""
        if not self._db:
            return

        await self._db.execute("""
            INSERT INTO arkham_packet_shares (
                id, packet_id, shared_with, permissions,
                shared_at, expires_at, access_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            share.id,
            share.packet_id,
            share.shared_with,
            share.permissions.value,
            share.shared_at.isoformat(),
            share.expires_at.isoformat() if share.expires_at else None,
            share.access_token,
        ))

    async def _save_version(self, version: PacketVersion) -> None:
        """Save packet version to the database."""
        if not self._db:
            return

        await self._db.execute("""
            INSERT INTO arkham_packet_versions (
                id, packet_id, version_number, created_at,
                changes_summary, snapshot_path
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            version.id,
            version.packet_id,
            version.version_number,
            version.created_at.isoformat(),
            version.changes_summary,
            version.snapshot_path,
        ))

    async def _update_packet_counts(self, packet_id: str) -> None:
        """Update content counts on a packet."""
        if not self._db:
            return

        count_row = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_packet_contents WHERE packet_id = ?",
            [packet_id],
        )
        count = count_row["count"] if count_row else 0

        await self._db.execute("""
            UPDATE arkham_packets SET
                contents_count = ?,
                updated_at = ?
            WHERE id = ?
        """, [count, datetime.utcnow().isoformat(), packet_id])

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
