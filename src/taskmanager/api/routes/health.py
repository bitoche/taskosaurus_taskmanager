"""Эндпоинты проверки работоспособности (Health check) и версии сервиса."""

from fastapi import APIRouter, status

from taskmanager.core.config import settings

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Проверка работоспособности сервиса",
    description="Используется для liveness/readiness проб в Docker и Kubernetes.",
    response_description="Статус доступности сервиса",
)
async def health_check() -> dict[str, str]:
    """Возвращает статус доступности сервиса и текущую версию.

    Returns:
        Словарь со статусом 'ok' и версией сервиса.
    """
    return {"status": "ok", "version": settings.app_version}


@router.get(
    "/version",
    status_code=status.HTTP_200_OK,
    summary="Версия сервиса",
    description="Возвращает текущую версию сервиса.",
    response_description="Версия сервиса",
)
async def get_version() -> dict[str, str]:
    """Возвращает текущую версию сервиса.

    Returns:
        Словарь с версией сервиса.
    """
    return {"version": settings.app_version}
