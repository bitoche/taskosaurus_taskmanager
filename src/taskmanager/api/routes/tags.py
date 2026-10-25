"""Маршруты API для управления тегами и их назначением на задачи."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status

from taskmanager.api.dependencies import get_current_user, get_tag_service
from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import TaskTag, TaskTagXTask, User
from taskmanager.schemas import TagAssign, TagCreate, TagRead, TagUpdate, TagWithTasks
from taskmanager.services.tag_service import TagService

router = APIRouter()


@router.get(
    "",
    response_model=list[TagRead],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=list[TagRead],
    status_code=status.HTTP_200_OK,
    summary="Получить все теги",
    description="Возвращает справочник персональных тегов текущего пользователя.",
    response_description="Список тегов",
)
async def get_all_tags(
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> Sequence[TaskTag]:
    """Возвращает все теги текущего пользователя."""
    return await service.list_all(user_id=current_user.user_id)


@router.get(
    "/tasks",
    response_model=list[TagWithTasks],
    status_code=status.HTTP_200_OK,
    summary="Получить связи тегов с задачами",
    description="Возвращает список всех привязок тегов к задачам текущего пользователя.",
    response_description="Список связей тег-задача",
)
async def get_all_tags_with_tasks(
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> Sequence[TaskTagXTask]:
    """Возвращает все ассоциации между тегами и задачами текущего пользователя."""
    return await service.list_assignments(user_id=current_user.user_id)


@router.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый тег",
    description="Добавляет новый персональный тег для текущего пользователя.",
    response_description="Созданный тег",
)
async def create_tag(
    body: TagCreate,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> TaskTag:
    """Создает новый тег."""
    return await service.create(body, user_id=current_user.user_id)


@router.post(
    "/assign",
    response_model=TagWithTasks,
    status_code=status.HTTP_201_CREATED,
    summary="Привязать тег к задаче",
    description="Назначает тег на задачу текущего пользователя.",
    response_description="Созданная связь",
)
async def assign_tag_to_task(
    body: TagAssign,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> TaskTagXTask:
    """Назначает тег на задачу."""
    try:
        return await service.assign_to_task(body, user_id=current_user.user_id)
    except EntityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err.message,
        ) from err


@router.put(
    "/{task_tag_id}",
    response_model=TagRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить тег",
    description="Обновляет цвет и/или название тега.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Тег не найден"}},
)
async def update_tag(
    task_tag_id: int,
    body: TagUpdate,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> TaskTag:
    """Обновляет параметры тега."""
    tag = await service.get_by_id(task_tag_id, user_id=current_user.user_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тег с ID {task_tag_id} не найден",
        )
    return await service.update(tag, body)


@router.delete(
    "/unassign/{task_tag_id}/task/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отвязать тег от задачи",
    description="Удаляет привязку конкретного тега к конкретной задаче пользователя.",
)
async def unassign_tag_from_task(
    task_tag_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> None:
    """Удаляет связь тега с задачей."""
    await service.unassign_from_task(tag_id=task_tag_id, task_id=task_id, user_id=current_user.user_id)


@router.delete(
    "/{task_tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тег глобально",
    description="Удаляет персональный тег пользователя и каскадно снимает его со всех задач.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Тег не найден"}},
)
async def delete_tag(
    task_tag_id: int,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(get_tag_service),
) -> None:
    """Удаляет тег."""
    tag = await service.get_by_id(task_tag_id, user_id=current_user.user_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тег с ID {task_tag_id} не найден",
        )
    await service.delete(tag)
