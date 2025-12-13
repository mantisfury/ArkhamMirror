"""
Phase 5.3: Entity Cleanup Service

Provides filtering and cleanup for noisy entity extractions.
Uses regex patterns from entity_filter_rules table.
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from .db.models import EntityFilterRule, Entity, CanonicalEntity

load_dotenv()
logger = logging.getLogger(__name__)




class EntityCleanupService:
    """Service for cleaning up and filtering noisy entities."""

    def __init__(self):
        # Robust connection pool settings to prevent hanging
        self.engine = create_engine(
            DATABASE_URL,
            pool_size=3,
            max_overflow=2,
            pool_timeout=10,  # Wait max 10s for connection
            pool_recycle=300,  # Recycle connections after 5 min
            pool_pre_ping=True,  # Test connection before use
        )
        self.Session = sessionmaker(bind=self.engine)
        self._compiled_rules: List[Tuple[re.Pattern, str]] = []
        self._rules_loaded = False

    def load_filter_rules(self, force_reload: bool = False) -> int:
        """Load filter rules from database and compile regex patterns."""
        if self._rules_loaded and not force_reload:
            return len(self._compiled_rules)

        session = self.Session()
        try:
            rules = session.query(EntityFilterRule).all()
            self._compiled_rules = []

            for rule in rules:
                try:
                    if rule.is_regex:
                        pattern = re.compile(rule.pattern, re.IGNORECASE)
                    else:
                        # Exact match - escape and compile
                        pattern = re.compile(re.escape(rule.pattern), re.IGNORECASE)
                    self._compiled_rules.append(
                        (pattern, rule.description or rule.pattern)
                    )
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{rule.pattern}': {e}")

            self._rules_loaded = True
            logger.info(f"Loaded {len(self._compiled_rules)} entity filter rules")
            return len(self._compiled_rules)

        finally:
            session.close()

    def should_filter(self, entity_text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an entity should be filtered out.

        Args:
            entity_text: The entity text to check

        Returns:
            Tuple of (should_filter, reason)
        """
        if not self._rules_loaded:
            self.load_filter_rules()

        text = entity_text.strip()

        for pattern, description in self._compiled_rules:
            if pattern.fullmatch(text):
                return True, description

        return False, None

    def clean_entity_text(self, text: str) -> str:
        """
        Clean up entity text by removing common noise.

        Args:
            text: Raw entity text

        Returns:
            Cleaned entity text
        """
        # Strip whitespace and normalize
        cleaned = text.strip()

        # Remove leading/trailing punctuation (except apostrophes for names)
        cleaned = re.sub(r"^[^\w\']+|[^\w\']+$", "", cleaned)

        # Normalize internal whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Remove leading articles for better matching
        cleaned = re.sub(r"^(the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)

        return cleaned

    def filter_entities(
        self, entities: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter a list of entities, separating valid from filtered.

        Args:
            entities: List of entity dicts with 'text' and 'label' keys

        Returns:
            Tuple of (valid_entities, filtered_entities)
        """
        valid = []
        filtered = []

        for entity in entities:
            text = entity.get("text", "")
            should_filter, reason = self.should_filter(text)

            if should_filter:
                entity["filter_reason"] = reason
                filtered.append(entity)
            else:
                # Clean the text
                entity["text"] = self.clean_entity_text(text)
                # Only keep if text is not empty after cleaning
                if entity["text"]:
                    valid.append(entity)
                else:
                    entity["filter_reason"] = "Empty after cleaning"
                    filtered.append(entity)

        return valid, filtered

    def add_filter_rule(
        self,
        pattern: str,
        is_regex: bool = True,
        description: Optional[str] = None,
        created_by: str = "user",
    ) -> int:
        """Add a new filter rule to the database."""
        session = self.Session()
        try:
            # Validate regex if applicable
            if is_regex:
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern: {e}")

            rule = EntityFilterRule(
                pattern=pattern,
                is_regex=1 if is_regex else 0,
                created_by=created_by,
                description=description,
            )
            session.add(rule)
            session.commit()

            # Force reload rules
            self._rules_loaded = False

            return rule.id

        finally:
            session.close()

    def remove_filter_rule(self, rule_id: int) -> bool:
        """Remove a filter rule by ID."""
        session = self.Session()
        try:
            rule = (
                session.query(EntityFilterRule)
                .filter(EntityFilterRule.id == rule_id)
                .first()
            )
            if rule:
                session.delete(rule)
                session.commit()
                self._rules_loaded = False
                return True
            return False
        finally:
            session.close()

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all filter rules."""
        session = self.Session()
        try:
            rules = (
                session.query(EntityFilterRule)
                .order_by(EntityFilterRule.created_at)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "pattern": r.pattern,
                    "is_regex": bool(r.is_regex),
                    "created_by": r.created_by,
                    "description": r.description,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rules
            ]
        finally:
            session.close()

    def cleanup_existing_entities(
        self, dry_run: bool = True, batch_size: int = 100, max_entities: int = 1000
    ) -> Dict[str, Any]:
        """
        Apply filter rules to existing entities in the database.

        Args:
            dry_run: If True, only report what would be removed
            batch_size: Number of entities to process per batch
            max_entities: Maximum entities to scan (prevents runaway queries)

        Returns:
            Summary of cleanup results
        """
        session = self.Session()
        try:
            # Get total count first (fast)
            total_count = session.query(Entity).count()

            # Process in batches to avoid memory issues
            to_remove = []
            processed = 0
            offset = 0

            while processed < max_entities:
                batch = session.query(Entity).offset(offset).limit(batch_size).all()

                if not batch:
                    break

                for entity in batch:
                    should_filter, reason = self.should_filter(entity.text)
                    if should_filter:
                        to_remove.append(
                            {
                                "id": entity.id,
                                "text": entity.text[:100],  # Truncate for memory
                                "label": entity.label,
                                "reason": reason,
                            }
                        )

                processed += len(batch)
                offset += batch_size

            result = {
                "total_entities": total_count,
                "scanned": processed,
                "to_remove": len(to_remove),
                "examples": to_remove[:20],  # Show first 20
                "dry_run": dry_run,
            }

            if not dry_run and to_remove:
                ids_to_remove = [e["id"] for e in to_remove]
                session.query(Entity).filter(Entity.id.in_(ids_to_remove)).delete(
                    synchronize_session=False
                )
                session.commit()
                result["removed"] = len(ids_to_remove)

            return result

        finally:
            session.close()

    def cleanup_canonical_entities(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Apply filter rules to canonical entities.

        Args:
            dry_run: If True, only report what would be removed

        Returns:
            Summary of cleanup results
        """
        session = self.Session()
        try:
            entities = session.query(CanonicalEntity).all()

            to_remove = []
            for entity in entities:
                should_filter, reason = self.should_filter(entity.canonical_name)
                if should_filter:
                    to_remove.append(
                        {
                            "id": entity.id,
                            "canonical_name": entity.canonical_name,
                            "label": entity.label,
                            "total_mentions": entity.total_mentions,
                            "reason": reason,
                        }
                    )

            result = {
                "total_canonical": len(entities),
                "to_remove": len(to_remove),
                "examples": to_remove[:20],
                "dry_run": dry_run,
            }

            if not dry_run and to_remove:
                ids_to_remove = [e["id"] for e in to_remove]
                # First update entities to unlink
                session.query(Entity).filter(
                    Entity.canonical_entity_id.in_(ids_to_remove)
                ).update({"canonical_entity_id": None}, synchronize_session=False)
                # Then delete canonical entities
                session.query(CanonicalEntity).filter(
                    CanonicalEntity.id.in_(ids_to_remove)
                ).delete(synchronize_session=False)
                session.commit()
                result["removed"] = len(ids_to_remove)

            return result

        finally:
            session.close()


# Singleton instance
_cleanup_service: Optional[EntityCleanupService] = None


def get_cleanup_service() -> EntityCleanupService:
    """Get the singleton cleanup service instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = EntityCleanupService()
    return _cleanup_service


def filter_entity(text: str) -> Tuple[bool, Optional[str]]:
    """Convenience function to check if an entity should be filtered."""
    return get_cleanup_service().should_filter(text)


def clean_entity(text: str) -> str:
    """Convenience function to clean entity text."""
    return get_cleanup_service().clean_entity_text(text)
