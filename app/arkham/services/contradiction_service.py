import os
import json
import logging
from typing import List, Dict, Optional
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL, REDIS_URL

from app.arkham.services.db.models import (
    Contradiction,
    ContradictionEvidence,
    ContradictionBatch,
    Entity,
    Chunk,
    CanonicalEntity,
)
from app.arkham.services.llm_service import chat_with_llm, CONTRADICTIONS_SCHEMA
from app.arkham.utils.service_logging import logged_service_call

load_dotenv()

logger = logging.getLogger(__name__)


class ContradictionService:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    @logged_service_call()
    def detect_contradictions(
        self,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        Detect contradictions for specific entities within specific documents.

        Args:
            entity_ids: Optional list of canonical entity IDs to analyze.
                       If None, analyzes top 5 entities by mention count.
            doc_ids: Optional list of document IDs to search within.
                    If None, searches all documents where entities appear.
        """
        session = self.Session()
        try:
            if entity_ids:
                # Use specified entities
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(entity_ids))
                    .all()
                )
            else:
                # Top 5 entities by mention count
                entities = (
                    session.query(CanonicalEntity)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(5)
                    .all()
                )

            results = []
            for entity in entities:
                if not entity:
                    continue

                contradictions = self._analyze_entity_contradictions(
                    session, entity, doc_ids
                )
                results.extend(contradictions)

            return results
        finally:
            session.close()

    def get_selectable_entities(self, limit: int = 50) -> List[Dict]:
        """Get entities for the filter selector."""
        session = self.Session()
        try:
            entities = (
                session.query(CanonicalEntity)
                .order_by(desc(CanonicalEntity.total_mentions))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": e.id,
                    "name": e.canonical_name,
                    "label": e.label,
                    "mentions": e.total_mentions,
                }
                for e in entities
            ]
        finally:
            session.close()

    def get_selectable_documents(self, limit: int = 100) -> List[Dict]:
        """Get documents for the filter selector."""
        from app.arkham.services.db.models import Document
        from app.arkham.services.utils.security_utils import get_display_filename

        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": d.id,
                    "filename": get_display_filename(d),
                    "doc_type": d.doc_type or "unknown",
                }
                for d in documents
            ]
        finally:
            session.close()

    def _analyze_entity_contradictions(
        self,
        session,
        entity: CanonicalEntity,
        doc_ids_filter: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        Analyze text chunks related to an entity for contradictions.

        Args:
            session: DB session
            entity: The canonical entity to analyze
            doc_ids_filter: Optional list of document IDs to restrict search.
                           If None, searches all documents where entity appears.
        """
        # Get chunks where the entity is mentioned.
        # Entity table links to Document. We need chunks from those documents.
        # Better: Find Entity records for this CanonicalEntity, get doc_ids.

        entity_records = (
            session.query(Entity)
            .filter(Entity.canonical_entity_id == entity.id)
            .limit(20)
            .all()
        )
        entity_doc_ids = list(set(e.doc_id for e in entity_records))

        if not entity_doc_ids:
            return []

        # If doc_ids_filter provided, intersect with entity's doc_ids
        if doc_ids_filter:
            search_doc_ids = [d for d in entity_doc_ids if d in doc_ids_filter]
            if not search_doc_ids:
                # Entity doesn't appear in the filtered documents
                return []
        else:
            search_doc_ids = entity_doc_ids

        # Get chunks from these documents.
        # Limit to 10 chunks to avoid context overflow with 18k token model
        chunks = (
            session.query(Chunk)
            .filter(Chunk.doc_id.in_(search_doc_ids))
            .limit(10)
            .all()
        )

        if len(chunks) < 2:
            return []

        # Prepare prompt - use shorter excerpts to fit within context window
        # 18k token model ~ 72k chars, but we need room for response
        chunk_texts = [f"[Chunk {c.id}]: {c.text[:300]}" for c in chunks]
        combined_text = "\n\n".join(chunk_texts)

        prompt = f"""You are an investigative analyst. Analyze the following text excerpts related to the entity '{entity.canonical_name}'. 
Identify any factual contradictions or conflicting statements. Focus on:
- Conflicting dates for the same event
- Conflicting locations for the same person at the same time
- Conflicting roles or titles
- Mutually exclusive actions
- Cross-entity conflicts (e.g., Person A says X but Person B says Y about the same event)

Return a JSON object with key 'contradictions' containing a list. Each item MUST have:
- 'claim_a': The first conflicting statement (quote or paraphrase from text)
- 'source_a': Where claim_a is from (e.g. "Chunk 123")
- 'claim_b': The second conflicting statement
- 'source_b': Where claim_b is from
- 'severity': 'High', 'Medium', or 'Low'
- 'explanation': Why these claims conflict
- 'category': One of: 'timeline', 'financial', 'factual', 'identity', 'attribution', 'location'
- 'confidence': A number 0.0-1.0 indicating how confident you are this is a real contradiction
- 'involved_entities': A list of ALL entity names (people, organizations) involved in this contradiction. Include everyone who made or is subject to conflicting claims.

Example format:
{{"contradictions": [{{"claim_a": "John said he was in NYC on Jan 5", "source_a": "Chunk 42", "claim_b": "Sarah said John was in LA on Jan 5", "source_b": "Chunk 78", "severity": "High", "explanation": "John's location on Jan 5 is disputed", "category": "location", "confidence": 0.95, "involved_entities": ["John", "Sarah"]}}]}}

Text Excerpts:
{combined_text}

If no contradictions found, return {{"contradictions": []}}."""

        # Log prompt size for debugging
        logger.info(
            f"Contradiction prompt for {entity.canonical_name}: {len(prompt)} chars, {len(chunks)} chunks"
        )

        # Call LLM with higher max_tokens to prevent output truncation
        try:
            response = chat_with_llm(
                [{"role": "user", "content": prompt}],
                max_tokens=3000,  # Increased to prevent truncation
                json_schema=CONTRADICTIONS_SCHEMA,
            )

            # Clean response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            response = response.strip()
            if not response:
                return []

            # Try to fix common JSON issues from LLM
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # Try to repair: ensure proper closing
                if response.count('"') % 2 != 0:
                    # Odd number of quotes - try adding one
                    response = response + '"'
                if not response.rstrip().endswith("}"):
                    response = (
                        response + "]}"
                        if '"contradictions"' in response
                        else response + "}"
                    )
                try:
                    data = json.loads(response)
                except json.JSONDecodeError:
                    # Last resort: return empty
                    logger.warning(
                        f"Could not parse LLM JSON for {entity.canonical_name}, skipping"
                    )
                    return []

            contradictions_data = data.get("contradictions", [])
            logger.info(
                f"LLM returned {len(contradictions_data)} contradictions for {entity.canonical_name}"
            )

            saved_contradictions = []
            for item in contradictions_data:
                # Schema uses claim_a, claim_b, explanation - build description from these
                claim_a = item.get("claim_a", "").strip()
                claim_b = item.get("claim_b", "").strip()
                explanation = item.get("explanation", "").strip()
                source_a = item.get("source_a", "")
                source_b = item.get("source_b", "")
                severity = item.get("severity", "Medium")
                # Phase 3: Extract category and confidence
                category = item.get("category", "factual")  # Default to factual
                llm_confidence = item.get("confidence", 0.8)  # Default confidence
                if isinstance(llm_confidence, str):
                    try:
                        llm_confidence = float(llm_confidence)
                    except ValueError:
                        llm_confidence = 0.8

                # NEW: Extract involved_entities and map to IDs
                involved_entity_names = item.get("involved_entities", [])
                involved_entity_ids = []
                if involved_entity_names:
                    # Look up canonical entity IDs for each name
                    for name in involved_entity_names:
                        if not isinstance(name, str):
                            continue
                        # Try exact match first
                        ce = (
                            session.query(CanonicalEntity)
                            .filter(CanonicalEntity.canonical_name.ilike(name))
                            .first()
                        )
                        if ce:
                            involved_entity_ids.append(ce.id)
                        else:
                            # Try partial match
                            ce = (
                                session.query(CanonicalEntity)
                                .filter(
                                    CanonicalEntity.canonical_name.ilike(f"%{name}%")
                                )
                                .first()
                            )
                            if ce:
                                involved_entity_ids.append(ce.id)

                # Always include the primary entity
                if entity.id not in involved_entity_ids:
                    involved_entity_ids.append(entity.id)

                logger.info(
                    f"  Contradiction: claim_a='{claim_a[:30]}...' claim_b='{claim_b[:30]}...' severity={severity} category={category} involved={len(involved_entity_ids)} entities"
                )

                # Skip if no actual claims
                if not claim_a or not claim_b:
                    logger.warning(
                        f"Skipping contradiction with missing claims for {entity.canonical_name}"
                    )
                    continue

                # Build description from the claims and explanation
                description = f"{claim_a} vs {claim_b}"
                if explanation:
                    description += f" - {explanation}"

                # Save to DB with Phase 3 fields and involved_entity_ids
                contradiction = Contradiction(
                    entity_id=entity.id,
                    description=description,
                    severity=severity,
                    confidence=llm_confidence,
                    status="Open",
                    category=category,  # Phase 3
                    detection_method="llm",  # Phase 3
                    involved_entity_ids=json.dumps(involved_entity_ids)
                    if involved_entity_ids
                    else None,
                )
                session.add(contradiction)
                session.flush()  # Get ID

                # Find chunks that contain the claims (fuzzy match)
                # This is more reliable than relying on LLM-provided chunk IDs
                evidence_added = False
                for claim_text, source_label in [
                    (claim_a, source_a),
                    (claim_b, source_b),
                ]:
                    if not claim_text:
                        continue

                    # Try to find a chunk containing part of this claim
                    claim_snippet = claim_text[
                        :50
                    ].lower()  # Use first 50 chars for matching
                    matched_chunk = None
                    for chunk in chunks:
                        if claim_snippet in chunk.text.lower():
                            matched_chunk = chunk
                            break

                    if matched_chunk:
                        evidence = ContradictionEvidence(
                            contradiction_id=contradiction.id,
                            document_id=matched_chunk.doc_id,
                            chunk_id=matched_chunk.id,
                            text_chunk=claim_text,  # Store the specific claim
                            page_number=0,
                        )
                        session.add(evidence)
                        evidence_added = True

                # If no chunk match, still save the claims as evidence
                if not evidence_added and (claim_a or claim_b):
                    # Use first chunk's doc_id as fallback
                    fallback_doc_id = chunks[0].doc_id if chunks else None
                    if fallback_doc_id:
                        evidence = ContradictionEvidence(
                            contradiction_id=contradiction.id,
                            document_id=fallback_doc_id,
                            chunk_id=None,
                            text_chunk=f"Claim A: {claim_a}\n\nClaim B: {claim_b}",
                            page_number=0,
                        )
                        session.add(evidence)

                saved_contradictions.append(
                    {
                        "id": contradiction.id,
                        "description": contradiction.description,
                        "severity": contradiction.severity,
                    }
                )

            session.commit()
            return saved_contradictions

        except Exception as e:
            logger.error(
                f"Error detecting contradictions for {entity.canonical_name}: {e}"
            )
            session.rollback()
            return []

    def get_contradictions(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """
        Fetch existing contradictions with their evidence.
        """
        session = self.Session()
        try:
            contradictions = (
                session.query(Contradiction)
                .order_by(desc(Contradiction.created_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

            results = []
            for c in contradictions:
                evidence = (
                    session.query(ContradictionEvidence)
                    .filter(ContradictionEvidence.contradiction_id == c.id)
                    .all()
                )
                entity = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id == c.entity_id)
                    .first()
                )

                results.append(
                    {
                        "id": c.id,
                        "entity_name": entity.canonical_name if entity else "Unknown",
                        "description": c.description,
                        "severity": c.severity,
                        "status": c.status,
                        "confidence": c.confidence,
                        "created_at": c.created_at.isoformat()
                        if c.created_at
                        else None,
                        "evidence": [
                            {"text": e.text_chunk, "document_id": e.document_id}
                            for e in evidence
                        ],
                        # Phase 3 fields
                        "category": c.category or "factual",
                        "tags": c.tags or [],
                        "chain_id": c.chain_id,
                        "chain_position": c.chain_position,
                        "detection_method": c.detection_method or "llm",
                        "user_notes": c.user_notes,
                    }
                )

            return results
        finally:
            session.close()

    def semantic_search_contradictions(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search contradictions by semantic similarity using Qdrant embeddings.

        Phase 4: Uses the embedded descriptions to find semantically similar contradictions.
        """
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer
        from config.settings import QDRANT_URL

        try:
            # Get embedding for query
            model = SentenceTransformer("BAAI/bge-m3")
            query_embedding = model.encode(query).tolist()

            # Search in Qdrant - contradictions collection
            qdrant_client = QdrantClient(url=QDRANT_URL)

            # First, try to create a collection for contradictions if it doesn't exist
            collections = [c.name for c in qdrant_client.get_collections().collections]

            if "contradictions" not in collections:
                # Build the collection from existing contradictions
                self._build_contradiction_embeddings(qdrant_client, model)

            # Search
            results = qdrant_client.search(
                collection_name="contradictions",
                query_vector=query_embedding,
                limit=limit,
            )

            # Get contradiction IDs from results
            contradiction_ids = [int(r.id) for r in results]

            if not contradiction_ids:
                return []

            # Fetch full contradiction data
            session = self.Session()
            try:
                contradictions = (
                    session.query(Contradiction)
                    .filter(Contradiction.id.in_(contradiction_ids))
                    .all()
                )

                # Order by search result order
                id_to_score = {int(r.id): r.score for r in results}
                id_to_contradiction = {c.id: c for c in contradictions}

                results_list = []
                for cid in contradiction_ids:
                    c = id_to_contradiction.get(cid)
                    if c:
                        evidence = (
                            session.query(ContradictionEvidence)
                            .filter(ContradictionEvidence.contradiction_id == c.id)
                            .all()
                        )
                        entity = (
                            session.query(CanonicalEntity)
                            .filter(CanonicalEntity.id == c.entity_id)
                            .first()
                        )

                        results_list.append(
                            {
                                "id": c.id,
                                "entity_name": entity.canonical_name
                                if entity
                                else "Unknown",
                                "description": c.description,
                                "severity": c.severity,
                                "status": c.status,
                                "confidence": c.confidence,
                                "created_at": c.created_at.isoformat()
                                if c.created_at
                                else None,
                                "category": c.category or "factual",
                                "evidence": [
                                    {"text": e.text_chunk, "document_id": e.document_id}
                                    for e in evidence
                                ],
                                "search_score": id_to_score.get(cid, 0.0),
                            }
                        )

                return results_list
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    def _build_contradiction_embeddings(self, qdrant_client, model):
        """Build Qdrant collection for contradiction embeddings."""
        from qdrant_client.models import VectorParams, Distance, PointStruct

        logger.info("Building contradiction embeddings collection...")

        session = self.Session()
        try:
            contradictions = session.query(Contradiction).all()

            if not contradictions:
                return

            # Create collection
            qdrant_client.create_collection(
                collection_name="contradictions",
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
            )

            # Embed and upsert
            points = []
            for c in contradictions:
                embedding = model.encode(c.description).tolist()
                points.append(
                    PointStruct(
                        id=c.id,
                        vector=embedding,
                        payload={
                            "severity": c.severity,
                            "status": c.status,
                            "category": c.category or "factual",
                        },
                    )
                )

            # Batch upsert
            qdrant_client.upsert(
                collection_name="contradictions",
                points=points,
            )

            logger.info(f"Built embeddings for {len(points)} contradictions")

        finally:
            session.close()

    def resolve_contradiction(self, contradiction_id: int, status: str, note: str = ""):
        """
        Update status of a contradiction.
        """
        session = self.Session()
        try:
            c = (
                session.query(Contradiction)
                .filter(Contradiction.id == contradiction_id)
                .first()
            )
            if c:
                c.status = status
                c.resolution_note = note
                session.commit()
                return True
            return False
        finally:
            session.close()

    def clear_all_contradictions(self) -> int:
        """
        Delete all contradictions and their evidence from the database.
        Returns the number of contradictions deleted.
        """
        session = self.Session()
        try:
            # First delete evidence (foreign key constraint)
            evidence_count = session.query(ContradictionEvidence).delete()
            logger.info(f"Deleted {evidence_count} contradiction evidence records")

            # Then delete contradictions
            contradiction_count = session.query(Contradiction).delete()
            logger.info(f"Deleted {contradiction_count} contradictions")

            # Also clear analysis cache so meaningful detection happens next time
            from app.arkham.services.db.models import EntityAnalysisCache

            cache_count = session.query(EntityAnalysisCache).delete()
            logger.info(f"Deleted {cache_count} entity analysis cache records")

            session.commit()
            return contradiction_count
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to clear contradictions: {e}")
            return 0
        finally:
            session.close()

    # ==================== Background Job Methods ====================

    def queue_detection_job(
        self,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
        detect_all: bool = False,
        force_refresh: bool = False,
    ) -> str:
        """
        Queue a background contradiction detection job.

        Args:
            entity_ids: Specific entities to analyze (optional)
            doc_ids: Document filter (optional)
            detect_all: If True, analyze all entities (overrides entity_ids)
            force_refresh: If True, bypass cache and re-analyze all

        Returns:
            job_id for tracking progress
        """
        import uuid
        from redis import Redis
        from rq import Queue

        redis_conn = Redis.from_url(REDIS_URL)
        # Use 'default' queue to work with existing worker infrastructure
        # Alternatively, start worker with: python run_rq_worker.py contradictions
        q = Queue("default", connection=redis_conn)

        job_id = str(uuid.uuid4())[:8]

        if detect_all:
            from app.arkham.services.workers.contradiction_worker import (
                detect_all as detect_all_job,
            )

            q.enqueue(
                detect_all_job,
                job_id,  # Pass as positional arg
                job_timeout="4h",
                job_id=f"contradiction-{job_id}",  # RQ job ID
            )
        else:
            # If no entities specified, get top entities by connection count
            if not entity_ids:
                entities = self.get_selectable_entities(limit=50)
                from app.arkham.services.workers.contradiction_worker import (
                    detect_batch,
                )

            q.enqueue(
                detect_batch,
                entity_ids,
                doc_ids,
                job_id,  # Our tracking ID
                force_refresh,  # Phase 2: bypass cache
                job_timeout="4h",
                job_id=f"contradiction-{job_id}",  # RQ job ID
            )

        logger.info(
            f"Queued contradiction detection job: {job_id} (force_refresh={force_refresh})"
        )
        return job_id

    def get_job_status(self, job_id: str) -> Dict:
        """
        Get the status of a background detection job.

        Returns:
            Dict with status, processed, total, found, current_entity, error
        """
        from redis import Redis

        redis_conn = Redis.from_url(REDIS_URL)
        data = redis_conn.hgetall(f"contradiction_job:{job_id}")

        if not data:
            # Job hasn't started writing yet - return queued status instead of error
            return {"status": "queued", "total": 0, "processed": 0, "found": 0}

        # Decode bytes to strings
        return {
            k.decode(): v.decode() if isinstance(v, bytes) else v
            for k, v in data.items()
        }

    def pause_job(self, job_id: str):
        """Pause a running detection job."""
        from redis import Redis

        redis_conn = Redis.from_url(REDIS_URL)
        redis_conn.set(f"contradiction_job:{job_id}:control", "pause")
        redis_conn.expire(f"contradiction_job:{job_id}:control", 3600)
        logger.info(f"Paused job {job_id}")

    def resume_job(self, job_id: str):
        """Resume a paused detection job."""
        from redis import Redis

        redis_conn = Redis.from_url(REDIS_URL)
        redis_conn.set(f"contradiction_job:{job_id}:control", "run")
        redis_conn.expire(f"contradiction_job:{job_id}:control", 3600)
        logger.info(f"Resumed job {job_id}")

    def stop_job(self, job_id: str):
        """Stop a running detection job."""
        from redis import Redis

        redis_conn = Redis.from_url(REDIS_URL)
        redis_conn.set(f"contradiction_job:{job_id}:control", "stop")
        redis_conn.expire(f"contradiction_job:{job_id}:control", 3600)
        logger.info(f"Stopped job {job_id}")

    # ========== Batch Management Methods ==========

    def get_batch_overview(
        self,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
        batch_size: int = 50,
    ) -> Dict:
        """
        Get status of all batches for the current entity set.
        Creates batch records if they don't exist.
        """
        session = self.Session()
        try:
            # Get total entity count
            total_entities = self._count_entities(session, entity_ids, doc_ids)

            # Calculate batches - can be 0 if no entities
            if total_entities == 0:
                total_batches = 0
            else:
                total_batches = (total_entities + batch_size - 1) // batch_size

            # Ensure batch records exist (or are cleared if 0)
            self._ensure_batch_records(
                session, total_batches, batch_size, total_entities
            )

            # Get batch statuses
            batches = (
                session.query(ContradictionBatch)
                .order_by(ContradictionBatch.batch_number)
                .all()
            )

            batch_list = []
            for b in batches:
                batch_list.append(
                    {
                        "batch_number": b.batch_number,
                        "status": b.status,
                        "entity_offset": b.entity_offset,
                        "entity_count": b.entity_count,
                        "contradictions_found": b.contradictions_found,
                        "job_id": b.job_id,
                        "started_at": b.started_at.isoformat()
                        if b.started_at
                        else None,
                        "completed_at": b.completed_at.isoformat()
                        if b.completed_at
                        else None,
                        "error": b.error,
                    }
                )

            # Find next pending batch
            next_pending = next(
                (b for b in batch_list if b["status"] == "pending"), None
            )
            completed = sum(1 for b in batch_list if b["status"] == "complete")

            return {
                "total_entities": total_entities,
                "batch_size": batch_size,
                "total_batches": len(batches),
                "completed_batches": completed,
                "batches": batch_list,
                "next_pending": next_pending,
                "all_complete": completed == len(batches),
            }
        finally:
            session.close()

    def _count_entities(
        self,
        session,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
    ) -> int:
        """Count entities to be analyzed."""
        from sqlalchemy import func

        query = session.query(func.count(CanonicalEntity.id))

        if entity_ids:
            query = query.filter(CanonicalEntity.id.in_(entity_ids))

        if doc_ids:
            # Get entities that appear in specified docs
            entity_ids_in_docs = (
                session.query(Entity.canonical_entity_id)
                .filter(Entity.doc_id.in_(doc_ids))
                .distinct()
            )
            query = query.filter(CanonicalEntity.id.in_(entity_ids_in_docs))

        return query.scalar() or 0

    def _ensure_batch_records(
        self,
        session,
        total_batches: int,
        batch_size: int,
        total_entities: int,
    ):
        """Create batch records if they don't exist."""
        existing = session.query(ContradictionBatch).count()

        if existing != total_batches:
            # Clear and recreate
            session.query(ContradictionBatch).delete()

            for i in range(total_batches):
                offset = i * batch_size
                count = min(batch_size, total_entities - offset)
                batch = ContradictionBatch(
                    batch_number=i + 1,
                    status="pending",
                    entity_offset=offset,
                    entity_count=count,
                )
                session.add(batch)

            session.commit()

    def start_batch(
        self,
        batch_number: int,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        auto_continue: bool = False,
    ) -> Optional[str]:
        """
        Start a specific batch by number.
        Returns job_id or None if batch doesn't exist.
        """
        from datetime import datetime
        from redis import Redis
        from rq import Queue

        session = self.Session()
        try:
            batch = (
                session.query(ContradictionBatch)
                .filter(ContradictionBatch.batch_number == batch_number)
                .first()
            )

            if not batch:
                logger.warning(f"Batch {batch_number} not found")
                return None

            # Get entity IDs for this batch
            offset = batch.entity_offset
            count = batch.entity_count

            query = (
                session.query(CanonicalEntity.id)
                .order_by(CanonicalEntity.id)
                .offset(offset)
                .limit(count)
            )

            if entity_ids:
                query = query.filter(CanonicalEntity.id.in_(entity_ids))

            if doc_ids:
                entity_ids_in_docs = (
                    session.query(Entity.canonical_entity_id)
                    .filter(Entity.doc_id.in_(doc_ids))
                    .distinct()
                )
                query = query.filter(CanonicalEntity.id.in_(entity_ids_in_docs))

            batch_entity_ids = [e[0] for e in query.all()]

            if not batch_entity_ids:
                logger.warning(f"No entities found for batch {batch_number}")
                batch.status = "complete"
                batch.completed_at = datetime.utcnow()
                session.commit()
                return None

            # Queue the job
            import uuid

            job_id = str(uuid.uuid4())[:8]

            redis_conn = Redis.from_url(REDIS_URL)
            q = Queue("default", connection=redis_conn)

            from app.arkham.services.workers.contradiction_worker import detect_batch

            _job = q.enqueue(
                detect_batch,
                args=[batch_entity_ids, doc_ids, job_id, force_refresh],
                kwargs={
                    "batch_number": batch_number,
                    "auto_continue": auto_continue,
                },
                job_id=f"contradiction-batch-{job_id}",
                job_timeout="4h",
            )

            # Update batch record
            batch.status = "running"
            batch.job_id = job_id
            batch.started_at = datetime.utcnow()
            batch.error = None
            session.commit()

            logger.info(f"Started batch {batch_number} with job {job_id}")
            return job_id

        finally:
            session.close()

    def start_next_batch(
        self,
        entity_ids: Optional[List[int]] = None,
        doc_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        auto_continue: bool = False,
    ) -> Optional[str]:
        """Start the next pending batch."""
        overview = self.get_batch_overview(entity_ids, doc_ids)
        next_batch = overview.get("next_pending")

        if next_batch:
            return self.start_batch(
                next_batch["batch_number"],
                entity_ids,
                doc_ids,
                force_refresh,
                auto_continue,
            )

        logger.info("No pending batches - all complete")
        return None

    def reset_batches(self):
        """Reset all batch records to pending state."""
        session = self.Session()
        try:
            session.query(ContradictionBatch).update(
                {
                    ContradictionBatch.status: "pending",
                    ContradictionBatch.started_at: None,
                    ContradictionBatch.completed_at: None,
                    ContradictionBatch.job_id: None,
                    ContradictionBatch.contradictions_found: 0,
                    ContradictionBatch.error: None,
                }
            )
            session.commit()
            logger.info("Reset all batches to pending")
        finally:
            session.close()


# Singleton instance
_service_instance = None


def get_contradiction_service() -> ContradictionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ContradictionService()
    return _service_instance
