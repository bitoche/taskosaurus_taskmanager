from fastapi import APIRouter

router = APIRouter()


@router.get("/check_updates")
async def check_remote_db_for_updates():
    """Stub for legacy remote DB checks. With PostgreSQL, DB is always centralized and in sync."""
    return {"updates": False, "status": "ok", "engine": "postgresql"}


@router.get("/sync_download")
@router.post("/sync_download")
async def sync_download():
    """Stub for legacy sync download."""
    return {"status": "ok", "message": "PostgreSQL is always in sync"}


@router.get("/sync_upload")
@router.post("/sync_upload")
async def sync_upload():
    """Stub for legacy sync upload."""
    return {"status": "ok", "message": "PostgreSQL is always in sync"}
