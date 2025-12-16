from config.settings import DATABASE_URL, REDIS_URL, QDRANT_URL
import os
import json
import logging
import spacy
from datetime import datetime
from itertools import combinations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from redis import Redis
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

from app.arkham.services.db.models import (
    Chunk,
    Anomaly,
    Document,
    Entity,
    CanonicalEntity,
    EntityRelationship,
    AnomalyKeyword,
)
from app.arkham.services.embedding_services import embed_hybrid
from app.arkham.services.entity_resolution import EntityResolver

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB & Redis
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(REDIS_URL)

# Qdrant
qdrant_client = QdrantClient(url=QDRANT_URL)
COLLECTION_NAME = "arkham_mirror_hybrid"

# Spacy Model (Lazy Load)
_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            logger.info("Loading Spacy model...")
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading Spacy model 'en_core_web_sm'...")
            from spacy.cli import download

            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


def ensure_collection():
    try:
        qdrant_client.get_collection(COLLECTION_NAME)
    except Exception:
        logger.info(f"Creating collection {COLLECTION_NAME}...")
        from qdrant_client.http import models

        try:
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "dense": models.VectorParams(
                        size=1024, distance=models.Distance.COSINE
                    ),
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(),
                },
            )
        except Exception as e:
            # If it fails, check if it's because it already exists (race condition)
            if "already exists" in str(e) or "409" in str(e):
                logger.info(
                    f"Collection {COLLECTION_NAME} already exists (race condition handled)."
                )
            else:
                raise e


ensure_collection()


def embed_chunk_job(chunk_id):
    """
    Embeds a chunk, upserts to Qdrant, runs Red Flag analysis, and extracts Entities.
    """
    session = Session()
    try:
        chunk = session.query(Chunk).get(chunk_id)
        if not chunk:
            logger.error(f"Chunk {chunk_id} not found.")
            return

        # 1. Generate Embedding
        emb_result = embed_hybrid(chunk.text)

        # 2. Upsert to Qdrant
        # Need to fetch Document to get metadata
        doc = session.query(Document).get(chunk.doc_id)

        point = PointStruct(
            id=chunk.id,
            vector={
                "dense": emb_result["dense"],
                "sparse": {
                    "indices": list(map(int, emb_result["sparse"].keys())),
                    "values": list(map(float, emb_result["sparse"].values())),
                },
            },
            payload={
                "doc_id": doc.id,
                "text": chunk.text,
                "doc_type": doc.doc_type,
                "project_id": doc.project_id,
                "chunk_index": chunk.chunk_index,
            },
        )

        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=[point])

        # 3. Red Flag / Anomaly Analysis (Streaming)
        # Fetch keywords from DB
        db_keywords = session.query(AnomalyKeyword).filter_by(is_active=1).all()
        if db_keywords:
            suspicious_keywords = {k.keyword: k.weight for k in db_keywords}
        else:
            # Fallback defaults
            suspicious_keywords = {
                "confidential": 0.2,
                "secret": 0.2,
                "delete": 0.2,
                "shred": 0.2,
                "hidden": 0.2,
            }

        score = 0
        reasons = []

        for kw, weight in suspicious_keywords.items():
            if kw in chunk.text.lower():
                score += weight
                reasons.append(kw)

        if score > 0:
            anomaly = Anomaly(
                chunk_id=chunk.id,
                score=score,
                reason=f"Keywords found: {', '.join(reasons)}",
            )
            session.add(anomaly)
            session.commit()
            logger.info(f"Flagged chunk {chunk.id} (Score: {score})")

        # 4. Entity Extraction (NER)
        try:
            nlp = get_nlp()
            spacy_doc = nlp(chunk.text)

            # Aggregate locally to reduce DB hits
            local_counts = {}

            # Noise Blocklist (Common OCR artifacts or irrelevant terms)
            BLOCKLIST = {
                "page",
                "total",
                "date",
                "invoice",
                "subtotal",
                "amount",
                "description",
                "item",
                "qty",
                "price",
                "tel",
                "fax",
                "email",
                "www",
                "http",
                "https",
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            }

            for ent in spacy_doc.ents:
                # 1. Filter by Label
                if ent.label_ in [
                    "CARDINAL",
                    "ORDINAL",
                    "PERCENT",
                    "QUANTITY",
                    "MONEY",
                    "TIME",
                ]:
                    continue

                # 2. Filter by Length (Noise reduction)
                clean_text = ent.text.strip()
                if len(clean_text) < 3:
                    continue

                # 3. Filter by Blocklist
                if clean_text.lower() in BLOCKLIST:
                    continue

                # 4. Filter specific patterns (e.g. just numbers)
                if clean_text.isdigit():
                    continue

                key = (clean_text, ent.label_)
                local_counts[key] = local_counts.get(key, 0) + 1

            # Entity Resolution: Link to canonical entities
            resolver = EntityResolver()

            for (text, label), count in local_counts.items():
                # 1. Check if entity mention already exists for this document
                entity = (
                    session.query(Entity)
                    .filter_by(doc_id=doc.id, text=text, label=label)
                    .first()
                )

                if entity:
                    entity.count += count
                else:
                    entity = Entity(doc_id=doc.id, text=text, label=label, count=count)
                    session.add(entity)
                    session.flush()  # Get entity ID

                # 2. Find or create canonical entity
                if not entity.canonical_entity_id:
                    # Fetch existing canonical entities of same label
                    existing_canonicals = (
                        session.query(CanonicalEntity).filter_by(label=label).all()
                    )

                    canonical_dicts = [
                        {
                            "id": c.id,
                            "canonical_name": c.canonical_name,
                            "aliases": c.aliases,
                        }
                        for c in existing_canonicals
                    ]

                    # Try to match with existing canonical
                    canonical_id = resolver.find_canonical_match(
                        text, label, canonical_dicts
                    )

                    if canonical_id:
                        # Link to existing canonical
                        canonical = session.query(CanonicalEntity).get(canonical_id)
                        entity.canonical_entity_id = canonical_id

                        # Update canonical stats
                        canonical.total_mentions += count
                        canonical.last_seen = datetime.utcnow()

                        # Update aliases
                        canonical.aliases = resolver.merge_aliases(
                            canonical.aliases or "", text
                        )

                        # Check if this new mention is a better canonical name
                        try:
                            current_aliases = json.loads(canonical.aliases)
                            all_names = [canonical.canonical_name] + current_aliases
                            best_name = resolver.select_best_name(all_names)

                            if best_name != canonical.canonical_name:
                                logger.info(
                                    f"Updating canonical name: {canonical.canonical_name} -> {best_name}"
                                )
                                canonical.canonical_name = best_name
                        except Exception as e:
                            logger.warning(f"Failed to update canonical name: {e}")

                    else:
                        # Create new canonical entity
                        canonical = CanonicalEntity(
                            canonical_name=text,
                            label=label,
                            total_mentions=count,
                            aliases=json.dumps(
                                [EntityResolver.sanitize_for_json(text)]
                            ),
                        )
                        session.add(canonical)
                        session.flush()
                        entity.canonical_entity_id = canonical.id

            # Collect all canonical entity IDs from this chunk for relationship creation
            chunk_canonical_ids = set()
            for (text, label), count in local_counts.items():
                entity = (
                    session.query(Entity)
                    .filter_by(doc_id=doc.id, text=text, label=label)
                    .first()
                )
                if entity and entity.canonical_entity_id:
                    chunk_canonical_ids.add(entity.canonical_entity_id)

            # Create co-occurrence relationships for entities in the same chunk
            if len(chunk_canonical_ids) >= 2:
                for entity1_id, entity2_id in combinations(
                    sorted(chunk_canonical_ids), 2
                ):
                    # Check if relationship already exists (in either direction)
                    existing = (
                        session.query(EntityRelationship)
                        .filter(
                            (
                                (EntityRelationship.entity1_id == entity1_id)
                                & (EntityRelationship.entity2_id == entity2_id)
                            )
                            | (
                                (EntityRelationship.entity1_id == entity2_id)
                                & (EntityRelationship.entity2_id == entity1_id)
                            )
                        )
                        .first()
                    )

                    if existing:
                        # Update existing relationship
                        existing.co_occurrence_count += 1
                        existing.strength = min(
                            existing.strength + 0.1, 10.0
                        )  # Capped at 10
                    else:
                        # Create new relationship
                        new_rel = EntityRelationship(
                            entity1_id=entity1_id,
                            entity2_id=entity2_id,
                            relationship_type="co-occurrence",
                            strength=1.0,
                            co_occurrence_count=1,
                            doc_id=doc.id,
                        )
                        session.add(new_rel)

                logger.info(
                    f"Created/updated {len(list(combinations(chunk_canonical_ids, 2)))} relationships from chunk {chunk.id}"
                )

            session.commit()
            logger.info(
                f"Extracted and linked {len(local_counts)} entities from chunk {chunk.id}"
            )

        except Exception as ner_e:
            logger.error(f"NER failed for chunk {chunk.id}: {ner_e}")

        logger.info(f"Embedded chunk {chunk.id}")

        # Check if all chunks for this document are processed
        # This is a bit expensive, but ensures status correctness
        total_chunks = session.query(Chunk).filter(Chunk.doc_id == doc.id).count()

        # Check if all MiniDocs for this doc are 'parsed'
        from arkham.services.db.models import MiniDoc

        pending_minidocs = (
            session.query(MiniDoc)
            .filter(MiniDoc.document_id == doc.id, MiniDoc.status != "parsed")
            .count()
        )

        if pending_minidocs == 0:
            if doc.status != "complete":
                doc.status = "complete"
                session.add(doc)
                session.commit()
                logger.info(f"Document {doc.id} marked as COMPLETE.")

    except Exception as e:
        logger.error(f"Embed job failed: {e}")
        session.rollback()
    finally:
        session.close()
