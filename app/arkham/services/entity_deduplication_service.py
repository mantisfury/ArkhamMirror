"""
Entity Deduplication Service for Reflex

Provides entity deduplication functionality for the Reflex UI:
- Get duplicate candidates for manual review
- Manual merge operations
- Automatic deduplication triggers
- Statistics and monitoring
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import create_engine, func, or_
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from .db.models import Entity, CanonicalEntity, EntityRelationship, EntityMergeAudit
from .entity_resolution import EntityResolver

logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class EntityDeduplicationService:
    """
    Service for entity deduplication operations.
    """

    def __init__(self):
        self.resolver = EntityResolver()

    def get_duplicate_candidates(
        self,
        label_filter: Optional[str] = None,
        min_similarity: float = 0.75,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get candidate pairs of canonical entities that might be duplicates.

        Returns:
            List of dicts with keys:
                - id1, id2: Canonical entity IDs
                - name1, name2: Canonical names
                - label: Entity type
                - similarity: Similarity score (0-1)
                - mentions1, mentions2: Total mention counts
                - aliases1, aliases2: List of known aliases
        """
        session = Session()
        try:
            # Get canonical entities
            query = session.query(CanonicalEntity)
            if label_filter:
                query = query.filter(CanonicalEntity.label == label_filter)

            canonicals = query.all()

            candidates = []
            checked_pairs = set()

            # Compare all pairs
            for i, c1 in enumerate(canonicals):
                for c2 in canonicals[i + 1 :]:
                    # Skip if already checked
                    pair_key = tuple(sorted([c1.id, c2.id]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)

                    # Skip if different labels
                    if c1.label != c2.label:
                        continue

                    # Calculate similarity
                    similarity = self.resolver.similarity_score(
                        self.resolver.normalize_text(c1.canonical_name),
                        self.resolver.normalize_text(c2.canonical_name),
                    )

                    # Check if they match according to resolver rules
                    is_match = self.resolver.is_match(
                        c1.canonical_name,
                        c2.canonical_name,
                        c1.label,
                    )

                    # Include if similarity is above threshold or if resolver says they match
                    if similarity >= min_similarity or is_match:
                        candidates.append(
                            {
                                "id1": c1.id,
                                "id2": c2.id,
                                "name1": c1.canonical_name,
                                "name2": c2.canonical_name,
                                "label": c1.label,
                                "similarity": round(similarity, 3),
                                "is_auto_match": is_match,
                                "mentions1": c1.total_mentions or 0,
                                "mentions2": c2.total_mentions or 0,
                                "aliases1": self._parse_aliases(c1.aliases),
                                "aliases2": self._parse_aliases(c2.aliases),
                            }
                        )

            # Sort by similarity descending
            candidates.sort(key=lambda x: x["similarity"], reverse=True)

            return candidates[:limit]

        finally:
            session.close()

    def get_entity_details(self, canonical_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a canonical entity.

        Returns:
            Dict with entity details or None if not found
        """
        session = Session()
        try:
            canonical = session.query(CanonicalEntity).get(canonical_id)
            if not canonical:
                return None

            # Get all entity mentions
            mentions = (
                session.query(Entity)
                .filter(Entity.canonical_entity_id == canonical_id)
                .all()
            )

            # Get documents where this entity appears
            doc_ids = [m.doc_id for m in mentions]

            return {
                "id": canonical.id,
                "canonical_name": canonical.canonical_name,
                "label": canonical.label,
                "total_mentions": canonical.total_mentions or 0,
                "aliases": self._parse_aliases(canonical.aliases),
                "first_seen": canonical.first_seen.isoformat()
                if canonical.first_seen
                else None,
                "last_seen": canonical.last_seen.isoformat()
                if canonical.last_seen
                else None,
                "latitude": canonical.latitude,
                "longitude": canonical.longitude,
                "resolved_address": canonical.resolved_address,
                "mention_count": len(mentions),
                "document_count": len(set(doc_ids)),
                "mention_texts": list(set(m.text for m in mentions)),
            }

        finally:
            session.close()

    def merge_entities(
        self,
        keep_id: int,
        merge_id: int,
        user_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merge two canonical entities, keeping the first and deleting the second.

        Args:
            keep_id: ID of canonical entity to keep
            merge_id: ID of canonical entity to merge into keep_id
            user_note: Optional note about why the merge was performed

        Returns:
            Dict with merge results
        """
        session = Session()
        try:
            # Get both entities
            keep = session.query(CanonicalEntity).get(keep_id)
            merge = session.query(CanonicalEntity).get(merge_id)

            if not keep or not merge:
                return {
                    "success": False,
                    "error": "One or both entities not found",
                }

            # Prevent merging different types
            if keep.label != merge.label:
                return {
                    "success": False,
                    "error": f"Cannot merge different entity types: {keep.label} != {merge.label}",
                }

            # Capture affected IDs for unmerge support
            affected_entities = (
                session.query(Entity.id)
                .filter(Entity.canonical_entity_id == merge_id)
                .all()
            )
            affected_ids = [e.id for e in affected_entities]

            # Update all entity mentions
            entities_updated = (
                session.query(Entity)
                .filter(Entity.id.in_(affected_ids))
                .update({"canonical_entity_id": keep_id}, synchronize_session=False)
            )

            # Update entity relationships
            rel_updated_1 = (
                session.query(EntityRelationship)
                .filter(EntityRelationship.entity1_id == merge_id)
                .update({"entity1_id": keep_id})
            )

            rel_updated_2 = (
                session.query(EntityRelationship)
                .filter(EntityRelationship.entity2_id == merge_id)
                .update({"entity2_id": keep_id})
            )

            # Merge metadata
            keep.total_mentions = (keep.total_mentions or 0) + (
                merge.total_mentions or 0
            )
            keep.last_seen = max(
                keep.last_seen or datetime.min,
                merge.last_seen or datetime.min,
            )

            # Merge aliases
            keep_aliases = set(self._parse_aliases(keep.aliases))
            merge_aliases = set(self._parse_aliases(merge.aliases))

            # Add the merged entity's name as an alias
            keep_aliases.add(merge.canonical_name)
            keep_aliases.update(merge_aliases)

            # Remove the kept entity's name from aliases
            keep_aliases.discard(keep.canonical_name)

            keep.aliases = json.dumps(list(keep_aliases))

            # Update best name if needed
            all_names = [keep.canonical_name, merge.canonical_name]
            all_names.extend(keep_aliases)
            best_name = self.resolver.select_best_name(all_names)

            if best_name != keep.canonical_name:
                # Move old name to aliases
                keep_aliases.add(keep.canonical_name)
                keep_aliases.discard(best_name)
                keep.canonical_name = best_name
                keep.aliases = json.dumps(list(keep_aliases))

            # Merge geospatial data if needed
            if not keep.latitude and merge.latitude:
                keep.latitude = merge.latitude
                keep.longitude = merge.longitude
                keep.resolved_address = merge.resolved_address

            # Log merge to audit table
            audit = EntityMergeAudit(
                kept_canonical_id=keep_id,
                merged_canonical_id=merge_id,
                kept_name=keep.canonical_name,
                merged_name=merge.canonical_name,
                label=keep.label,
                entities_affected=entities_updated,
                relationships_affected=rel_updated_1 + rel_updated_2,
                merge_type="manual",
                user_note=user_note,
                similarity_score=self.resolver.similarity_score(
                    self.resolver.normalize_text(keep.canonical_name),
                    self.resolver.normalize_text(merge.canonical_name),
                ),
                affected_entity_ids=json.dumps(affected_ids)
            )
            session.add(audit)

            # Delete the merged entity
            session.delete(merge)

            # Commit changes
            session.commit()

            logger.info(
                f"Merged canonical entities: {keep_id} <- {merge_id} "
                f"('{keep.canonical_name}' <- '{merge.canonical_name}')"
            )

            return {
                "success": True,
                "kept_id": keep_id,
                "merged_id": merge_id,
                "final_name": keep.canonical_name,
                "entities_updated": entities_updated,
                "relationships_updated": rel_updated_1 + rel_updated_2,
                "aliases": list(keep_aliases),
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error merging entities {keep_id} <- {merge_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            session.close()

    def unmerge_last_merge(self) -> Dict[str, Any]:
        """
        Undo the last merge operation.
        Restores the merged entity and its relationships using audit log data.
        """
        session = Session()
        try:
            # Get last audit record
            audit = session.query(EntityMergeAudit).order_by(EntityMergeAudit.merged_at.desc()).first()
            if not audit:
                return {"success": False, "error": "No merge history found"}
            
            if not audit.affected_entity_ids:
                return {"success": False, "error": "Cannot unmerge: metadata missing (legacy merge)"}
                
            affected_ids = json.loads(audit.affected_entity_ids)
            
            # 1. Check if ID conflicts (rare but possible if sequence wrapped or manual insert)
            existing = session.query(CanonicalEntity).get(audit.merged_canonical_id)
            if existing:
                return {"success": False, "error": f"Cannot restore entity {audit.merged_canonical_id}: ID reused"}
                
            # 2. Restore canonical entity
            merged_entity = CanonicalEntity(
                id=audit.merged_canonical_id,
                canonical_name=audit.merged_name,
                label=audit.label,
                total_mentions=0, # Will populate below
                first_seen=datetime.utcnow(), 
                last_seen=datetime.utcnow()
            )
            session.add(merged_entity)
            
            # 3. Move entities back
            count = session.query(Entity).filter(Entity.id.in_(affected_ids)).update(
                {"canonical_entity_id": audit.merged_canonical_id},
                synchronize_session=False
            )
            
            # 4. Restore count
            merged_entity.total_mentions = count
            
            # 5. Update kept entity stats
            kept = session.query(CanonicalEntity).get(audit.kept_canonical_id)
            if kept:
                kept.total_mentions = max(0, (kept.total_mentions or 0) - count)
                # Cleanup aliases (best effort)
                try:
                    aliases = set(self._parse_aliases(kept.aliases))
                    aliases.discard(audit.merged_name)
                    kept.aliases = json.dumps(list(aliases))
                except:
                    pass

            # 6. Delete audit record
            session.delete(audit)
            session.commit()
            
            logger.info(f"Unmerged entity {audit.merged_canonical_id} from {audit.kept_canonical_id}")
            
            return {
                "success": True, 
                "restored_id": audit.merged_canonical_id,
                "restored_name": audit.merged_name,
                "entities_moved": count
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error unmerging: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def unlink_entity(self, entity_id: int) -> Dict[str, Any]:
        """
        Unlink an entity mention from its canonical entity.

        Args:
            entity_id: ID of entity mention to unlink

        Returns:
            Dict with success status
        """
        session = Session()
        try:
            entity = session.query(Entity).get(entity_id)
            if not entity:
                return {"success": False, "error": "Entity not found"}

            old_canonical_id = entity.canonical_entity_id

            # Unlink
            entity.canonical_entity_id = None

            # Update canonical entity stats
            if old_canonical_id:
                canonical = session.query(CanonicalEntity).get(old_canonical_id)
                if canonical:
                    canonical.total_mentions = max(
                        0, (canonical.total_mentions or 0) - entity.count
                    )

            session.commit()

            logger.info(
                f"Unlinked entity {entity_id} from canonical {old_canonical_id}"
            )

            return {
                "success": True,
                "entity_id": entity_id,
                "old_canonical_id": old_canonical_id,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error unlinking entity {entity_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def add_alias(self, canonical_id: int, alias: str) -> Dict[str, Any]:
        """
        Add a custom alias to a canonical entity.

        Args:
            canonical_id: ID of canonical entity
            alias: New alias to add

        Returns:
            Dict with success status
        """
        session = Session()
        try:
            canonical = session.query(CanonicalEntity).get(canonical_id)
            if not canonical:
                return {"success": False, "error": "Entity not found"}

            aliases = set(self._parse_aliases(canonical.aliases))
            aliases.add(alias.strip())
            aliases.discard(canonical.canonical_name)  # Don't include canonical name

            canonical.aliases = json.dumps(list(aliases))
            session.commit()

            logger.info(f"Added alias '{alias}' to canonical entity {canonical_id}")

            return {
                "success": True,
                "canonical_id": canonical_id,
                "aliases": list(aliases),
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding alias to entity {canonical_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get deduplication statistics.

        Returns:
            Dict with various stats
        """
        session = Session()
        try:
            # Total entities
            total_entities = session.query(Entity).count()
            linked_entities = (
                session.query(Entity)
                .filter(Entity.canonical_entity_id.isnot(None))
                .count()
            )
            unlinked_entities = total_entities - linked_entities

            # Canonical entities
            total_canonicals = session.query(CanonicalEntity).count()

            # By label
            canonical_by_label = {}
            for label, count in (
                session.query(CanonicalEntity.label, func.count(CanonicalEntity.id))
                .group_by(CanonicalEntity.label)
                .all()
            ):
                canonical_by_label[label] = count

            # Top entities by mentions
            top_entities = []
            for canonical in (
                session.query(CanonicalEntity)
                .order_by(CanonicalEntity.total_mentions.desc())
                .limit(10)
                .all()
            ):
                top_entities.append(
                    {
                        "id": canonical.id,
                        "name": canonical.canonical_name,
                        "label": canonical.label,
                        "mentions": canonical.total_mentions or 0,
                    }
                )

            return {
                "total_entities": total_entities,
                "linked_entities": linked_entities,
                "unlinked_entities": unlinked_entities,
                "total_canonicals": total_canonicals,
                "canonicals_by_label": canonical_by_label,
                "link_rate": round(linked_entities / total_entities * 100, 1)
                if total_entities > 0
                else 0,
                "top_entities": top_entities,
            }

        finally:
            session.close()

    def _parse_aliases(self, aliases_json: Optional[str]) -> List[str]:
        """Parse aliases JSON string into list."""
        if not aliases_json:
            return []
        try:
            return json.loads(aliases_json)
        except json.JSONDecodeError:
            return []


# Convenience functions for Reflex state classes
def get_duplicate_candidates(
    label_filter: Optional[str] = None,
    min_similarity: float = 0.75,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Get duplicate entity candidates."""
    service = EntityDeduplicationService()
    return service.get_duplicate_candidates(label_filter, min_similarity, limit)


def get_entity_details(canonical_id: int) -> Optional[Dict[str, Any]]:
    """Get entity details."""
    service = EntityDeduplicationService()
    return service.get_entity_details(canonical_id)


def merge_entities(
    keep_id: int, merge_id: int, user_note: Optional[str] = None
) -> Dict[str, Any]:
    """Merge two entities."""
    service = EntityDeduplicationService()
    return service.merge_entities(keep_id, merge_id, user_note)

def unmerge_last_merge() -> Dict[str, Any]:
    """Undo the last merge."""
    service = EntityDeduplicationService()
    return service.unmerge_last_merge()

def unlink_entity(entity_id: int) -> Dict[str, Any]:
    """Unlink an entity mention."""
    service = EntityDeduplicationService()
    return service.unlink_entity(entity_id)


def add_alias(canonical_id: int, alias: str) -> Dict[str, Any]:
    """Add an alias to an entity."""
    service = EntityDeduplicationService()
    return service.add_alias(canonical_id, alias)


def get_deduplication_stats() -> Dict[str, Any]:
    """Get deduplication statistics."""
    service = EntityDeduplicationService()
    return service.get_statistics()


def search_entities(
    query: str,
    label_filter: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Search canonical entities by name.

    Args:
        query: Search query (partial match)
        label_filter: Optional entity type filter
        limit: Max results

    Returns:
        List of matching entities with id, name, label, mentions
    """
    session = Session()
    try:
        q = session.query(CanonicalEntity)

        # Filter by name (case-insensitive partial match)
        if query:
            q = q.filter(CanonicalEntity.canonical_name.ilike(f"%{query}%"))

        # Filter by label
        if label_filter and label_filter != "all":
            q = q.filter(CanonicalEntity.label == label_filter)

        # Order by mentions (most mentioned first)
        q = q.order_by(CanonicalEntity.total_mentions.desc())

        results = []
        for entity in q.limit(limit).all():
            results.append(
                {
                    "id": entity.id,
                    "name": entity.canonical_name,
                    "label": entity.label,
                    "mentions": entity.total_mentions or 0,
                }
            )

        return results
    finally:
        session.close()


def delete_entity(canonical_id: int) -> Dict[str, Any]:
    """
    Delete a canonical entity and all its references.

    Used to clean up garbage entities (parsing errors, malformed data).

    Args:
        canonical_id: ID of canonical entity to delete

    Returns:
        Dict with success status and counts
    """
    session = Session()
    try:
        canonical = session.query(CanonicalEntity).get(canonical_id)
        if not canonical:
            return {"success": False, "error": "Entity not found"}

        name = canonical.canonical_name
        label = canonical.label

        # Count affected records
        entity_count = (
            session.query(Entity)
            .filter(Entity.canonical_entity_id == canonical_id)
            .count()
        )

        rel_count = (
            session.query(EntityRelationship)
            .filter(
                (EntityRelationship.entity1_id == canonical_id)
                | (EntityRelationship.entity2_id == canonical_id)
            )
            .count()
        )

        # Unlink all entity mentions (don't delete, just unlink)
        session.query(Entity).filter(Entity.canonical_entity_id == canonical_id).update(
            {"canonical_entity_id": None}
        )

        # Delete all relationships
        session.query(EntityRelationship).filter(
            (EntityRelationship.entity1_id == canonical_id)
            | (EntityRelationship.entity2_id == canonical_id)
        ).delete(synchronize_session=False)

        # Delete the canonical entity
        session.delete(canonical)
        session.commit()

        logger.info(f"Deleted canonical entity {canonical_id}: '{name}' ({label})")

        return {
            "success": True,
            "deleted_name": name,
            "deleted_label": label,
            "entities_unlinked": entity_count,
            "relationships_deleted": rel_count,
        }

    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting entity {canonical_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_all_labels() -> List[str]:
    """Get all unique entity labels."""
    session = Session()
    try:
        labels = session.query(CanonicalEntity.label).distinct().all()
        return [label[0] for label in labels if label[0]]
    finally:
        session.close()