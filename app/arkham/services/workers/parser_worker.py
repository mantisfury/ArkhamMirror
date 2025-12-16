from config.settings import DATABASE_URL, REDIS_URL
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rq import Queue
from redis import Redis
from dotenv import load_dotenv

from app.arkham.services.db.models import MiniDoc, PageOCR, Chunk, Document, TimelineEvent, DateMention, SensitiveDataMatch
from app.arkham.services.timeline_service import extract_timeline_from_chunk
from app.arkham.services.utils.pattern_detector import detect_sensitive_data
# from arkham.services.embedding_services import embed_hybrid # Not used here
# Actually parser just chunks. Embedder embeds.

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB & Redis
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(REDIS_URL)
q = Queue(connection=redis_conn)


def parse_minidoc_job(minidoc_db_id):
    """
    Stitches OCR text for a MiniDoc, chunks it, and enqueues embedding.
    """
    session = Session()
    try:
        minidoc = session.query(MiniDoc).get(minidoc_db_id)
        if not minidoc:
            logger.error(f"MiniDoc {minidoc_db_id} not found.")
            return

        logger.info(f"Parsing MiniDoc: {minidoc.minidoc_id}")

        # 1. Fetch Pages
        pages = (
            session.query(PageOCR)
            .filter(
                PageOCR.document_id == minidoc.document_id,
                PageOCR.page_num >= minidoc.page_start,
                PageOCR.page_num <= minidoc.page_end,
            )
            .order_by(PageOCR.page_num)
            .all()
        )

        if not pages:
            logger.warning("No pages found for MiniDoc.")
            return

        # 2. Stitch Text
        full_text = ""
        for p in pages:
            full_text += f"=== PAGE {p.page_num} START ===\n"
            full_text += p.text + "\n"
            full_text += f"=== PAGE {p.page_num} END ===\n\n"

        # 3. Chunking
        step = 512
        overlap = 50

        # Global chunk indexing strategy:
        # MiniDocs are processed in parallel, so we use page_start as a namespace.
        # Formula: (page_start * 1_000_000) + local_chunk_index
        # This supports up to 1M chunks per minidoc (with 512-char chunks = 512MB text, far exceeding any real document).
        local_chunk_index = 0

        for i in range(0, len(full_text), step - overlap):
            chunk_text = full_text[i : i + step]

            # Calculate global chunk index using page_start namespace
            global_chunk_index = (minidoc.page_start * 1_000_000) + local_chunk_index

            chunk = Chunk(
                doc_id=minidoc.document_id,
                text=chunk_text,
                chunk_index=global_chunk_index,
            )
            session.add(chunk)
            session.flush()  # Get ID

            # Extract timeline information from chunk
            try:
                date_mentions, timeline_events = extract_timeline_from_chunk(
                    chunk_text, chunk.id, minidoc.document_id
                )

                # Insert date mentions
                for mention_data in date_mentions:
                    mention = DateMention(**mention_data)
                    session.add(mention)

                # Insert timeline events
                for event_data in timeline_events:
                    event = TimelineEvent(**event_data)
                    session.add(event)

                if date_mentions or timeline_events:
                    logger.info(
                        f"Extracted {len(date_mentions)} date mentions and {len(timeline_events)} events from chunk {chunk.id}"
                    )

            except Exception as e:
                logger.warning(f"Timeline extraction failed for chunk {chunk.id}: {str(e)}")
                # Don't fail the entire parsing job if timeline extraction fails

            # Detect sensitive data patterns
            try:
                sensitive_matches = detect_sensitive_data(chunk_text)

                for match in sensitive_matches:
                    sensitive_data = SensitiveDataMatch(
                        chunk_id=chunk.id,
                        doc_id=minidoc.document_id,
                        pattern_type=match.pattern_type,
                        match_text=match.match_text,
                        confidence=match.confidence,
                        start_pos=match.start_pos,
                        end_pos=match.end_pos,
                        context_before=match.context_before,
                        context_after=match.context_after
                    )
                    session.add(sensitive_data)

                if sensitive_matches:
                    logger.info(
                        f"Detected {len(sensitive_matches)} sensitive pattern(s) in chunk {chunk.id}"
                    )

            except Exception as e:
                logger.warning(f"Sensitive data detection failed for chunk {chunk.id}: {str(e)}")
                # Don't fail the entire parsing job if pattern detection fails

            # Enqueue Embed Job
            q.enqueue("arkham.services.workers.embed_worker.embed_chunk_job", chunk_id=chunk.id)

            # Increment local chunk counter for next iteration
            local_chunk_index += 1

        minidoc.status = "parsed"
        session.commit()
        logger.info(
            f"MiniDoc {minidoc.minidoc_id} parsed. Created {local_chunk_index} chunks."
        )

    except Exception as e:
        logger.error(f"Parser failed: {e}")
        session.rollback()
    finally:
        session.close()
