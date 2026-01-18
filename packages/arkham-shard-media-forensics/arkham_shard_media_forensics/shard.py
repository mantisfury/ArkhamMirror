"""Media Forensics Shard - Media metadata extraction and forensic analysis."""

import base64
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

from arkham_frame.shard_interface import ArkhamShard


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert an object to be JSON-serializable."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return f"<bytes:{len(obj)}>"
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    # Handle numpy types
    try:
        import numpy as np
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    # Handle IFDRational, Fraction, and other numeric types
    try:
        return float(obj)
    except (TypeError, ValueError):
        pass
    # Fall back to string representation
    return str(obj)

from .api import init_api, router
from .models import (
    AnalysisStats,
    ELAResult,
    IntegrityStatus,
    MediaAnalysis,
    SimilarImage,
    SunVerification,
)

logger = logging.getLogger(__name__)


class MediaForensicsShard(ArkhamShard):
    """
    Media Forensics shard for ArkhamFrame.

    Provides media metadata extraction and forensic analysis for images:
    - EXIF/XMP metadata extraction
    - Perceptual hashing (pHash, dHash, aHash) for image similarity
    - C2PA Content Credentials parsing and verification
    - Error Level Analysis (ELA) visualization
    - Sun position verification for shadow analysis

    All features work fully offline (air-gap compatible).
    """

    name = "media-forensics"
    version = "0.1.0"
    description = "Media metadata extraction and forensic analysis"

    def __init__(self):
        super().__init__()
        self._frame = None
        self._db = None
        self._event_bus = None
        self._storage = None

        # Services (lazy-loaded)
        self.exif_extractor = None
        self.hash_service = None
        self.c2pa_parser = None
        self.ela_analyzer = None
        self.sun_position = None

    async def initialize(self, frame) -> None:
        """
        Initialize the shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame
        self._db = frame.database
        self._event_bus = frame.get_service("events")
        self._storage = frame.get_service("storage")

        logger.info("Initializing Media Forensics Shard...")

        # Create database schema
        await self._create_schema()

        # Initialize services
        self._init_services()

        # Initialize API with shard reference
        init_api(self)

        # Subscribe to events
        if self._event_bus:
            await self._event_bus.subscribe("document.ingested", self._handle_document_ingested)
            logger.info("Subscribed to document.ingested event")

        # Register on app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.media_forensics_shard = self
            logger.debug("Media Forensics Shard registered on app.state")

        logger.info("Media Forensics Shard initialized")

    def _init_services(self) -> None:
        """Initialize service classes (lazy import to avoid import errors)."""
        try:
            from .services.exif_extractor import ExifExtractor
            self.exif_extractor = ExifExtractor(self._frame)
            logger.debug("ExifExtractor initialized")
        except ImportError as e:
            logger.warning(f"ExifExtractor not available: {e}")

        try:
            from .services.perceptual_hash import PerceptualHashService
            self.hash_service = PerceptualHashService(self._frame)
            logger.debug("PerceptualHashService initialized")
        except ImportError as e:
            logger.warning(f"PerceptualHashService not available: {e}")

        try:
            from .services.c2pa_parser import C2PAParser
            self.c2pa_parser = C2PAParser(self._frame)
            logger.debug("C2PAParser initialized")
        except ImportError as e:
            logger.warning(f"C2PAParser not available: {e}")

        try:
            from .services.ela_analyzer import ELAAnalyzer
            self.ela_analyzer = ELAAnalyzer(self._frame)
            logger.debug("ELAAnalyzer initialized")
        except ImportError as e:
            logger.warning(f"ELAAnalyzer not available: {e}")

        try:
            from .services.sun_position import SunPositionService
            self.sun_position = SunPositionService(self._frame)
            logger.debug("SunPositionService initialized")
        except ImportError as e:
            logger.warning(f"SunPositionService not available: {e}")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Media Forensics Shard...")

        # Unsubscribe from events
        if self._event_bus:
            self._event_bus.unsubscribe("document.ingested")

        # Clear services
        self.exif_extractor = None
        self.hash_service = None
        self.c2pa_parser = None
        self.ela_analyzer = None
        self.sun_position = None

        logger.info("Media Forensics Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # ===========================================
    # Database Schema
    # ===========================================

    async def _create_schema(self) -> None:
        """Create database tables for media forensics."""
        if not self._db:
            logger.warning("Database not available - persistence disabled")
            return

        try:
            # Main analyses table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_media_analyses (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,  -- Nullable for direct file analysis
                    tenant_id UUID,

                    -- File info
                    filename TEXT,  -- Original filename
                    file_path TEXT,  -- Full path to file for ELA and other operations
                    file_type TEXT,
                    file_size INTEGER,
                    width INTEGER,
                    height INTEGER,

                    -- Cryptographic hashes
                    sha256 TEXT,
                    md5 TEXT,

                    -- Perceptual hashes
                    phash TEXT,
                    dhash TEXT,
                    ahash TEXT,

                    -- EXIF data (JSON)
                    exif_data TEXT DEFAULT '{}',

                    -- Camera info (extracted from EXIF)
                    camera_make TEXT,
                    camera_model TEXT,
                    software TEXT,

                    -- Timestamps (extracted from EXIF)
                    datetime_original TEXT,
                    datetime_digitized TEXT,
                    datetime_modified TEXT,

                    -- GPS (extracted from EXIF)
                    gps_latitude REAL,
                    gps_longitude REAL,
                    gps_altitude REAL,

                    -- C2PA data (JSON)
                    c2pa_data TEXT DEFAULT '{}',
                    has_c2pa INTEGER DEFAULT 0,
                    c2pa_signer TEXT,
                    c2pa_timestamp TEXT,

                    -- Analysis results
                    warnings TEXT DEFAULT '[]',
                    anomalies TEXT DEFAULT '[]',
                    integrity_status TEXT DEFAULT 'unknown',
                    confidence_score REAL DEFAULT 0.0,

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add file_path column if not exists (for existing databases)
            try:
                await self._db.execute("""
                    ALTER TABLE arkham_media_analyses ADD COLUMN IF NOT EXISTS file_path TEXT
                """)
            except Exception:
                pass  # Column might already exist or not supported

            # Similar images table (for perceptual hash matches)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_media_similar (
                    id TEXT PRIMARY KEY,
                    source_analysis_id TEXT NOT NULL,
                    target_analysis_id TEXT NOT NULL,

                    hash_type TEXT NOT NULL,
                    hamming_distance INTEGER NOT NULL,
                    similarity_score REAL NOT NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (source_analysis_id) REFERENCES arkham_media_analyses(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_analysis_id) REFERENCES arkham_media_analyses(id) ON DELETE CASCADE,
                    UNIQUE(source_analysis_id, target_analysis_id, hash_type)
                )
            """)

            # ELA results table (generated on demand)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_media_ela (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,

                    quality INTEGER DEFAULT 95,
                    ela_image_path TEXT,

                    -- Analysis of ELA result
                    uniform_regions TEXT DEFAULT '[]',
                    anomalous_regions TEXT DEFAULT '[]',
                    interpretation TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (analysis_id) REFERENCES arkham_media_analyses(id) ON DELETE CASCADE
                )
            """)

            # Sun position verification table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_media_sun_verification (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,

                    -- Input parameters
                    claimed_datetime TEXT,
                    latitude REAL,
                    longitude REAL,

                    -- Calculated sun position
                    sun_altitude REAL,
                    sun_azimuth REAL,
                    expected_shadow_direction REAL,

                    -- Verification result
                    verification_status TEXT,
                    notes TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (analysis_id) REFERENCES arkham_media_analyses(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_analyses_document ON arkham_media_analyses(document_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_analyses_tenant ON arkham_media_analyses(tenant_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_analyses_phash ON arkham_media_analyses(phash)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_analyses_integrity ON arkham_media_analyses(integrity_status)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_similar_source ON arkham_media_similar(source_analysis_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_ela_analysis ON arkham_media_ela(analysis_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_media_sun_analysis ON arkham_media_sun_verification(analysis_id)"
            )

            # Migration: add tenant_id column if missing
            await self._db.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'arkham_media_analyses'
                        AND column_name = 'tenant_id'
                    ) THEN
                        ALTER TABLE arkham_media_analyses ADD COLUMN tenant_id UUID;
                    END IF;
                END $$;
            """)

            # Migration: make document_id nullable for direct file analysis
            try:
                await self._db.execute("""
                    ALTER TABLE arkham_media_analyses
                    ALTER COLUMN document_id DROP NOT NULL;
                """)
            except Exception:
                pass  # Column may already be nullable

            # Migration: add filename column if it doesn't exist
            try:
                await self._db.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'arkham_media_analyses'
                            AND column_name = 'filename'
                        ) THEN
                            ALTER TABLE arkham_media_analyses ADD COLUMN filename TEXT;
                        END IF;
                    END $$;
                """)
            except Exception:
                pass  # Column may already exist

            logger.info("Media forensics schema created successfully")

        except Exception as e:
            logger.error(f"Failed to create schema: {e}")

    # ===========================================
    # Event Handlers
    # ===========================================

    async def _handle_document_ingested(self, event_data: Dict) -> None:
        """Auto-analyze image documents when ingested."""
        doc_id = event_data.get("document_id")
        doc_type = event_data.get("doc_type", "").lower()

        # Only process image types
        image_types = ["image/jpeg", "image/png", "image/tiff", "image/webp", "image/heic", "image/gif"]
        if any(t in doc_type for t in image_types):
            try:
                await self.analyze_document(doc_id)
                logger.info(f"Auto-analyzed document {doc_id}")
            except Exception as e:
                logger.warning(f"Auto-analysis failed for {doc_id}: {e}")

    # ===========================================
    # Public API Methods
    # ===========================================

    async def analyze_document(self, document_id: str) -> Dict[str, Any]:
        """
        Perform full media analysis on a document.

        Extracts EXIF, computes hashes, parses C2PA.

        Args:
            document_id: Document ID to analyze

        Returns:
            Analysis results dictionary

        Raises:
            FileNotFoundError: If document or file not found
            ValueError: If document is not an image
        """
        if not self._db:
            raise RuntimeError("Database service not available")

        # Get document from frame
        doc = await self._db.fetch_one(
            "SELECT id, path, doc_type FROM arkham_frame.documents WHERE id = :id",
            {"id": document_id},
        )

        if not doc:
            raise FileNotFoundError(f"Document {document_id} not found")

        file_path = Path(doc["path"])
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Create analysis record
        analysis_id = str(uuid.uuid4())
        tenant_id = self.get_tenant_id_or_none()

        # Extract metadata
        exif_data = {}
        if self.exif_extractor:
            exif_data = await self.exif_extractor.extract_all(file_path)

        # Compute hashes
        hashes = {}
        if self.hash_service:
            hashes = await self.hash_service.compute_all_hashes(file_path)

        # Parse C2PA
        c2pa_data = {}
        c2pa_interpretation = {}
        if self.c2pa_parser:
            c2pa_data = await self.c2pa_parser.parse(file_path) or {}
            c2pa_interpretation = self.c2pa_parser.interpret_c2pa(c2pa_data)

        # Compile warnings
        warnings = exif_data.get("warnings", [])
        if c2pa_interpretation.get("is_ai_generated"):
            warnings.append(f"AI_GENERATED: C2PA indicates AI generation by {c2pa_data.get('signer')}")

        # Determine integrity status
        if c2pa_data and c2pa_data.get("has_c2pa") and c2pa_data.get("signature_valid"):
            integrity_status = "verified"
        elif warnings:
            integrity_status = "flagged"
        else:
            integrity_status = "unverified"

        # Calculate confidence score
        confidence_score = 0.8 if c2pa_data and c2pa_data.get("has_c2pa") else 0.5

        # Save to database
        await self._db.execute(
            """
            INSERT INTO arkham_media_analyses (
                id, document_id, tenant_id, filename, file_type,
                width, height,
                sha256, md5, phash, dhash, ahash,
                exif_data,
                camera_make, camera_model, software,
                datetime_original, datetime_digitized, datetime_modified,
                gps_latitude, gps_longitude, gps_altitude,
                c2pa_data, has_c2pa, c2pa_signer, c2pa_timestamp,
                warnings, integrity_status, confidence_score,
                created_at, updated_at
            ) VALUES (
                :id, :document_id, :tenant_id, :filename, :file_type,
                :width, :height,
                :sha256, :md5, :phash, :dhash, :ahash,
                :exif_data,
                :camera_make, :camera_model, :software,
                :datetime_original, :datetime_digitized, :datetime_modified,
                :gps_latitude, :gps_longitude, :gps_altitude,
                :c2pa_data, :has_c2pa, :c2pa_signer, :c2pa_timestamp,
                :warnings, :integrity_status, :confidence_score,
                :created_at, :updated_at
            )
            ON CONFLICT (id) DO UPDATE SET
                exif_data = EXCLUDED.exif_data,
                warnings = EXCLUDED.warnings,
                integrity_status = EXCLUDED.integrity_status,
                updated_at = NOW()
            """,
            {
                "id": analysis_id,
                "document_id": document_id,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "filename": file_path.name,
                "file_type": doc["doc_type"],
                "width": exif_data.get("basic", {}).get("width"),
                "height": exif_data.get("basic", {}).get("height"),
                "sha256": hashes.get("sha256"),
                "md5": hashes.get("md5"),
                "phash": hashes.get("phash"),
                "dhash": hashes.get("dhash"),
                "ahash": hashes.get("ahash"),
                "exif_data": json.dumps(_make_json_safe(exif_data.get("exif", {}))),
                "camera_make": exif_data.get("camera", {}).get("make"),
                "camera_model": exif_data.get("camera", {}).get("model"),
                "software": exif_data.get("camera", {}).get("software"),
                "datetime_original": exif_data.get("timestamps", {}).get("datetime_original"),
                "datetime_digitized": exif_data.get("timestamps", {}).get("datetime_digitized"),
                "datetime_modified": exif_data.get("timestamps", {}).get("datetime_modified"),
                "gps_latitude": exif_data.get("gps", {}).get("latitude"),
                "gps_longitude": exif_data.get("gps", {}).get("longitude"),
                "gps_altitude": exif_data.get("gps", {}).get("altitude"),
                "c2pa_data": json.dumps(_make_json_safe(c2pa_data)) if c2pa_data else "{}",
                "has_c2pa": 1 if c2pa_data and c2pa_data.get("has_c2pa") else 0,
                "c2pa_signer": c2pa_data.get("signer") if c2pa_data else None,
                "c2pa_timestamp": c2pa_data.get("timestamp") if c2pa_data else None,
                "warnings": json.dumps(warnings),
                "integrity_status": integrity_status,
                "confidence_score": confidence_score,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "media.metadata.extracted",
                {
                    "document_id": document_id,
                    "analysis_id": analysis_id,
                    "has_exif": bool(exif_data.get("exif")),
                    "has_gps": bool(exif_data.get("gps", {}).get("latitude")),
                    "has_c2pa": bool(c2pa_data and c2pa_data.get("has_c2pa")),
                    "warnings": warnings,
                    "integrity_status": integrity_status,
                },
                source="media-forensics",
            )

        # Find similar images
        if self.hash_service and hashes.get("phash"):
            similar = await self.hash_service.find_similar(
                hashes["phash"], hash_type="phash", threshold=10
            )
            # Filter out self
            similar = [s for s in similar if s["analysis_id"] != analysis_id]

            if similar and self._event_bus:
                await self._event_bus.emit(
                    "media.similar.found",
                    {
                        "source_analysis_id": analysis_id,
                        "similar_count": len(similar),
                        "matches": [s["analysis_id"] for s in similar[:5]],
                    },
                    source="media-forensics",
                )

        return {
            "analysis_id": analysis_id,
            "document_id": document_id,
            "exif": exif_data,
            "hashes": hashes,
            "c2pa": c2pa_data,
            "c2pa_interpretation": c2pa_interpretation,
            "warnings": warnings,
            "integrity_status": integrity_status,
        }

    async def analyze_file(
        self,
        file_path: Path,
        filename: str,
        run_ela: bool = False,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze an image file directly without requiring a document record.

        This is the core analysis method that works on raw files.

        Args:
            file_path: Path to the image file
            filename: Original filename for display
            run_ela: Whether to also run ELA analysis
            document_id: Optional document ID to link to

        Returns:
            Analysis results dictionary
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Create analysis record
        analysis_id = str(uuid.uuid4())
        tenant_id = self.get_tenant_id_or_none()

        # Get file info
        file_size = file_path.stat().st_size
        file_type = file_path.suffix.lower().lstrip(".")

        # Extract EXIF metadata
        exif_data = {}
        if self.exif_extractor:
            try:
                exif_data = await self.exif_extractor.extract_all(file_path)
                logger.info(f"EXIF extraction complete: {len(exif_data)} keys")
            except Exception as e:
                logger.warning(f"EXIF extraction failed: {e}")
                exif_data = {"error": str(e), "warnings": [f"EXIF extraction failed: {e}"]}

        # Compute perceptual hashes
        hashes = {}
        if self.hash_service:
            try:
                hashes = await self.hash_service.compute_all_hashes(file_path)
                logger.info(f"Hash computation complete: {list(hashes.keys())}")
            except Exception as e:
                logger.warning(f"Hash computation failed: {e}")
                hashes = {"error": str(e)}

        # Parse C2PA content credentials
        c2pa_data = {}
        c2pa_interpretation = {}
        if self.c2pa_parser:
            try:
                c2pa_data = await self.c2pa_parser.parse(file_path) or {}
                c2pa_interpretation = self.c2pa_parser.interpret_c2pa(c2pa_data)
                logger.info(f"C2PA parsing complete: has_c2pa={c2pa_data.get('has_c2pa')}")
            except Exception as e:
                logger.warning(f"C2PA parsing failed: {e}")
                c2pa_data = {"error": str(e)}

        # Compile warnings from all sources
        warnings = list(exif_data.get("warnings", []))
        if c2pa_interpretation.get("is_ai_generated"):
            warnings.append(f"AI_GENERATED: C2PA indicates AI generation by {c2pa_data.get('signer')}")

        # Determine integrity status
        if c2pa_data and c2pa_data.get("has_c2pa") and c2pa_data.get("signature_valid"):
            integrity_status = "verified"
        elif warnings:
            integrity_status = "flagged"
        else:
            integrity_status = "unverified"

        # Calculate confidence score
        confidence_score = 0.8 if c2pa_data and c2pa_data.get("has_c2pa") else 0.5

        # ELA analysis if requested
        ela_result = None
        if run_ela and self.ela_analyzer:
            try:
                ela_result = await self.ela_analyzer.analyze(file_path)
                logger.info("ELA analysis complete")
            except Exception as e:
                logger.warning(f"ELA analysis failed: {e}")
                ela_result = {"error": str(e)}

        # Save to database if available
        if self._db:
            try:
                await self._db.execute(
                    """
                    INSERT INTO arkham_media_analyses (
                        id, document_id, tenant_id, filename, file_path, file_type, file_size,
                        width, height,
                        sha256, md5, phash, dhash, ahash,
                        exif_data,
                        camera_make, camera_model, software,
                        datetime_original, datetime_digitized, datetime_modified,
                        gps_latitude, gps_longitude, gps_altitude,
                        c2pa_data, has_c2pa, c2pa_signer, c2pa_timestamp,
                        warnings, integrity_status, confidence_score,
                        created_at, updated_at
                    ) VALUES (
                        :id, :document_id, :tenant_id, :filename, :file_path, :file_type, :file_size,
                        :width, :height,
                        :sha256, :md5, :phash, :dhash, :ahash,
                        :exif_data,
                        :camera_make, :camera_model, :software,
                        :datetime_original, :datetime_digitized, :datetime_modified,
                        :gps_latitude, :gps_longitude, :gps_altitude,
                        :c2pa_data, :has_c2pa, :c2pa_signer, :c2pa_timestamp,
                        :warnings, :integrity_status, :confidence_score,
                        :created_at, :updated_at
                    )
                    """,
                    {
                        "id": analysis_id,
                        "document_id": document_id,
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "filename": file_path.name,
                        "file_path": str(file_path.absolute()),
                        "file_type": file_type,
                        "file_size": file_size,
                        "width": exif_data.get("basic", {}).get("width"),
                        "height": exif_data.get("basic", {}).get("height"),
                        "sha256": hashes.get("sha256"),
                        "md5": hashes.get("md5"),
                        "phash": hashes.get("phash"),
                        "dhash": hashes.get("dhash"),
                        "ahash": hashes.get("ahash"),
                        "exif_data": json.dumps(_make_json_safe(exif_data.get("exif", {}))),
                        "camera_make": exif_data.get("camera", {}).get("make"),
                        "camera_model": exif_data.get("camera", {}).get("model"),
                        "software": exif_data.get("camera", {}).get("software"),
                        "datetime_original": exif_data.get("timestamps", {}).get("datetime_original"),
                        "datetime_digitized": exif_data.get("timestamps", {}).get("datetime_digitized"),
                        "datetime_modified": exif_data.get("timestamps", {}).get("datetime_modified"),
                        "gps_latitude": exif_data.get("gps", {}).get("latitude"),
                        "gps_longitude": exif_data.get("gps", {}).get("longitude"),
                        "gps_altitude": exif_data.get("gps", {}).get("altitude"),
                        "c2pa_data": json.dumps(_make_json_safe(c2pa_data)) if c2pa_data else "{}",
                        "has_c2pa": 1 if c2pa_data and c2pa_data.get("has_c2pa") else 0,
                        "c2pa_signer": c2pa_data.get("signer") if c2pa_data else None,
                        "c2pa_timestamp": c2pa_data.get("timestamp") if c2pa_data else None,
                        "warnings": json.dumps(warnings),
                        "integrity_status": integrity_status,
                        "confidence_score": confidence_score,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                )
                logger.info(f"Saved analysis {analysis_id} to database")
            except Exception as e:
                logger.error(f"Failed to save analysis to database: {e}")

        # Emit event
        if self._event_bus:
            try:
                await self._event_bus.emit(
                    "media.file.analyzed",
                    {
                        "analysis_id": analysis_id,
                        "filename": filename,
                        "file_type": file_type,
                        "has_exif": bool(exif_data.get("exif")),
                        "has_gps": bool(exif_data.get("gps", {}).get("latitude")),
                        "has_c2pa": bool(c2pa_data and c2pa_data.get("has_c2pa")),
                        "warnings_count": len(warnings),
                        "integrity_status": integrity_status,
                    },
                    source="media-forensics",
                )
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")

        # Build result
        result = {
            "analysis_id": analysis_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "exif": exif_data,
            "hashes": hashes,
            "c2pa": c2pa_data,
            "c2pa_interpretation": c2pa_interpretation,
            "warnings": warnings,
            "integrity_status": integrity_status,
            "confidence_score": confidence_score,
        }

        if ela_result:
            result["ela"] = ela_result

        return result

    async def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific analysis by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_media_analyses WHERE id = :id",
            {"id": analysis_id}
        )

        if not row:
            return None

        return self._row_to_analysis_dict(row)

    async def get_analysis_by_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis for a specific document."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_media_analyses WHERE document_id = :document_id ORDER BY created_at DESC LIMIT 1",
            {"document_id": document_id}
        )

        if not row:
            return None

        return self._row_to_analysis_dict(row)

    async def list_analyses(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        verification_status: Optional[str] = None,
        has_c2pa: Optional[bool] = None,
        has_warnings: Optional[bool] = None,
        has_findings: Optional[bool] = None,
        integrity_status: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List media analyses with optional filtering."""
        if not self._db:
            return []

        # Build query with filters
        query = "SELECT * FROM arkham_media_analyses WHERE 1=1"
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        # Add tenant filtering
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        # Status filters (map to integrity_status for now as we don't have a separate status column)
        if status:
            # Status is mapped to integrity_status for compatibility
            pass  # Status not yet implemented as a separate column

        if verification_status:
            query += " AND integrity_status = :verification_status"
            params["verification_status"] = verification_status

        if has_c2pa is not None:
            query += " AND has_c2pa = :has_c2pa"
            params["has_c2pa"] = 1 if has_c2pa else 0

        if has_warnings is not None:
            if has_warnings:
                query += " AND warnings != '[]'"
            else:
                query += " AND warnings = '[]'"

        if has_findings is not None:
            # has_findings maps to has_warnings for now
            if has_findings:
                query += " AND warnings != '[]'"
            else:
                query += " AND warnings = '[]'"

        if integrity_status:
            query += " AND integrity_status = :integrity_status"
            params["integrity_status"] = integrity_status

        if doc_id:
            query += " AND document_id = :doc_id"
            params["doc_id"] = doc_id

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_analysis_dict(row) for row in rows]

    async def get_analysis_count(self) -> int:
        """Get total analysis count."""
        if not self._db:
            return 0

        query = "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE 1=1"
        params: Dict[str, Any] = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db.fetch_one(query, params)
        return row["count"] if row else 0

    async def generate_ela(
        self,
        analysis_id: str,
        quality: int = 95,
        scale: int = 15,
    ) -> Dict[str, Any]:
        """
        Generate Error Level Analysis for an analysis.

        Args:
            analysis_id: Analysis ID
            quality: JPEG quality for resave (90-95 recommended)
            scale: Multiplier for error visualization (10-20 recommended)

        Returns:
            ELA result with base64 image and interpretation
        """
        if not self.ela_analyzer:
            return {"success": False, "error": "ELA analyzer not available"}

        analysis = await self.get_analysis(analysis_id)
        if not analysis:
            return {"success": False, "error": "Analysis not found"}

        # Get file path - first try from analysis record, then from documents table
        file_path = None

        # Check if file_path is stored directly on the analysis
        if analysis.get("file_path"):
            file_path = Path(analysis["file_path"])

        # Fall back to documents table if we have a document_id
        if (not file_path or not file_path.exists()) and analysis.get("document_id"):
            doc = await self._db.fetch_one(
                "SELECT path FROM arkham_frame.documents WHERE id = :id",
                {"id": analysis["document_id"]}
            )
            if doc and doc.get("path"):
                file_path = Path(doc["path"])

        if not file_path:
            return {"success": False, "error": "File path not found in analysis or documents"}

        if not file_path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        # Generate ELA
        result = await self.ela_analyzer.analyze(file_path, quality=quality, scale=scale)

        # Save to database if successful
        if result.get("success") and self._db:
            ela_id = str(uuid.uuid4())
            await self._db.execute(
                """
                INSERT INTO arkham_media_ela (id, analysis_id, quality, interpretation, created_at)
                VALUES (:id, :analysis_id, :quality, :interpretation, :created_at)
                """,
                {
                    "id": ela_id,
                    "analysis_id": analysis_id,
                    "quality": quality,
                    "interpretation": json.dumps(result.get("interpretation", {})),
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

            # Emit event
            if self._event_bus:
                await self._event_bus.emit(
                    "media.ela.generated",
                    {
                        "analysis_id": analysis_id,
                        "ela_id": ela_id,
                        "quality": quality,
                    },
                    source="media-forensics",
                )

        return result

    async def find_similar_images(
        self,
        analysis_id: str,
        hash_type: str = "phash",
        threshold: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find images similar to a given analysis using perceptual hashing.

        Args:
            analysis_id: Source analysis ID
            hash_type: Type of hash to use (phash, dhash, ahash)
            threshold: Maximum Hamming distance

        Returns:
            List of similar images
        """
        if not self.hash_service:
            return []

        analysis = await self.get_analysis(analysis_id)
        if not analysis:
            return []

        target_hash = analysis.get(hash_type)
        if not target_hash:
            return []

        similar = await self.hash_service.find_similar(target_hash, hash_type=hash_type, threshold=threshold)

        # Filter out self
        similar = [s for s in similar if s["analysis_id"] != analysis_id]

        return similar

    async def reverse_image_search(
        self, analysis_id: str, base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform reverse image search using external web APIs or generate search URLs.

        This requires network access for API-based searches.
        Always generates clickable search URLs for manual searching.

        Args:
            analysis_id: Source analysis ID
            base_url: Base URL for constructing image URL (e.g., http://localhost:8100)

        Returns:
            Dict containing search URLs and any API-based results
        """
        analysis = await self.get_analysis(analysis_id)
        if not analysis:
            return {"search_urls": [], "api_results": [], "error": "Analysis not found"}

        file_path = analysis.get("file_path")
        if not file_path:
            return {"search_urls": [], "api_results": [], "error": "No file path in analysis"}

        # Check if file exists
        if not Path(file_path).exists():
            return {"search_urls": [], "api_results": [], "error": "Image file not found"}

        # Generate search URLs for manual reverse image search
        search_urls = await self._generate_search_urls(analysis_id, file_path, base_url)

        # Try API-based searches if configured
        api_results = []

        # Check if we're in offline mode
        offline_mode = False
        if self._frame and hasattr(self._frame, "config"):
            config = self._frame.config
            offline_mode = getattr(config, "offline_mode", False)

        if not offline_mode:
            try:
                import aiohttp

                # Use TinEye API if configured (requires API key)
                tineye_key = os.environ.get("TINEYE_API_KEY")
                if tineye_key:
                    tineye_results = await self._tineye_search(file_path, tineye_key)
                    api_results.extend(tineye_results)

                # Use Google Vision API if configured (requires API key)
                google_key = os.environ.get("GOOGLE_VISION_API_KEY")
                if google_key:
                    google_results = await self._google_vision_search(file_path, google_key)
                    api_results.extend(google_results)

                # Use SerpAPI for Google Reverse Image Search (has free tier)
                serpapi_key = os.environ.get("SERPAPI_KEY")
                if serpapi_key and base_url:
                    serpapi_results = await self._serpapi_search(analysis_id, base_url, serpapi_key)
                    api_results.extend(serpapi_results)

            except ImportError:
                logger.debug("aiohttp not installed - API-based reverse image search unavailable")

        return {
            "search_urls": search_urls,
            "api_results": api_results,
            "has_api_keys": bool(
                os.environ.get("TINEYE_API_KEY") or
                os.environ.get("GOOGLE_VISION_API_KEY") or
                os.environ.get("SERPAPI_KEY")
            ),
        }

    async def _generate_search_urls(
        self, analysis_id: str, file_path: str, base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate URLs for reverse image search engines."""
        search_urls = []

        # If we have a base URL, generate a URL to the served image
        image_url = None
        if base_url:
            # Use the image endpoint to serve the analysis image
            image_url = f"{base_url}/api/media-forensics/image/{analysis_id}"

        # Google Images reverse search (supports URL-based search)
        if image_url:
            google_url = f"https://lens.google.com/uploadbyurl?url={quote(image_url)}"
            search_urls.append({
                "engine": "Google Lens",
                "url": google_url,
                "icon": "search",
                "description": "Search with Google Lens (URL-based)",
                "type": "url_search",
            })

        # Google Images upload page (always available)
        search_urls.append({
            "engine": "Google Images",
            "url": "https://images.google.com/",
            "icon": "image",
            "description": "Upload image to Google Images",
            "type": "upload_search",
            "instructions": "Click the camera icon and upload the image",
        })

        # TinEye (upload-based)
        search_urls.append({
            "engine": "TinEye",
            "url": "https://tineye.com/",
            "icon": "eye",
            "description": "Upload image to TinEye",
            "type": "upload_search",
            "instructions": "Upload the image to search for matches",
        })

        # Yandex Images (supports URL-based search)
        if image_url:
            yandex_url = f"https://yandex.com/images/search?url={quote(image_url)}&rpt=imageview"
            search_urls.append({
                "engine": "Yandex Images",
                "url": yandex_url,
                "icon": "globe",
                "description": "Search with Yandex Images (URL-based)",
                "type": "url_search",
            })

        # Yandex upload page (always available)
        search_urls.append({
            "engine": "Yandex Images",
            "url": "https://yandex.com/images/",
            "icon": "globe",
            "description": "Upload image to Yandex Images",
            "type": "upload_search",
            "instructions": "Click the camera icon and upload the image",
        })

        # Bing Visual Search (URL-based)
        if image_url:
            bing_url = f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{quote(image_url)}"
            search_urls.append({
                "engine": "Bing Visual Search",
                "url": bing_url,
                "icon": "search",
                "description": "Search with Bing Visual Search (URL-based)",
                "type": "url_search",
            })

        return search_urls

    async def _serpapi_search(
        self, analysis_id: str, base_url: str, api_key: str
    ) -> List[Dict[str, Any]]:
        """Search using SerpAPI Google Reverse Image Search."""
        try:
            import aiohttp

            image_url = f"{base_url}/api/media-forensics/image/{analysis_id}"

            params = {
                "engine": "google_reverse_image",
                "image_url": image_url,
                "api_key": api_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []

                        # Process image results
                        for match in data.get("image_results", [])[:10]:
                            results.append({
                                "url": match.get("link"),
                                "domain": match.get("source"),
                                "title": match.get("title", "SerpAPI Match"),
                                "thumbnail_url": match.get("thumbnail"),
                                "similarity_score": 0.75,
                                "source": "serpapi",
                            })

                        # Process inline images
                        for match in data.get("inline_images", [])[:5]:
                            if match.get("link"):
                                results.append({
                                    "url": match.get("link"),
                                    "domain": match.get("source"),
                                    "title": match.get("title", "SerpAPI Match"),
                                    "thumbnail_url": match.get("thumbnail"),
                                    "similarity_score": 0.7,
                                    "source": "serpapi",
                                })

                        return results
                    else:
                        logger.warning(f"SerpAPI search returned status {resp.status}")
        except Exception as e:
            logger.warning(f"SerpAPI search failed: {e}")
        return []

    async def _tineye_search(self, file_path: str, api_key: str) -> List[Dict[str, Any]]:
        """Search TinEye for matching images."""
        try:
            import aiohttp
            import base64

            # Read and encode image
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tineye.com/rest/search/",
                    data={"image": image_data},
                    headers={"x-api-key": api_key},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for match in data.get("matches", [])[:10]:
                            results.append({
                                "url": match.get("backlinks", [{}])[0].get("url"),
                                "domain": match.get("domain"),
                                "title": match.get("backlinks", [{}])[0].get("page_title", "TinEye Match"),
                                "thumbnail_url": match.get("image_url"),
                                "similarity_score": match.get("score", 50) / 100,
                                "source": "tineye",
                            })
                        return results
        except Exception as e:
            logger.warning(f"TinEye search failed: {e}")
        return []

    async def _google_vision_search(self, file_path: str, api_key: str) -> List[Dict[str, Any]]:
        """Search Google Vision for web detection."""
        try:
            import aiohttp
            import base64

            # Read and encode image
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
                    json={
                        "requests": [{
                            "image": {"content": image_data},
                            "features": [{"type": "WEB_DETECTION", "maxResults": 10}],
                        }]
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        web_detection = data.get("responses", [{}])[0].get("webDetection", {})

                        # Pages with matching images
                        for page in web_detection.get("pagesWithMatchingImages", [])[:10]:
                            results.append({
                                "url": page.get("url"),
                                "domain": page.get("url", "").split("/")[2] if page.get("url") else None,
                                "title": page.get("pageTitle", "Google Vision Match"),
                                "thumbnail_url": page.get("fullMatchingImages", [{}])[0].get("url")
                                    if page.get("fullMatchingImages") else None,
                                "similarity_score": 0.8,  # Google doesn't provide score
                                "source": "google_vision",
                            })
                        return results
        except Exception as e:
            logger.warning(f"Google Vision search failed: {e}")
        return []

    async def calculate_sun_position(
        self,
        latitude: float,
        longitude: float,
        dt: datetime,
    ) -> Dict[str, Any]:
        """Calculate sun position for given coordinates and time."""
        if not self.sun_position:
            return {"success": False, "error": "Sun position service not available"}

        return await self.sun_position.calculate_sun_position(latitude, longitude, dt)

    async def get_sun_position_from_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """Calculate sun position from EXIF data of an analyzed image."""
        if not self.sun_position:
            return {"success": False, "error": "Sun position service not available"}

        analysis = await self.get_analysis(analysis_id)
        if not analysis:
            return {"success": False, "error": "Analysis not found"}

        gps_data = {
            "latitude": analysis.get("gps_latitude"),
            "longitude": analysis.get("gps_longitude"),
        }

        timestamp_data = {
            "datetime_original": analysis.get("datetime_original"),
            "datetime_digitized": analysis.get("datetime_digitized"),
            "datetime_modified": analysis.get("datetime_modified"),
        }

        result = await self.sun_position.verify_from_exif(gps_data, timestamp_data)

        # Save to database if successful
        if result.get("success") and self._db:
            sun_id = str(uuid.uuid4())
            await self._db.execute(
                """
                INSERT INTO arkham_media_sun_verification
                (id, analysis_id, claimed_datetime, latitude, longitude,
                 sun_altitude, sun_azimuth, expected_shadow_direction,
                 verification_status, notes, created_at)
                VALUES
                (:id, :analysis_id, :claimed_datetime, :latitude, :longitude,
                 :sun_altitude, :sun_azimuth, :expected_shadow_direction,
                 :verification_status, :notes, :created_at)
                """,
                {
                    "id": sun_id,
                    "analysis_id": analysis_id,
                    "claimed_datetime": result.get("datetime"),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "sun_altitude": result.get("sun_altitude"),
                    "sun_azimuth": result.get("sun_azimuth"),
                    "expected_shadow_direction": result.get("expected_shadow_direction"),
                    "verification_status": "calculated",
                    "notes": result.get("interpretation"),
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        return result

    async def get_stats(self) -> Dict[str, Any]:
        """Get media forensics statistics."""
        if not self._db:
            return {
                "total_analyses": 0,
                "by_status": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
                "by_verification": {"verified": 0, "flagged": 0, "unknown": 0, "tampered": 0},
                "with_c2pa": 0,
                "with_exif": 0,
                "with_gps": 0,
                "with_findings": 0,
                "critical_findings_total": 0,
                "high_findings_total": 0,
                "ela_analyses": 0,
                "sun_position_analyses": 0,
                "similar_images_searches": 0,
                "avg_findings_per_analysis": 0,
            }

        # Initialize with frontend-expected structure
        stats = {
            "total_analyses": 0,
            "by_status": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
            "by_verification": {"verified": 0, "flagged": 0, "unknown": 0, "tampered": 0},
            "with_c2pa": 0,
            "with_exif": 0,
            "with_gps": 0,
            "with_findings": 0,
            "critical_findings_total": 0,
            "high_findings_total": 0,
            "ela_analyses": 0,
            "sun_position_analyses": 0,
            "similar_images_searches": 0,
            "avg_findings_per_analysis": 0.0,
            # Also keep legacy fields for backward compatibility
            "with_warnings": 0,
            "ai_generated_detected": 0,
            "by_integrity_status": {},
            "by_file_type": {},
        }

        try:
            # Total count
            total_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses"
            )
            total = total_row["count"] if total_row else 0
            stats["total_analyses"] = total
            # All records in DB are completed
            stats["by_status"]["completed"] = total

            # With EXIF (camera_make not null)
            exif_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE camera_make IS NOT NULL"
            )
            stats["with_exif"] = exif_row["count"] if exif_row else 0

            # With GPS
            gps_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE gps_latitude IS NOT NULL"
            )
            stats["with_gps"] = gps_row["count"] if gps_row else 0

            # With C2PA
            c2pa_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE has_c2pa = 1"
            )
            stats["with_c2pa"] = c2pa_row["count"] if c2pa_row else 0

            # With warnings/findings
            warnings_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE warnings != '[]'"
            )
            warnings_count = warnings_row["count"] if warnings_row else 0
            stats["with_warnings"] = warnings_count
            stats["with_findings"] = warnings_count

            # AI generated (check warnings for AI_GENERATED)
            ai_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_media_analyses WHERE warnings LIKE '%AI_GENERATED%'"
            )
            stats["ai_generated_detected"] = ai_row["count"] if ai_row else 0

            # By integrity status (maps to by_verification)
            status_rows = await self._db.fetch_all(
                "SELECT integrity_status, COUNT(*) as count FROM arkham_media_analyses GROUP BY integrity_status"
            )
            by_integrity = {row["integrity_status"]: row["count"] for row in status_rows}
            stats["by_integrity_status"] = by_integrity
            # Map to frontend verification status
            stats["by_verification"]["verified"] = by_integrity.get("verified", 0)
            stats["by_verification"]["flagged"] = by_integrity.get("flagged", 0) + by_integrity.get("unverified", 0)
            stats["by_verification"]["unknown"] = by_integrity.get("unknown", 0)
            stats["by_verification"]["tampered"] = by_integrity.get("tampered", 0)

            # By file type
            type_rows = await self._db.fetch_all(
                "SELECT file_type, COUNT(*) as count FROM arkham_media_analyses WHERE file_type IS NOT NULL GROUP BY file_type"
            )
            stats["by_file_type"] = {row["file_type"]: row["count"] for row in type_rows}

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")

        return stats

    # ===========================================
    # Helper Methods
    # ===========================================

    def _row_to_analysis_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a database row to an analysis dictionary."""
        # Parse JSON fields
        raw_exif_data = row.get("exif_data", "{}")
        if isinstance(raw_exif_data, str):
            try:
                raw_exif_data = json.loads(raw_exif_data)
            except json.JSONDecodeError:
                raw_exif_data = {}

        # Structure exif_data to match frontend ExifData type
        exif_data = self._structure_exif_data(raw_exif_data, row)

        raw_c2pa_data = row.get("c2pa_data", "{}")
        if isinstance(raw_c2pa_data, str):
            try:
                raw_c2pa_data = json.loads(raw_c2pa_data)
            except json.JSONDecodeError:
                raw_c2pa_data = {}

        # Transform C2PA data to frontend expected format
        c2pa_data = self._transform_c2pa_for_frontend(raw_c2pa_data)

        warnings = row.get("warnings", "[]")
        if isinstance(warnings, str):
            try:
                warnings = json.loads(warnings)
            except json.JSONDecodeError:
                warnings = []

        anomalies = row.get("anomalies", "[]")
        if isinstance(anomalies, str):
            try:
                anomalies = json.loads(anomalies)
            except json.JSONDecodeError:
                anomalies = []

        # Convert string warnings to ForensicFinding objects for frontend compatibility
        findings = []
        for i, warning in enumerate(warnings if isinstance(warnings, list) else []):
            if isinstance(warning, str):
                # Determine category and severity from warning text
                category = "general"
                severity = "medium"
                if warning.startswith("EXIF_"):
                    category = "exif"
                elif warning.startswith("C2PA_"):
                    category = "c2pa"
                elif warning.startswith("AI_GENERATED"):
                    category = "c2pa"
                    severity = "high"
                elif warning.startswith("TIMESTAMP_"):
                    category = "exif"
                elif warning.startswith("GPS_"):
                    category = "exif"

                findings.append({
                    "id": f"{row['id']}_warning_{i}",
                    "category": category,
                    "severity": severity,
                    "title": warning.split(":")[0] if ":" in warning else warning[:50],
                    "description": warning,
                    "evidence": {},
                    "recommendation": None,
                    "confidence": 0.7,
                    "auto_detected": True,
                    "detected_at": row["created_at"].isoformat() if row.get("created_at") else datetime.utcnow().isoformat(),
                })
            elif isinstance(warning, dict):
                # Already a finding object
                findings.append(warning)

        # Map integrity_status to verification_status for frontend compatibility
        integrity_status = row.get("integrity_status", "unknown")

        # Derive filename from document_id or file path if stored
        filename = row.get("filename")
        if not filename and row.get("document_id"):
            # Use document_id as filename placeholder
            filename = row.get("document_id", "unknown")

        return {
            "id": row["id"],
            "doc_id": row.get("document_id"),  # Frontend expects doc_id
            "document_id": row.get("document_id"),
            "filename": filename,
            "file_path": row.get("file_path"),  # For ELA and other operations
            "tenant_id": row.get("tenant_id"),
            "file_type": row.get("file_type"),
            "file_size": row.get("file_size"),
            "file_hash_md5": row.get("md5"),
            "file_hash_sha256": row.get("sha256"),
            "width": row.get("width"),
            "height": row.get("height"),
            "sha256": row.get("sha256"),
            "md5": row.get("md5"),
            "phash": row.get("phash"),
            "dhash": row.get("dhash"),
            "ahash": row.get("ahash"),
            "exif_data": exif_data,
            "camera_make": row.get("camera_make"),
            "camera_model": row.get("camera_model"),
            "software": row.get("software"),
            "datetime_original": row.get("datetime_original"),
            "datetime_digitized": row.get("datetime_digitized"),
            "datetime_modified": row.get("datetime_modified"),
            "gps_latitude": row.get("gps_latitude"),
            "gps_longitude": row.get("gps_longitude"),
            "gps_altitude": row.get("gps_altitude"),
            "c2pa_data": c2pa_data,
            "has_c2pa": bool(row.get("has_c2pa")),
            "c2pa_signer": row.get("c2pa_signer"),
            "c2pa_timestamp": row.get("c2pa_timestamp"),
            "warnings": warnings,
            "anomalies": anomalies,
            # Status fields for frontend compatibility
            "status": "completed",  # Analysis is always completed when in DB
            "verification_status": integrity_status,
            "integrity_status": integrity_status,
            "confidence_score": row.get("confidence_score", 0.0),
            # Findings fields - properly structured ForensicFinding objects
            "findings": findings,
            "findings_count": len(findings),
            "critical_findings": sum(1 for f in findings if f.get("severity") == "critical"),
            "high_findings": sum(1 for f in findings if f.get("severity") == "high"),
            # Timestamps
            "analyzed_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            "analyzed_by": "system",
            "notes": None,
            # Component results (null by default, populated when requested)
            "ela_result": None,
            "sun_position_result": None,
            "similar_images_result": None,
        }

    def _structure_exif_data(self, raw_exif: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw EXIF data into the structured format expected by the frontend.

        Frontend expects:
        {
            camera: { make, model, serial_number, lens_make, lens_model, lens_serial },
            image: { width, height, orientation, color_space, bits_per_sample, compression },
            gps: { latitude, longitude, altitude, altitude_ref, gps_timestamp, gps_date, direction, direction_ref },
            capture: { exposure_time, f_number, iso, focal_length, focal_length_35mm, exposure_mode, exposure_program, metering_mode, white_balance, flash },
            timestamps: { datetime_original, datetime_digitized, datetime_modified, timezone_offset },
            software: { software, processing_software, host_computer, firmware },
            raw_data: { ... original raw exif ... },
            warnings: [ ... ]
        }
        """
        # Build camera info from raw EXIF or row columns
        camera = {
            "make": row.get("camera_make") or raw_exif.get("Make") or raw_exif.get("Image Make"),
            "model": row.get("camera_model") or raw_exif.get("Model") or raw_exif.get("Image Model"),
            "serial_number": raw_exif.get("SerialNumber") or raw_exif.get("EXIF SerialNumber"),
            "lens_make": raw_exif.get("LensMake") or raw_exif.get("EXIF LensMake"),
            "lens_model": raw_exif.get("LensModel") or raw_exif.get("EXIF LensModel"),
            "lens_serial": raw_exif.get("LensSerialNumber") or raw_exif.get("EXIF LensSerialNumber"),
        }

        # Build image info
        image = {
            "width": row.get("width") or raw_exif.get("EXIF ExifImageWidth") or raw_exif.get("ImageWidth"),
            "height": row.get("height") or raw_exif.get("EXIF ExifImageLength") or raw_exif.get("ImageLength"),
            "orientation": raw_exif.get("Orientation") or raw_exif.get("Image Orientation"),
            "color_space": raw_exif.get("EXIF ColorSpace") or raw_exif.get("ColorSpace"),
            "bits_per_sample": raw_exif.get("BitsPerSample") or raw_exif.get("Image BitsPerSample"),
            "compression": raw_exif.get("Compression") or raw_exif.get("Image Compression"),
        }

        # Build GPS info
        gps = {
            "latitude": row.get("gps_latitude"),
            "longitude": row.get("gps_longitude"),
            "altitude": row.get("gps_altitude"),
            "altitude_ref": raw_exif.get("GPS GPSAltitudeRef"),
            "gps_timestamp": raw_exif.get("GPS GPSTimeStamp"),
            "gps_date": raw_exif.get("GPS GPSDate"),
            "direction": None,  # Would need parsing from GPS GPSImgDirection
            "direction_ref": raw_exif.get("GPS GPSImgDirectionRef"),
        }
        # Try to parse direction
        if raw_exif.get("GPS GPSImgDirection"):
            try:
                direction_str = str(raw_exif.get("GPS GPSImgDirection"))
                if "/" in direction_str:
                    num, den = direction_str.split("/")
                    gps["direction"] = float(num) / float(den)
                else:
                    gps["direction"] = float(direction_str)
            except (ValueError, ZeroDivisionError):
                pass

        # Build capture settings
        capture = {
            "exposure_time": str(raw_exif.get("EXIF ExposureTime")) if raw_exif.get("EXIF ExposureTime") else None,
            "f_number": None,
            "iso": None,
            "focal_length": None,
            "focal_length_35mm": None,
            "exposure_mode": raw_exif.get("EXIF ExposureMode"),
            "exposure_program": raw_exif.get("EXIF ExposureProgram"),
            "metering_mode": raw_exif.get("EXIF MeteringMode"),
            "white_balance": raw_exif.get("EXIF WhiteBalance"),
            "flash": raw_exif.get("EXIF Flash"),
        }
        # Parse numeric values
        if raw_exif.get("EXIF FNumber"):
            try:
                fn_str = str(raw_exif.get("EXIF FNumber"))
                if "/" in fn_str:
                    num, den = fn_str.split("/")
                    capture["f_number"] = round(float(num) / float(den), 1)
                else:
                    capture["f_number"] = float(fn_str)
            except (ValueError, ZeroDivisionError):
                pass
        if raw_exif.get("EXIF ISOSpeedRatings"):
            try:
                capture["iso"] = int(str(raw_exif.get("EXIF ISOSpeedRatings")).split()[0])
            except (ValueError, IndexError):
                pass
        if raw_exif.get("EXIF FocalLength"):
            try:
                fl_str = str(raw_exif.get("EXIF FocalLength"))
                if "/" in fl_str:
                    num, den = fl_str.split("/")
                    capture["focal_length"] = round(float(num) / float(den), 1)
                else:
                    capture["focal_length"] = float(fl_str)
            except (ValueError, ZeroDivisionError):
                pass
        if raw_exif.get("EXIF FocalLengthIn35mmFilm"):
            try:
                capture["focal_length_35mm"] = int(str(raw_exif.get("EXIF FocalLengthIn35mmFilm")))
            except ValueError:
                pass

        # Build timestamps
        timestamps = {
            "datetime_original": row.get("datetime_original") or raw_exif.get("EXIF DateTimeOriginal"),
            "datetime_digitized": row.get("datetime_digitized") or raw_exif.get("EXIF DateTimeDigitized"),
            "datetime_modified": row.get("datetime_modified") or raw_exif.get("DateTime") or raw_exif.get("Image DateTime"),
            "timezone_offset": raw_exif.get("EXIF OffsetTime") or raw_exif.get("OffsetTime"),
        }

        # Build software info
        software = {
            "software": row.get("software") or raw_exif.get("Software") or raw_exif.get("Image Software"),
            "processing_software": raw_exif.get("ProcessingSoftware"),
            "host_computer": raw_exif.get("HostComputer") or raw_exif.get("Image HostComputer"),
            "firmware": raw_exif.get("Firmware") or raw_exif.get("MakerNote FirmwareVersion"),
        }

        # Collect warnings from raw exif (if any embedded warnings)
        warnings = []

        return {
            "camera": camera,
            "image": image,
            "gps": gps,
            "capture": capture,
            "timestamps": timestamps,
            "software": software,
            "raw_data": raw_exif,
            "warnings": warnings,
        }

    def _transform_c2pa_for_frontend(self, raw_c2pa: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform backend C2PA data into the format expected by the frontend.

        Backend stores:
        {
            has_c2pa: bool,
            manifests: ["urn:..."],  # Array of URN strings
            active_manifest: "urn:...",
            signature_valid: bool,
            signer: "Adobe Inc.",
            timestamp: "...",
            actions: [...],
            ingredients: [...],
            claim_generator: "...",
            raw_manifest: {...}  # Full raw manifest data
        }

        Frontend expects:
        {
            has_manifest: bool,
            manifests: C2PAManifest[],  # Array of full manifest objects
            active_manifest_index: number | null,
            validation_status: 'valid' | 'invalid' | 'expired' | 'revoked' | 'unknown',
            validation_errors: string[],
            provenance_chain: string[],
        }
        """
        if not raw_c2pa or not raw_c2pa.get("has_c2pa"):
            return {
                "has_manifest": False,
                "manifests": [],
                "active_manifest_index": None,
                "validation_status": "unknown",
                "validation_errors": [],
                "provenance_chain": [],
            }

        # Build the manifest object from raw data
        manifests = []

        # Get raw manifest data if available
        raw_manifest_store = raw_c2pa.get("raw_manifest", {})
        active_manifest_id = raw_c2pa.get("active_manifest")

        # Determine validation status
        if raw_c2pa.get("signature_valid"):
            validation_status = "valid"
        elif raw_c2pa.get("signature_verification_available") is False:
            # Signature verification not available (no trust anchors)
            validation_status = "unknown"
        else:
            validation_status = "invalid"

        # Build manifest from available data
        manifest = {
            "claim_generator": raw_c2pa.get("claim_generator"),
            "title": None,
            "format": None,
            "instance_id": active_manifest_id,
            "assertions": [],
            "actions": [],
            "ingredients": [],
            "signer": None,
            "signature_date": raw_c2pa.get("timestamp"),
        }

        # Build signer object
        if raw_c2pa.get("signer"):
            manifest["signer"] = {
                "name": raw_c2pa.get("signer"),
                "organization": None,
                "issued_date": None,
                "expiry_date": None,
                "is_trusted": raw_c2pa.get("signature_valid", False),
                "trust_chain": [],
                "validation_status": validation_status,
            }
            # Try to extract organization from signer name
            signer_name = raw_c2pa.get("signer", "")
            if " Inc" in signer_name or " LLC" in signer_name or " Corp" in signer_name:
                manifest["signer"]["organization"] = signer_name

        # Transform actions
        for action in raw_c2pa.get("actions", []):
            if isinstance(action, dict):
                manifest["actions"].append({
                    "action": action.get("action", "unknown"),
                    "when": action.get("when"),
                    "software_agent": action.get("softwareAgent"),
                    "parameters": action.get("parameters", {}),
                })
            elif isinstance(action, str):
                manifest["actions"].append({
                    "action": action,
                    "when": None,
                    "software_agent": None,
                    "parameters": {},
                })

        # Transform ingredients
        for ingredient in raw_c2pa.get("ingredients", []):
            if isinstance(ingredient, dict):
                manifest["ingredients"].append({
                    "title": ingredient.get("title"),
                    "format": ingredient.get("format"),
                    "document_id": ingredient.get("document_id"),
                    "instance_id": ingredient.get("instance_id"),
                    "relationship": ingredient.get("relationship", "componentOf"),
                    "thumbnail": ingredient.get("thumbnail"),
                })

        # Try to get more details from raw_manifest if available
        if raw_manifest_store and "manifests" in raw_manifest_store and active_manifest_id:
            if active_manifest_id in raw_manifest_store["manifests"]:
                full_manifest = raw_manifest_store["manifests"][active_manifest_id]

                # Get title from manifest
                if "title" in full_manifest:
                    manifest["title"] = full_manifest["title"]
                if "format" in full_manifest:
                    manifest["format"] = full_manifest["format"]

                # Get assertions
                for assertion in full_manifest.get("assertions", []):
                    manifest["assertions"].append({
                        "label": assertion.get("label", ""),
                        "data": assertion.get("data", {}),
                        "instance": assertion.get("instance"),
                    })

                # Get signature info
                if "signature_info" in full_manifest:
                    sig_info = full_manifest["signature_info"]
                    if manifest["signer"]:
                        manifest["signer"]["issued_date"] = sig_info.get("time")
                    manifest["signature_date"] = sig_info.get("time")

        manifests.append(manifest)

        # Build provenance chain from ingredient titles
        provenance_chain = []
        for ing in manifest["ingredients"]:
            if ing.get("title"):
                provenance_chain.append(ing["title"])

        return {
            "has_manifest": True,
            "manifests": manifests,
            "active_manifest_index": 0,  # Always first manifest since we only build one
            "validation_status": validation_status,
            "validation_errors": [],
            "provenance_chain": provenance_chain,
        }
