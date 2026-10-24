"""Эндпоинт проверки работоспособности (Health check) сервиса."""

from fastapi import APIRouter, status

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Проверка работоспособности сервиса",
    description="Используется для liveness/readiness проб в Docker и Kubernetes.",
    response_description="Статус доступности сервиса",
)
async def health_check() -> dict[str, str]:
    """Возвращает статус доступности сервиса.

    Returns:
        Словарь со статусом 'ok'.
    """
    return {"status": "ok"}
