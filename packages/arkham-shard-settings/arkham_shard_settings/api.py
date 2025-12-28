"""
Settings Shard - API Endpoints

FastAPI router for settings management.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .shard import SettingsShard

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


def setting_to_response(setting) -> SettingResponse:
    """Convert a Setting dataclass to a response model."""
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
        options=setting.options,
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
    return [setting_to_response(s) for s in settings]


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
            stats = await storage.get_stats()
            storage_categories = stats.get("by_category", {})
            total_bytes = stats.get("used_bytes", 0)
        except Exception:
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


@router.post("/data/clear-database", response_model=DataActionResponse)
async def clear_database(request: Request):
    """Clear all database tables (truncate arkham schemas)."""
    shard = get_shard(request)
    frame = shard._frame
    db = frame.get_service("database")

    if not db:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get all arkham schemas
        schemas = await db.list_schemas()
        tables_cleared = 0

        for schema in schemas:
            # Get tables in this schema
            tables = await db.fetch_all(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_type = 'BASE TABLE'",
                {"schema": schema}
            )

            for table in tables:
                table_name = table["table_name"]
                # Skip settings tables to preserve user preferences
                if table_name in ("settings", "settings_profiles"):
                    continue
                await db.execute(f'TRUNCATE TABLE "{schema}"."{table_name}" CASCADE')
                tables_cleared += 1

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
        files_deleted = await storage.cleanup_temp(force=True)
        return DataActionResponse(
            success=True,
            message=f"Cleared {files_deleted} temporary file(s)",
            details={"files_deleted": files_deleted},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear temp storage: {str(e)}")


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

    # Clear database
    db = frame.get_service("database")
    if db:
        try:
            schemas = await db.list_schemas()
            tables_cleared = 0
            for schema in schemas:
                tables = await db.fetch_all(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_type = 'BASE TABLE'",
                    {"schema": schema}
                )
                for table in tables:
                    table_name = table["table_name"]
                    if table_name in ("settings", "settings_profiles"):
                        continue
                    await db.execute(f'TRUNCATE TABLE "{schema}"."{table_name}" CASCADE')
                    tables_cleared += 1
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
            files_deleted = await storage.cleanup_temp(force=True)
            results["temp_storage"] = {"success": True, "message": f"Cleared {files_deleted} files"}
        except Exception as e:
            results["temp_storage"] = {"success": False, "message": str(e)}

    all_success = all(r["success"] for r in results.values() if r["message"] != "Not attempted")

    return DataActionResponse(
        success=all_success,
        message="Data reset completed" if all_success else "Some operations failed",
        details=results,
    )


# === Individual Setting Operations ===
# NOTE: /{key:path} is a catch-all route - must come AFTER specific routes


@router.get("/{key:path}", response_model=SettingResponse)
async def get_setting(key: str, request: Request):
    """Get a specific setting by key."""
    shard = get_shard(request)
    setting = await shard.get_setting(key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
    return setting_to_response(setting)


@router.put("/{key:path}", response_model=SettingResponse)
async def update_setting(key: str, body: SettingUpdateRequest, request: Request):
    """Update a setting value."""
    shard = get_shard(request)
    try:
        setting = await shard.update_setting(key, body.value)
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
        return setting_to_response(setting)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{key:path}", response_model=SettingResponse)
async def reset_setting(key: str, request: Request):
    """Reset a setting to its default value."""
    shard = get_shard(request)
    try:
        setting = await shard.reset_setting(key)
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
        return setting_to_response(setting)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Category Operations ===


@router.get("/category/{category}", response_model=List[SettingResponse])
async def get_category_settings(category: str, request: Request):
    """Get all settings in a category."""
    shard = get_shard(request)
    settings = await shard.get_category_settings(category)
    return [setting_to_response(s) for s in settings]


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
