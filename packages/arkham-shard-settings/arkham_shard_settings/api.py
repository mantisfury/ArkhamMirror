"""
Settings Shard - API Endpoints

FastAPI router for settings management.
"""

import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .shard import SettingsShard

try:
    from arkham_frame.auth import current_optional_user
except ImportError:
    async def current_optional_user():
        return None

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

router = APIRouter(prefix="/api/settings", tags=["settings"])


# === Helper to get shard instance ===

def get_shard(request: Request) -> "SettingsShard":
    """Get the settings shard instance from app state."""
    shard = getattr(request.app.state, "settings_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Settings shard not available")
    return shard


# === Request/Response Models ===


class SettingResponse(BaseModel):
    """Response model for a setting."""
    key: str
    value: Any
    default_value: Any
    category: str
    data_type: str
    label: str
    description: str
    requires_restart: bool = False
    is_modified: bool = False
    is_readonly: bool = False
    order: int = 0
    options: List[Dict[str, Any]] = []
    validation: Dict[str, Any] = {}


class SettingUpdateRequest(BaseModel):
    """Request to update a setting."""
    value: Any


class BulkSettingsUpdateRequest(BaseModel):
    """Request to update multiple settings."""
    settings: Dict[str, Any]


class ProfileCreateRequest(BaseModel):
    """Request to create a settings profile."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    settings: Optional[Dict[str, Any]] = None
    use_current: bool = True  # Use current settings if settings not provided


class ProfileResponse(BaseModel):
    """Response model for a profile."""
    id: str
    name: str
    description: str
    settings_count: int
    is_default: bool
    is_builtin: bool
    created_at: str
    updated_at: str


class BackupCreateRequest(BaseModel):
    """Request to create a backup."""
    name: str = ""
    description: str = ""


class BackupResponse(BaseModel):
    """Response model for a backup."""
    id: str
    name: str
    description: str
    settings_count: int
    file_size: int
    created_at: str


class ShardSettingsResponse(BaseModel):
    """Response model for shard settings."""
    shard_name: str
    shard_version: str
    is_enabled: bool
    settings: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    shard: str
    version: str
    settings_count: int


class ValidationResponse(BaseModel):
    """Response model for validation."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    coerced_value: Any = None


# === Endpoints ===


def _check_cloud_api_available() -> bool:
    """Check if a cloud API key is configured for embeddings."""
    import os
    # Check for API keys that would enable cloud embeddings
    return bool(
        os.environ.get("OPENAI_API_KEY") or
        os.environ.get("LLM_API_KEY") or
        os.environ.get("ANTHROPIC_API_KEY")
    )


def _filter_embedding_options(options: list, api_available: bool) -> list:
    """Filter/annotate embedding model options based on API availability."""
    if api_available:
        return options

    # If no API key, mark cloud options as disabled
    filtered = []
    for opt in options:
        if "[CLOUD API]" in opt.get("label", ""):
            # Add disabled flag and warning to cloud options
            filtered.append({
                **opt,
                "disabled": True,
                "disabledReason": "Requires API key (OPENAI_API_KEY or LLM_API_KEY)",
            })
        else:
            filtered.append(opt)
    return filtered


def setting_to_response(setting, cloud_api_available: bool = False) -> SettingResponse:
    """Convert a Setting dataclass to a response model."""
    options = setting.options

    # Apply special filtering for embedding model options
    if setting.key == "advanced.embedding_model":
        options = _filter_embedding_options(options, cloud_api_available)

    return SettingResponse(
        key=setting.key,
        value=setting.value,
        default_value=setting.default_value,
        category=setting.category.value,
        data_type=setting.data_type.value,
        label=setting.label,
        description=setting.description,
        requires_restart=setting.requires_restart,
        is_modified=setting.is_modified,
        is_readonly=setting.is_readonly,
        order=setting.order,
        options=options,
        validation=setting.validation,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)
    settings = await shard.get_all_settings()
    return HealthResponse(
        status="healthy",
        shard="settings",
        version="0.1.0",
        settings_count=len(settings),
    )


@router.get("/count")
async def get_modified_count(request: Request):
    """Get count of modified settings (for badge)."""
    shard = get_shard(request)
    all_settings = await shard.get_all_settings(modified_only=True)
    return {"count": len(all_settings)}


# === Settings CRUD ===


@router.get("/", response_model=List[SettingResponse])
async def list_settings(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in key/label"),
    modified_only: bool = Query(False, description="Only show modified settings"),
):
    """List all settings."""
    shard = get_shard(request)
    settings = await shard.get_all_settings(
        category=category,
        search=search,
        modified_only=modified_only
    )
    cloud_api_available = _check_cloud_api_available()
    return [setting_to_response(s, cloud_api_available) for s in settings]


# === Data Management Endpoints ===
# NOTE: These must be defined BEFORE the /{key:path} catch-all route


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    database_connected: bool
    database_schemas: List[str]
    vector_store_connected: bool
    vector_collections: List[Dict[str, Any]]
    storage_categories: Dict[str, int]
    total_storage_bytes: int


class DataActionResponse(BaseModel):
    """Response for data management actions."""
    success: bool
    message: str
    details: Dict[str, Any] = {}


@router.get("/data/stats", response_model=StorageStatsResponse)
async def get_storage_stats(request: Request):
    """Get storage and database statistics."""
    shard = get_shard(request)
    frame = shard._frame

    # Database info
    db = frame.get_service("database")
    db_connected = await db.is_connected() if db else False
    db_schemas = await db.list_schemas() if db and db_connected else []

    # Vector store info
    vectors = frame.get_service("vectors")
    vector_connected = False
    vector_collections = []
    if vectors:
        try:
            collections = await vectors.list_collections()
            vector_connected = True
            vector_collections = [c.to_dict() for c in collections]
        except Exception:
            vector_connected = False

    # Storage info
    storage = frame.get_service("storage")
    storage_categories = {}
    total_bytes = 0
    if storage:
        try:
            stats = await storage.get_storage_stats()
            storage_categories = stats.by_category
            total_bytes = stats.used_bytes
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            pass

    return StorageStatsResponse(
        database_connected=db_connected,
        database_schemas=db_schemas,
        vector_store_connected=vector_connected,
        vector_collections=vector_collections,
        storage_categories=storage_categories,
        total_storage_bytes=total_bytes,
    )


@router.post("/data/clear-vectors", response_model=DataActionResponse)
async def clear_vector_store(request: Request):
    """Clear all vector embeddings."""
    shard = get_shard(request)
    frame = shard._frame
    vectors = frame.get_service("vectors")

    if not vectors:
        raise HTTPException(status_code=503, detail="Vector service not available")

    try:
        collections = await vectors.list_collections()
        deleted_count = 0
        for coll in collections:
            await vectors.delete_collection(coll.name)
            deleted_count += 1

        return DataActionResponse(
            success=True,
            message=f"Cleared {deleted_count} vector collection(s)",
            details={"collections_deleted": deleted_count},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear vectors: {str(e)}")


# Schemas and tables to preserve on "Clear Database" / "Reset All"
# - arkham_auth: tenants, users, audit_events (organization/auth data)
# - arkham_settings*: user preferences and shard settings
PRESERVED_SCHEMAS = frozenset({"arkham_auth"})
PRESERVED_TABLES = frozenset({
    "arkham_settings",
    "arkham_settings_profiles",
    "arkham_settings_changes",
})


async def _clear_database_tables(db) -> tuple[int, list[str]]:
    """Clear all clearable database tables. Returns (tables_cleared, schemas_processed).
    Preserves arkham_auth (org/tenant/users) and settings tables.
    Includes public so entity and other arkham_* tables there are cleared.
    """
    schemas = list(await db.list_schemas())
    if "public" not in schemas:
        schemas.append("public")
    tables_cleared = 0
    for schema in schemas:
        if schema in PRESERVED_SCHEMAS:
            continue
        tables = await db.fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE'",
            {"schema": schema},
        )
        for table in tables:
            table_name = table["table_name"]
            if table_name in PRESERVED_TABLES:
                continue
            await db.execute(f'TRUNCATE TABLE "{schema}"."{table_name}" CASCADE')
            tables_cleared += 1
    return tables_cleared, schemas


@router.post("/data/clear-database", response_model=DataActionResponse)
async def clear_database(request: Request):
    """Clear all database tables (truncate arkham schemas).
    Preserves: arkham_auth (tenants, users, audit) and settings tables.
    Includes public so entity tables (arkham_entities, etc.) are cleared.
    """
    shard = get_shard(request)
    frame = shard._frame
    db = frame.get_service("database")

    if not db:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        tables_cleared, schemas = await _clear_database_tables(db)
        return DataActionResponse(
            success=True,
            message=f"Cleared {tables_cleared} database table(s)",
            details={"tables_cleared": tables_cleared, "schemas": schemas},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")


@router.post("/data/clear-temp", response_model=DataActionResponse)
async def clear_temp_storage(request: Request):
    """Clear temporary files from storage."""
    shard = get_shard(request)
    frame = shard._frame
    storage = frame.get_service("storage")

    if not storage:
        raise HTTPException(status_code=503, detail="Storage service not available")

    try:
        # Use cleanup_temp_files with max_age_hours=0 to delete all temp files
        files_deleted = await storage.cleanup_temp_files(max_age_hours=0)
        return DataActionResponse(
            success=True,
            message=f"Cleared {files_deleted} temporary file(s)",
            details={"files_deleted": files_deleted},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear temp storage: {str(e)}")


class VectorMaintenanceResponse(BaseModel):
    """Response model for vector maintenance operations."""
    success: bool
    message: str
    operation: str
    details: Dict[str, Any] = {}


class VectorHealthResponse(BaseModel):
    """Response model for vector health check."""
    status: str
    total_vectors: int
    total_collections: int
    collections: List[Dict[str, Any]] = []
    warnings: List[str] = []
    last_reindex: Optional[str] = None
    reindex_in_progress: bool = False


@router.get("/vectors/health", response_model=VectorHealthResponse)
async def get_vector_health(request: Request):
    """Get vector store health status."""
    shard = get_shard(request)
    frame = shard._frame
    vectors = frame.get_service("vectors")
    maintenance = frame.get_service("vector_maintenance")

    if not vectors:
        return VectorHealthResponse(
            status="unavailable",
            total_vectors=0,
            total_collections=0,
            warnings=["Vector service not available"],
        )

    try:
        collections = await vectors.list_collections()
        total_vectors = 0
        collection_data = []

        for coll in collections:
            info = await vectors.get_collection_info(coll.name if hasattr(coll, 'name') else coll)
            coll_vectors = info.vector_count if hasattr(info, 'vector_count') else 0
            total_vectors += coll_vectors
            collection_data.append({
                "name": info.name if hasattr(info, 'name') else str(coll),
                "vector_count": coll_vectors,
                "vector_size": info.vector_size if hasattr(info, 'vector_size') else 0,
                "index_type": info.index_type if hasattr(info, 'index_type') else "unknown",
                "lists": info.lists if hasattr(info, 'lists') else 0,
                "probes": info.probes if hasattr(info, 'probes') else 0,
                "last_reindex": info.last_reindex.isoformat() if hasattr(info, 'last_reindex') and info.last_reindex else None,
            })

        # Get maintenance status if available
        last_reindex = None
        reindex_in_progress = False
        if maintenance:
            status = maintenance.get_status()
            last_reindex = status.get("last_reindex")
            reindex_in_progress = status.get("reindex_in_progress", False)

        return VectorHealthResponse(
            status="healthy",
            total_vectors=total_vectors,
            total_collections=len(collections),
            collections=collection_data,
            warnings=[],
            last_reindex=last_reindex,
            reindex_in_progress=reindex_in_progress,
        )

    except Exception as e:
        return VectorHealthResponse(
            status="error",
            total_vectors=0,
            total_collections=0,
            warnings=[f"Failed to get vector health: {str(e)}"],
        )


@router.post("/vectors/reindex", response_model=VectorMaintenanceResponse)
async def trigger_reindex_all(request: Request):
    """
    Trigger manual reindex of all vector collections.

    This rebuilds all IVFFlat indexes with optimal parameters based on
    current data distribution. Use after significant data changes.
    """
    shard = get_shard(request)
    frame = shard._frame
    maintenance = frame.get_service("vector_maintenance")

    if not maintenance:
        # Fallback to vectors service directly
        vectors = frame.get_service("vectors")
        if not vectors:
            raise HTTPException(status_code=503, detail="Vector service not available")

        try:
            result = await vectors.reindex_all()
            return VectorMaintenanceResponse(
                success=result.get("success", True),
                message=f"Reindexed {result.get('collections_reindexed', 0)} collection(s)",
                operation="reindex_all",
                details=result,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")

    try:
        result = await maintenance.reindex_all()
        return VectorMaintenanceResponse(
            success=result.get("success", False),
            message=f"Reindexed {result.get('collections_reindexed', 0)} collection(s)",
            operation="reindex_all",
            details=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")


@router.post("/vectors/reindex/{collection_name}", response_model=VectorMaintenanceResponse)
async def trigger_reindex_collection(collection_name: str, request: Request):
    """
    Trigger manual reindex of a specific vector collection.

    Args:
        collection_name: Name of the collection to reindex
    """
    shard = get_shard(request)
    frame = shard._frame
    maintenance = frame.get_service("vector_maintenance")

    if not maintenance:
        vectors = frame.get_service("vectors")
        if not vectors:
            raise HTTPException(status_code=503, detail="Vector service not available")

        try:
            result = await vectors.reindex_collection(collection_name)
            return VectorMaintenanceResponse(
                success=True,
                message=f"Reindexed collection '{collection_name}'",
                operation="reindex_collection",
                details=result,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")

    try:
        result = await maintenance.reindex_collection(collection_name)
        return VectorMaintenanceResponse(
            success=result.get("success", False),
            message=f"Reindexed collection '{collection_name}'",
            operation="reindex_collection",
            details=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")


@router.get("/vectors/reindex/history")
async def get_reindex_history(request: Request, limit: int = Query(20, ge=1, le=100)):
    """Get history of reindex operations."""
    shard = get_shard(request)
    frame = shard._frame
    maintenance = frame.get_service("vector_maintenance")

    if not maintenance:
        return {"history": [], "message": "Maintenance service not available"}

    return {"history": maintenance.get_reindex_history(limit=limit)}


@router.post("/data/reset-all", response_model=DataActionResponse)
async def reset_all_data(request: Request):
    """Reset all data - database, vectors, and temp files."""
    shard = get_shard(request)
    frame = shard._frame

    results = {
        "database": {"success": False, "message": "Not attempted"},
        "vectors": {"success": False, "message": "Not attempted"},
        "temp_storage": {"success": False, "message": "Not attempted"},
    }

    # Clear database (same logic as clear-database: preserve auth + settings, include public for entities)
    db = frame.get_service("database")
    if db:
        try:
            tables_cleared, _ = await _clear_database_tables(db)
            results["database"] = {"success": True, "message": f"Cleared {tables_cleared} tables"}
        except Exception as e:
            results["database"] = {"success": False, "message": str(e)}

    # Clear vectors
    vectors = frame.get_service("vectors")
    if vectors:
        try:
            collections = await vectors.list_collections()
            for coll in collections:
                await vectors.delete_collection(coll.name)
            results["vectors"] = {"success": True, "message": f"Cleared {len(collections)} collections"}
        except Exception as e:
            results["vectors"] = {"success": False, "message": str(e)}

    # Clear temp storage
    storage = frame.get_service("storage")
    if storage:
        try:
            # Use cleanup_temp_files with max_age_hours=0 to delete all temp files
            files_deleted = await storage.cleanup_temp_files(max_age_hours=0)
            results["temp_storage"] = {"success": True, "message": f"Cleared {files_deleted} files"}
        except Exception as e:
            results["temp_storage"] = {"success": False, "message": str(e)}

    all_success = all(r["success"] for r in results.values() if r["message"] != "Not attempted")

    return DataActionResponse(
        success=all_success,
        message="Data reset completed" if all_success else "Some operations failed",
        details=results,
    )


# === ML Model Management Endpoints ===
# NOTE: These must be defined BEFORE the /{key:path} catch-all route


class ModelInfoResponse(BaseModel):
    """Response model for ML model information."""
    id: str
    name: str
    model_type: str
    description: str
    size_mb: float
    status: str
    path: Optional[str] = None
    error: Optional[str] = None
    required_by: List[str] = []
    is_default: bool = False
    is_selected: bool = False  # Currently active/selected model


class ModelsListResponse(BaseModel):
    """Response for listing all models."""
    offline_mode: bool
    cache_path: str
    models: List[ModelInfoResponse]
    selected_embedding_model: Optional[str] = None  # Currently selected embedding model ID
    selected_ocr_model: Optional[str] = None  # Currently selected OCR model (language)


class ModelDownloadResponse(BaseModel):
    """Response for model download action."""
    success: bool
    message: str
    model: Optional[ModelInfoResponse] = None


@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    request: Request,
    model_type: Optional[str] = Query(None, description="Filter by type: embedding, ocr, vision"),
):
    """
    List all available ML models and their installation status.

    Use this to check which models are installed for air-gap deployments.
    """
    shard = get_shard(request)
    frame = shard._frame
    models_service = frame.get_service("models")

    if not models_service:
        raise HTTPException(status_code=503, detail="Model service not available")

    # Filter by type if specified
    type_filter = None
    if model_type:
        from arkham_frame.services.models import ModelType
        try:
            type_filter = ModelType(model_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_type: {model_type}. Must be: embedding, ocr, vision"
            )

    models = models_service.list_models(model_type=type_filter)

    # Get currently selected models from settings
    selected_embedding = None
    selected_ocr = "paddleocr-en"  # Default OCR model
    try:
        embed_setting = await shard.get_setting("advanced.embedding_model")
        if embed_setting and embed_setting.value:
            # Map HuggingFace path to our model ID
            embed_value = embed_setting.value
            model_id_map = {
                "sentence-transformers/all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2": "all-mpnet-base-v2",
                "BAAI/bge-m3": "bge-m3",
                "BAAI/bge-large-en-v1.5": "bge-large-en-v1.5",
                "sentence-transformers/multi-qa-MiniLM-L6-cos-v1": "multi-qa-MiniLM-L6-cos-v1",
                "sentence-transformers/paraphrase-MiniLM-L6-v2": "paraphrase-MiniLM-L6-v2",
            }
            selected_embedding = model_id_map.get(embed_value, embed_value)
    except Exception:
        pass  # Use defaults if settings unavailable

    return ModelsListResponse(
        offline_mode=models_service.offline_mode,
        cache_path=models_service.cache_path or "",
        selected_embedding_model=selected_embedding,
        selected_ocr_model=selected_ocr,
        models=[
            ModelInfoResponse(
                id=m.id,
                name=m.name,
                model_type=m.model_type.value,
                description=m.description,
                size_mb=m.size_mb,
                status=m.status.value,
                path=m.path,
                error=m.error,
                required_by=m.required_by,
                is_default=m.is_default,
                is_selected=(
                    (m.model_type.value == "embedding" and m.id == selected_embedding) or
                    (m.model_type.value == "ocr" and m.id == selected_ocr)
                ),
            )
            for m in models
        ],
    )


@router.get("/models/{model_id}", response_model=ModelInfoResponse)
async def get_model_status(model_id: str, request: Request):
    """Get the status of a specific ML model."""
    shard = get_shard(request)
    frame = shard._frame
    models_service = frame.get_service("models")

    if not models_service:
        raise HTTPException(status_code=503, detail="Model service not available")

    model = models_service.get_model_status(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")

    return ModelInfoResponse(
        id=model.id,
        name=model.name,
        model_type=model.model_type.value,
        description=model.description,
        size_mb=model.size_mb,
        status=model.status.value,
        path=model.path,
        error=model.error,
        required_by=model.required_by,
        is_default=model.is_default,
    )


@router.post("/models/{model_id}/download", response_model=ModelDownloadResponse)
async def download_model(model_id: str, request: Request):
    """
    Download an ML model.

    This triggers an on-demand download of the specified model.
    Will fail if offline mode is enabled (ARKHAM_OFFLINE_MODE=true).
    """
    shard = get_shard(request)
    frame = shard._frame
    models_service = frame.get_service("models")

    if not models_service:
        raise HTTPException(status_code=503, detail="Model service not available")

    if models_service.offline_mode:
        raise HTTPException(
            status_code=400,
            detail="Cannot download models in offline mode. Disable ARKHAM_OFFLINE_MODE or pre-cache models."
        )

    try:
        model = await models_service.download_model(model_id)
        return ModelDownloadResponse(
            success=True,
            message=f"Successfully downloaded model: {model_id}",
            model=ModelInfoResponse(
                id=model.id,
                name=model.name,
                model_type=model.model_type.value,
                description=model.description,
                size_mb=model.size_mb,
                status=model.status.value,
                path=model.path,
                error=model.error,
                required_by=model.required_by,
                is_default=model.is_default,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/models/offline-status")
async def get_offline_status(request: Request):
    """
    Get the current offline/air-gap mode status.

    Returns information about whether the system is in offline mode
    and which models are available for use.
    """
    shard = get_shard(request)
    frame = shard._frame
    models_service = frame.get_service("models")
    config = frame.get_service("config")

    offline_mode = config.offline_mode if config else False

    if not models_service:
        return {
            "offline_mode": offline_mode,
            "models_service_available": False,
            "message": "Model service not initialized",
        }

    models = models_service.list_models()
    installed = [m for m in models if m.status.value == "installed"]
    not_installed = [m for m in models if m.status.value == "not_installed"]

    return {
        "offline_mode": offline_mode,
        "models_service_available": True,
        "cache_path": models_service.cache_path,
        "total_models": len(models),
        "installed_count": len(installed),
        "not_installed_count": len(not_installed),
        "installed_models": [m.id for m in installed],
        "missing_models": [m.id for m in not_installed],
        "ready_for_airgap": len(not_installed) == 0 or offline_mode,
    }


# === Individual Setting Operations ===
# NOTE: /{key:path} is a catch-all route - must come AFTER specific routes


@router.get("/{key:path}", response_model=SettingResponse)
async def get_setting(key: str, request: Request):
    """Get a specific setting by key."""
    shard = get_shard(request)
    setting = await shard.get_setting(key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
    cloud_api_available = _check_cloud_api_available()
    return setting_to_response(setting, cloud_api_available)


@router.put("/{key:path}", response_model=SettingResponse)
async def update_setting(key: str, body: SettingUpdateRequest, request: Request):
    """Update a setting value."""
    with log_operation("settings.update", setting_key=key) as event:
        try:
            if event:
                event.context("shard", "settings")
                event.context("operation", "update")
                event.input(setting_key=key, has_value=body.value is not None)

            shard = get_shard(request)
            setting = await shard.update_setting(key, body.value)

            if not setting:
                raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

            cloud_api_available = _check_cloud_api_available()

            if event:
                event.output(
                    setting_key=key,
                    category=setting.category,
                    requires_restart=setting.requires_restart,
                )

            return setting_to_response(setting, cloud_api_available)
        except ValueError as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            if event:
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
            raise


@router.delete("/{key:path}", response_model=SettingResponse)
async def reset_setting(key: str, request: Request):
    """Reset a setting to its default value."""
    shard = get_shard(request)
    try:
        setting = await shard.reset_setting(key)
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
        cloud_api_available = _check_cloud_api_available()
        return setting_to_response(setting, cloud_api_available)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Category Operations ===


@router.get("/category/{category}", response_model=List[SettingResponse])
async def get_category_settings(category: str, request: Request):
    """Get all settings in a category."""
    shard = get_shard(request)
    settings = await shard.get_category_settings(category)
    cloud_api_available = _check_cloud_api_available()
    return [setting_to_response(s, cloud_api_available) for s in settings]


@router.put("/category/{category}")
async def update_category_settings(
    category: str,
    body: BulkSettingsUpdateRequest,
    request: Request,
):
    """Bulk update settings in a category."""
    shard = get_shard(request)
    updated = await shard.update_category_settings(category, body.settings)
    return {
        "success": True,
        "category": category,
        "updated_count": len(updated),
    }


# === Profiles ===


@router.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles():
    """List all settings profiles."""
    # Stub: return empty list
    return []


@router.post("/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(request: ProfileCreateRequest):
    """Create a new settings profile."""
    import uuid
    from datetime import datetime

    return ProfileResponse(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        settings_count=len(request.settings) if request.settings else 0,
        is_default=False,
        is_builtin=False,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str):
    """Get a profile by ID."""
    raise HTTPException(status_code=404, detail="Profile not found")


@router.put("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: str, request: ProfileCreateRequest):
    """Update a profile."""
    raise HTTPException(status_code=404, detail="Profile not found")


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a profile."""
    return {"deleted": True, "profile_id": profile_id}


@router.post("/profiles/{profile_id}/apply")
async def apply_profile(profile_id: str):
    """Apply a settings profile."""
    # Stub: return success
    return {
        "success": True,
        "profile_id": profile_id,
        "applied_count": 0,
    }


# === Shard Settings ===


@router.get("/shards", response_model=List[ShardSettingsResponse])
async def list_shard_settings():
    """List settings for all shards."""
    # Stub: return empty list
    return []


@router.get("/shards/{shard_name}", response_model=ShardSettingsResponse)
async def get_shard_settings(shard_name: str):
    """Get settings for a specific shard."""
    raise HTTPException(status_code=404, detail=f"Shard not found: {shard_name}")


@router.put("/shards/{shard_name}", response_model=ShardSettingsResponse)
async def update_shard_settings(
    shard_name: str,
    request: BulkSettingsUpdateRequest,
):
    """Update settings for a shard."""
    raise HTTPException(status_code=404, detail=f"Shard not found: {shard_name}")


@router.delete("/shards/{shard_name}")
async def reset_shard_settings(shard_name: str):
    """Reset shard settings to defaults."""
    return {
        "reset": True,
        "shard_name": shard_name,
    }


# === Backup/Restore ===


@router.get("/backups", response_model=List[BackupResponse])
async def list_backups():
    """List all settings backups."""
    # Stub: return empty list
    return []


@router.post("/backup", response_model=BackupResponse, status_code=201)
async def create_backup(request: BackupCreateRequest):
    """Create a settings backup."""
    if not _storage:
        raise HTTPException(
            status_code=503,
            detail="Storage service not available for backups",
        )

    import uuid
    from datetime import datetime

    return BackupResponse(
        id=str(uuid.uuid4()),
        name=request.name or f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        description=request.description,
        settings_count=0,
        file_size=0,
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/backups/{backup_id}", response_model=BackupResponse)
async def get_backup(backup_id: str):
    """Get a backup by ID."""
    raise HTTPException(status_code=404, detail="Backup not found")


@router.post("/restore/{backup_id}")
async def restore_backup(backup_id: str):
    """Restore settings from a backup."""
    # Stub: return success
    return {
        "success": True,
        "backup_id": backup_id,
        "restored_count": 0,
    }


@router.delete("/backups/{backup_id}")
async def delete_backup(backup_id: str):
    """Delete a backup."""
    return {"deleted": True, "backup_id": backup_id}


# === Export/Import ===


@router.get("/export")
async def export_settings(
    include_profiles: bool = Query(True, description="Include profiles in export"),
):
    """Export all settings as JSON."""
    from datetime import datetime

    return {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "settings": {},
        "profiles": [] if include_profiles else None,
    }


@router.post("/import")
async def import_settings(
    data: Dict[str, Any],
    merge: bool = Query(True, description="Merge with existing settings"),
):
    """Import settings from JSON."""
    return {
        "success": True,
        "imported_count": 0,
        "profiles_imported": 0,
        "merge": merge,
    }


# === Validation ===


class ValidateRequest(BaseModel):
    """Request to validate a setting."""
    key: str
    value: Any


@router.post("/validate", response_model=ValidationResponse)
async def validate_setting(body: ValidateRequest, request: Request):
    """Validate a setting value without saving."""
    shard = get_shard(request)
    result = await shard.validate_setting(body.key, body.value)
    return ValidationResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
        coerced_value=result.coerced_value,
    )
