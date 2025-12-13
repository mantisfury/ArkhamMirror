import sys
import logging
from pathlib import Path

import subprocess

from config.settings import DATABASE_URL, QDRANT_URL

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

# Import base models to ensure they're registered with SQLAlchemy
from app.arkham.services.db.models import Base


def _table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = :table_name
                );
            """),
                {"table_name": table_name},
            ).scalar()
            return result
    except Exception:
        return False


def _create_base_tables(engine) -> bool:
    """Create all base tables from SQLAlchemy models if they don't exist."""
    try:
        # Create all tables defined in models.py
        Base.metadata.create_all(engine)
        logger.info("✓ Base database tables ensured")
        return True
    except Exception as e:
        logger.error(f"Failed to create base tables: {e}")
        return False


def _run_phase5_migration(engine) -> bool:
    """Create Phase 5.2 tables (ingestion_errors, entity_filter_rules)."""
    try:
        with engine.connect() as conn:
            # Check and create ingestion_errors table
            if not _table_exists(engine, "ingestion_errors"):
                logger.info("Creating ingestion_errors table...")
                conn.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS ingestion_errors (
                        id SERIAL PRIMARY KEY,
                        document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                        chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
                        stage VARCHAR(50) NOT NULL,
                        error_type VARCHAR(100) NOT NULL,
                        error_message TEXT NOT NULL,
                        stack_trace TEXT,
                        is_resolved INTEGER DEFAULT 0,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_ingestion_errors_doc_id ON ingestion_errors(document_id);"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_ingestion_errors_stage ON ingestion_errors(stage);"
                    )
                )
                conn.commit()
                logger.info("✓ ingestion_errors table created")

            # Check and create entity_filter_rules table
            if not _table_exists(engine, "entity_filter_rules"):
                logger.info("Creating entity_filter_rules table...")
                conn.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS entity_filter_rules (
                        id SERIAL PRIMARY KEY,
                        pattern VARCHAR(255) NOT NULL,
                        is_regex INTEGER DEFAULT 1,
                        created_by VARCHAR(50) DEFAULT 'system',
                        description VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                )

                # Insert default filter rules for noisy entities
                default_rules = [
                    (r"^\d+$", "Pure numbers"),
                    (r"^[\W_]+$", "Only special characters"),
                    (r"^.{1,2}$", "Too short (1-2 chars)"),
                    (r"^\d{1,2}/\d{1,2}(/\d{2,4})?$", "Date patterns like 12/25"),
                    (
                        r"^(january|february|march|april|may|june|july|august|september|october|november|december)$",
                        "Month names",
                    ),
                    (r"^page\s*\d+$", "Page markers"),
                    (
                        r"^(start|end|figure|table|section|chapter)$",
                        "Document structure words",
                    ),
                ]

                for pattern, description in default_rules:
                    conn.execute(
                        text("""
                        INSERT INTO entity_filter_rules (pattern, is_regex, created_by, description)
                        VALUES (:pattern, 1, 'system', :description)
                    """),
                        {"pattern": pattern, "description": description},
                    )

                conn.commit()
                logger.info(
                    f"✓ entity_filter_rules table created with {len(default_rules)} default rules"
                )

        return True
    except Exception as e:
        logger.error(f"Failed to run Phase 5 migration: {e}")
        return False


def _run_additional_indexes(engine) -> bool:
    """Create additional indexes for performance."""
    try:
        with engine.connect() as conn:
            # Performance indexes (IF NOT EXISTS to be idempotent)
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);",
                "CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);",
                "CREATE INDEX IF NOT EXISTS idx_entities_doc_id ON entities(doc_id);",
                "CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_entity_id);",
                "CREATE INDEX IF NOT EXISTS idx_timeline_events_doc_id ON timeline_events(doc_id);",
                "CREATE INDEX IF NOT EXISTS idx_timeline_events_date ON timeline_events(event_date);",
            ]

            for idx_sql in indexes:
                try:
                    conn.execute(text(idx_sql))
                except Exception:
                    pass  # Index might already exist

            conn.commit()
            logger.debug("✓ Additional indexes ensured")

        return True
    except Exception as e:
        logger.warning(f"Failed to create some indexes: {e}")
        return True  # Non-critical


def _get_embedding_dimension() -> int:
    """
    Get the vector dimension based on configured embedding provider.

    Returns:
        1024 for BGE-M3 (default), 384 for MiniLM
    """
    try:
        from app.arkham.services.config import get_config

        provider = get_config("embedding.provider", "bge-m3")

        if provider == "minilm-bm25":
            dimension = get_config(
                "embedding.providers.minilm-bm25.dense_dimension", 384
            )
            logger.info(f"Using MiniLM embeddings (dimension={dimension})")
            return dimension
        else:
            dimension = get_config("embedding.providers.bge-m3.dense_dimension", 1024)
            logger.info(f"Using BGE-M3 embeddings (dimension={dimension})")
            return dimension
    except Exception as e:
        logger.warning(f"Could not read embedding config, defaulting to 1024: {e}")
        return 1024


def _ensure_qdrant_collection() -> bool:
    """
    Create Qdrant collection if it doesn't exist.

    This is idempotent and safe to call on every startup.
    Collection is created with named vectors for hybrid search:
    - 'dense': Dense embeddings from BGE-M3 or MiniLM
    - 'sparse': Sparse embeddings for BM25-style search

    Collection dimension is dynamic based on embedding.provider in config.yaml:
    - bge-m3: 1024 dimensions (default, multilingual, ~2.2GB)
    - minilm-bm25: 384 dimensions (lightweight, English-only, ~80MB)
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        from qdrant_client.http.exceptions import UnexpectedResponse

        collection_name = "arkham_mirror_hybrid"

        try:
            client = QdrantClient(url=QDRANT_URL, timeout=5.0)

            # Check if collection exists
            collections = client.get_collections().collections
            existing = next((c for c in collections if c.name == collection_name), None)

            if existing:
                # Collection exists - assume it was created with correct schema
                # Note: If schema is wrong, user must delete collection manually
                logger.debug(f"✓ Qdrant collection '{collection_name}' already exists")
                return True

            # Get dimension from configured embedding provider
            vector_dimension = _get_embedding_dimension()

            # Create the collection with NAMED VECTORS for hybrid search
            # This matches what embed_worker.py expects
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=vector_dimension,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(),
                },
            )
            logger.info(
                f"✓ Qdrant collection '{collection_name}' created (dimension={vector_dimension}, hybrid=True)"
            )
            return True

        except (ConnectionError, ConnectionRefusedError, UnexpectedResponse) as e:
            logger.warning(f"Could not connect to Qdrant at {QDRANT_URL}: {e}")
            logger.warning(
                "Vector search will not work until Qdrant is running. Start with: docker compose up -d"
            )
            return True  # Non-critical - app can start without vector search

    except ImportError:
        logger.warning("qdrant-client not installed. Vector search disabled.")
        return True  # Non-critical
    except Exception as e:
        logger.warning(f"Could not initialize Qdrant: {e}")
        return True  # Non-critical


def _ensure_spacy_model() -> bool:
    """
    Download spaCy language model if not present.

    This is idempotent - skips download if model exists.
    Model is used for named entity recognition (NER).
    """
    model_name = "en_core_web_sm"

    try:
        import spacy

        # Try to load the model
        try:
            spacy.load(model_name)
            logger.debug(f"✓ spaCy model '{model_name}' already installed")
            return True
        except OSError:
            # Model not found, download it
            logger.info(f"Downloading spaCy language model '{model_name}'...")
            logger.info("This may take a minute on first run...")

            result = subprocess.run(
                [sys.executable, "-m", "spacy", "download", model_name],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info(f"✓ spaCy model '{model_name}' downloaded successfully")
                return True
            else:
                logger.warning(f"Failed to download spaCy model: {result.stderr}")
                return True  # Non-critical

    except ImportError:
        logger.warning("spaCy not installed. Named entity recognition disabled.")
        return True  # Non-critical
    except Exception as e:
        logger.warning(f"Could not initialize spaCy: {e}")
        return True  # Non-critical


def ensure_database_ready() -> bool:
    """
    Ensure the database and dependencies are fully initialized and ready for use.

    This function is idempotent - safe to call on every startup.
    It will:
    1. Create all base tables from SQLAlchemy models
    2. Run migrations for additional tables
    3. Create performance indexes
    4. Ensure Qdrant collection exists (for vector search)
    5. Ensure spaCy model is downloaded (for NER)

    Returns:
        True if database is ready, False if initialization failed.
    """
    try:
        logger.info("Checking database initialization...")

        engine = create_engine(DATABASE_URL)

        # Test database connection
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError as e:
            logger.error(f"Cannot connect to database: {e}")
            logger.error("Make sure PostgreSQL is running (docker compose up -d)")
            return False

        # Check if documents table exists (basic indicator of initialization)
        needs_init = not _table_exists(engine, "documents")

        if needs_init:
            logger.info("Database not initialized. Creating tables...")

        # Create base tables (always safe to run - uses IF NOT EXISTS internally)
        if not _create_base_tables(engine):
            return False

        # Run migrations for additional tables
        if not _run_phase5_migration(engine):
            return False

        # Create performance indexes
        _run_additional_indexes(engine)

        if needs_init:
            logger.info("✓ Database initialization complete!")
        else:
            logger.debug("✓ Database already initialized")

        # Initialize Qdrant collection (non-critical)
        _ensure_qdrant_collection()

        # Ensure spaCy model is available (non-critical)
        _ensure_spacy_model()

        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# Allow running as standalone script
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = ensure_database_ready()
    if success:
        print("\n✓ Database is ready!")
    else:
        print("\n✗ Database initialization failed!")
        sys.exit(1)
