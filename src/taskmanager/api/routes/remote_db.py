"""Маршруты-заглушки для обратной совместимости со старыми механизмами синхронизации.

В оригинальном приложении DuckDB синхронизировался через Яндекс.Диск.
При использовании централизованной PostgreSQL данные всегда находятся
в актуальном состоянии, и эти эндпоинты возвращают успешные ответы для webui.
"""

from fastapi import APIRouter, status

router = APIRouter()


@router.get(
    "/check_updates",
    status_code=status.HTTP_200_OK,
    summary="Проверка удаленных обновлений базы данных",
    description="Заглушка для webui. Сообщает, что локальная база всегда актуальна.",
)
async def check_remote_db_for_updates() -> dict[str, bool | str]:
    """Проверяет наличие обновлений базы данных.

    Returns:
        Словарь с флагом updates: False и статусом ok.
    """
    return {
        "updates": False,
        "status": "ok",
        "engine": "postgresql",
        "message": "База данных PostgreSQL централизована и всегда синхронизирована.",
    }


@router.get(
    "/sync_download",
    status_code=status.HTTP_200_OK,
    summary="Скачивание базы (устарело)",
    description="Заглушка для кнопки синхронизации в интерфейсе.",
)
@router.post(
    "/sync_download",
    status_code=status.HTTP_200_OK,
    summary="Скачивание базы (устарело)",
    description="Заглушка для кнопки синхронизации в интерфейсе.",
)
async def sync_download() -> dict[str, str]:
    """Обрабатывает вызов скачивания копии базы."""
    return {"status": "ok", "message": "Синхронизация не требуется (PostgreSQL)."}


@router.get(
    "/sync_upload",
    status_code=status.HTTP_200_OK,
    summary="Выгрузка базы (устарело)",
    description="Заглушка для кнопки выгрузки в интерфейсе.",
)
@router.post(
    "/sync_upload",
    status_code=status.HTTP_200_OK,
    summary="Выгрузка базы (устарело)",
    description="Заглушка для кнопки выгрузки в интерфейсе.",
)
async def sync_upload() -> dict[str, str]:
    """Обрабатывает вызов выгрузки копии базы."""
    return {"status": "ok", "message": "Синхронизация не требуется (PostgreSQL)."}
