"""Маршруты API для управления приоритетами задач."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status

from taskmanager.api.dependencies import get_current_user, get_priority_service
from taskmanager.models import TaskPriority, User
from taskmanager.schemas import PriorityCreate, PriorityRead, PriorityUpdate
from taskmanager.services.priority_service import PriorityService

router = APIRouter()


@router.get(
    "",
    response_model=list[PriorityRead],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=list[PriorityRead],
    status_code=status.HTTP_200_OK,
    summary="Получить все приоритеты",
    description="Возвращает список приоритетов текущего пользователя, отсортированных по весу.",
    response_description="Список приоритетов",
)
async def get_all_priorities(
    current_user: User = Depends(get_current_user),
    service: PriorityService = Depends(get_priority_service),
) -> Sequence[TaskPriority]:
    """Возвращает все приоритеты текущего пользователя."""
    return await service.list_all(user_id=current_user.user_id)


@router.get(
    "/{priority_id}",
    response_model=PriorityRead,
    status_code=status.HTTP_200_OK,
    summary="Получить приоритет по ID",
    description="Возвращает информацию о конкретном приоритете текущего пользователя.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Приоритет не найден"}},
)
async def get_priority(
    priority_id: int,
    current_user: User = Depends(get_current_user),
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Ищет приоритет по идентификатору."""
    priority = await service.get_by_id(priority_id, user_id=current_user.user_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Приоритет с ID {priority_id} не найден",
        )
    return priority


@router.post(
    "",
    response_model=PriorityRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=PriorityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый приоритет",
    description="Добавляет новый персональный приоритет пользователя с цветом и весом сортировки.",
    response_description="Созданный приоритет",
)
async def create_priority(
    body: PriorityCreate,
    current_user: User = Depends(get_current_user),
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Создает новый приоритет для текущего пользователя."""
    return await service.create(body, user_id=current_user.user_id)


@router.put(
    "/{priority_id}",
    response_model=PriorityRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить приоритет",
    description="Обновляет параметры существующего приоритета пользователя.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Приоритет не найден"}},
)
async def update_priority(
    priority_id: int,
    body: PriorityUpdate,
    current_user: User = Depends(get_current_user),
    service: PriorityService = Depends(get_priority_service),
) -> TaskPriority:
    """Обновляет параметры приоритета."""
    priority = await service.get_by_id(priority_id, user_id=current_user.user_id)
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
    current_user: User = Depends(get_current_user),
    service: PriorityService = Depends(get_priority_service),
) -> None:
    """Удаляет приоритет."""
    priority = await service.get_by_id(priority_id, user_id=current_user.user_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Приоритет с ID {priority_id} не найден",
        )
    await service.delete(priority)
