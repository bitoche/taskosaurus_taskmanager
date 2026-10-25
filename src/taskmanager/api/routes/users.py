"""Маршруты API управления пользователями, сессиями и резервным копированием (экспорт/импорт)."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.api.dependencies import (
    get_current_admin,
    get_current_user,
    get_data_transfer_service,
)
from taskmanager.core.database import get_session
from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import Task, User
from taskmanager.schemas import ImportSummary, UserAdminRead, UserDataExport
from taskmanager.services.data_transfer_service import DataTransferService

router = APIRouter()


@router.get(
    "",
    response_model=list[UserAdminRead],
    status_code=status.HTTP_200_OK,
    summary="Список пользователей (только для админа)",
    description="Возвращает список всех зарегистрированных пользователей со статистикой задач.",
)
async def list_users(
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Sequence[UserAdminRead]:
    """Получение списка пользователей с подсчетом задач."""
    stmt = (
        select(
            User,
            func.count(Task.task_id).label("tasks_count"),
        )
        .outerjoin(Task, User.user_id == Task.user_id)
        .group_by(User.user_id)
        .order_by(User.user_id.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    user_list = []
    for user_obj, count in rows:
        item = UserAdminRead(
            user_id=user_obj.user_id,
            username=user_obj.username,
            email=user_obj.email,
            role=user_obj.role,
            is_active=user_obj.is_active,
            token_version=user_obj.token_version,
            created_at=user_obj.created_at,
            tasks_count=count,
        )
        user_list.append(item)
    return user_list


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя (только для админа)",
    description="Удаляет учетную запись пользователя и каскадно очищает все его задачи, теги и приоритеты.",
)
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Удаление пользователя."""
    if current_admin.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить собственный административный аккаунт",
        )

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )

    await session.delete(user)
    await session.commit()


@router.post(
    "/{user_id}/revoke-sessions",
    status_code=status.HTTP_200_OK,
    summary="Сбросить все сессии пользователя (только для админа)",
    description="Инвалидирует все активные JWT-токены и cookie пользователя.",
)
async def revoke_user_sessions(
    user_id: int,
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str | int]:
    """Инвалидация сессий целевого пользователя."""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )

    user.token_version += 1
    await session.commit()
    return {
        "message": f"Все активные сессии пользователя '{user.username}' успешно отозваны",
        "token_version": user.token_version,
    }


# ── Экспорт и Импорт данных ──────────────────────────────────────────────────


@router.get(
    "/me/export",
    response_model=UserDataExport,
    status_code=status.HTTP_200_OK,
    summary="Экспорт данных текущего пользователя",
    description="Выгружает полный JSON-дамп задач, тегов, комментариев и приоритетов текущего пользователя.",
)
async def export_my_data(
    current_user: User = Depends(get_current_user),
    service: DataTransferService = Depends(get_data_transfer_service),
) -> UserDataExport:
    """Экспорт своих данных."""
    return await service.export_data(current_user.user_id)


@router.post(
    "/me/import",
    response_model=ImportSummary,
    status_code=status.HTTP_200_OK,
    summary="Импорт данных текущего пользователя",
    description="Загружает задачи, теги, комментарии и приоритеты в аккаунт текущего пользователя.",
)
async def import_my_data(
    body: UserDataExport,
    current_user: User = Depends(get_current_user),
    service: DataTransferService = Depends(get_data_transfer_service),
) -> ImportSummary:
    """Импорт своих данных."""
    return await service.import_data(current_user.user_id, body)


@router.get(
    "/{user_id}/export",
    response_model=UserDataExport,
    status_code=status.HTTP_200_OK,
    summary="Экспорт данных любого пользователя (только для админа)",
    description="Администратор может выгрузить полный дамп задач и настроек любого пользователя.",
)
async def export_user_data_by_admin(
    user_id: int,
    _admin: User = Depends(get_current_admin),
    service: DataTransferService = Depends(get_data_transfer_service),
) -> UserDataExport:
    """Экспорт данных пользователя администратором."""
    try:
        return await service.export_data(user_id)
    except EntityNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message) from err


@router.post(
    "/{user_id}/import",
    response_model=ImportSummary,
    status_code=status.HTTP_200_OK,
    summary="Импорт данных в аккаунт любого пользователя (только для админа)",
    description="Администратор может загрузить задачи и настройки в профиль любого пользователя.",
)
async def import_user_data_by_admin(
    user_id: int,
    body: UserDataExport,
    _admin: User = Depends(get_current_admin),
    service: DataTransferService = Depends(get_data_transfer_service),
) -> ImportSummary:
    """Импорт данных в пользователя администратором."""
    try:
        return await service.import_data(user_id, body)
    except EntityNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message) from err
