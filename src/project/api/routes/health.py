from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Liveness / readiness probe."""
    return {"status": "ok"}
