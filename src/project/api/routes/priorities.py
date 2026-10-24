"""Маршруты API для управления приоритетами задач."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import TaskPriority
from project.schemas import PriorityCreate, PriorityRead, PriorityUpdate
from project.services.priority_service import PriorityService

router = APIRouter()


def get_priority_service(
    session: AsyncSession = Depends(get_session),
) -> PriorityService:
    """Внедрение зависимости сервиса приоритетов.

    Args:
        session: Сессия SQLAlchemy из контекста запроса.

    Returns:
        Экземпляр PriorityService.
    """
    return PriorityService(session)


@router.get(
    "/",
    response_model=list[PriorityRead],
    status_code=status.HTTP_200_OK,
    summary="Получить все приоритеты",
    description="Возвращает список приоритетов, отсортированных по весу (sorting_weight).",
    response_description="Список приоритетов",
)
async def get_all_priorities(
    service: PriorityService = Depends(get_priority_service),
) -> Sequence[TaskPriority]:
    """Возвращает все приоритеты."""
    return await service.list_all()


@router.get(
    "/{priority_id}",
    response_model=PriorityRead,
    status_code=status.HTTP_200_OK,
    summary="Получить приоритет по ID",
    description="Возвращает информацию о конкретном приоритете.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Приоритет не найден"}},
)
async def get_priority(
    priority_id: int,
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Ищет приоритет по идентификатору."""
    priority = await service.get_by_id(priority_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Приоритет с ID {priority_id} не найден",
        )
    return priority


@router.post(
    "/",
    response_model=PriorityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый приоритет",
    description="Добавляет новый приоритет с цветом и весом сортировки.",
    response_description="Созданный приоритет",
)
async def create_priority(
    body: PriorityCreate,
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Создает новый приоритет."""
    return await service.create(body)


@router.put(
    "/{priority_id}",
    response_model=PriorityRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить приоритет",
    description="Обновляет параметры существующего приоритета.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Приоритет не найден"}},
)
async def update_priority(
    priority_id: int,
    body: PriorityUpdate,
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Обновляет параметры приоритета."""
    priority = await service.get_by_id(priority_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Приоритет с ID {priority_id} не найден",
        )
    return await service.update(priority, body)


@router.delete(
    "/{priority_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить приоритет",
    description="Удаляет приоритет. У всех связанных задач поле task_priority_id сбрасывается в null.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Приоритет не найден"}},
)
async def delete_priority(
    priority_id: int,
    service: PriorityService = Depends(get_priority_service),
) -> None:
    """Удаляет приоритет."""
    priority = await service.get_by_id(priority_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Приоритет с ID {priority_id} не найден",
        )
    await service.delete(priority)
