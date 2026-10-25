"""Маршруты-заглушки для обратной совместимости со старыми механизмами синхронизации.

В оригинальном приложении DuckDB синхронизировался через Яндекс.Диск.
При использовании централизованной PostgreSQL данные всегда находятся
в актуальном состоянии. Эндпоинты помечены как deprecated и возвращают
успешные безопасные ответы для обеспечения обратной совместимости.
"""

from fastapi import APIRouter, status

router = APIRouter()


@router.get(
    "/check_updates",
    status_code=status.HTTP_200_OK,
    summary="Проверка удаленных обновлений базы данных (устарело)",
    description="Заглушка обратной совместимости. База данных PostgreSQL централизована и актуальна.",
    deprecated=True,
)
@router.get(
    "/check_updates/",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
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
    description="Заглушка обратной совместимости. Синхронизация файлов не требуется.",
    deprecated=True,
)
@router.get(
    "/sync_download/",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.post(
    "/sync_download",
    status_code=status.HTTP_200_OK,
    summary="Скачивание базы (устарело)",
    description="Заглушка обратной совместимости. Синхронизация файлов не требуется.",
    deprecated=True,
)
@router.post(
    "/sync_download/",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def sync_download() -> dict[str, str]:
    """Обрабатывает вызов скачивания копии базы."""
    return {"status": "ok", "message": "Синхронизация не требуется (PostgreSQL)."}


@router.get(
    "/sync_upload",
    status_code=status.HTTP_200_OK,
    summary="Выгрузка базы (устарело)",
    description="Заглушка обратной совместимости. Синхронизация файлов не требуется.",
    deprecated=True,
)
@router.get(
    "/sync_upload/",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.post(
    "/sync_upload",
    status_code=status.HTTP_200_OK,
    summary="Выгрузка базы (устарело)",
    description="Заглушка обратной совместимости. Синхронизация файлов не требуется.",
    deprecated=True,
)
@router.post(
    "/sync_upload/",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def sync_upload() -> dict[str, str]:
    """Обрабатывает вызов выгрузки копии базы."""
    return {"status": "ok", "message": "Синхронизация не требуется (PostgreSQL)."}
