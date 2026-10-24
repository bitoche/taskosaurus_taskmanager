"""Маршруты API для управления тегами и их назначением на задачи."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.database import get_session
from taskmanager.models import TaskTag, TaskTagXTask
from taskmanager.schemas import TagAssign, TagCreate, TagRead, TagUpdate, TagWithTasks
from taskmanager.services.tag_service import TagService

router = APIRouter()


def get_tag_service(session: AsyncSession = Depends(get_session)) -> TagService:
    """Внедрение зависимости сервиса тегов.

    Args:
        session: Сессия SQLAlchemy из контекста запроса.

    Returns:
        Экземпляр TagService.
    """
    return TagService(session)


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
    description="Возвращает справочник всех существующих тегов.",
    response_description="Список тегов",
)
async def get_all_tags(
    service: TagService = Depends(get_tag_service),
) -> Sequence[TaskTag]:
    """Возвращает все теги."""
    return await service.list_all()


@router.get(
    "/tasks",
    response_model=list[TagWithTasks],
    status_code=status.HTTP_200_OK,
    summary="Получить связи тегов с задачами",
    description="Возвращает список всех привязок тегов к задачам.",
    response_description="Список связей тег-задача",
)
async def get_all_tags_with_tasks(
    service: TagService = Depends(get_tag_service),
) -> Sequence[TaskTagXTask]:
    """Возвращает все ассоциации между тегами и задачами."""
    return await service.list_assignments()


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
    description="Добавляет новый тег в справочник.",
    response_description="Созданный тег",
)
async def create_tag(
    body: TagCreate,
    service: TagService = Depends(get_tag_service),
) -> TaskTag:
    """Создает новый тег."""
    return await service.create(body)


@router.post(
    "/assign",
    response_model=TagWithTasks,
    status_code=status.HTTP_201_CREATED,
    summary="Привязать тег к задаче",
    description="Назначает тег на указанную задачу.",
    response_description="Созданная связь",
)
async def assign_tag_to_task(
    body: TagAssign,
    service: TagService = Depends(get_tag_service),
) -> TaskTagXTask:
    """Назначает тег на задачу."""
    return await service.assign_to_task(body)


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
    service: TagService = Depends(get_tag_service),
) -> TaskTag:
    """Обновляет параметры тега."""
    tag = await service.get_by_id(task_tag_id)
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
    description="Удаляет привязку конкретного тега к конкретной задаче.",
)
async def unassign_tag_from_task(
    task_tag_id: int,
    task_id: int,
    service: TagService = Depends(get_tag_service),
) -> None:
    """Удаляет связь тега с задачей."""
    await service.unassign_from_task(tag_id=task_tag_id, task_id=task_id)


@router.delete(
    "/{task_tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тег глобально",
    description="Удаляет тег из системы и каскадно снимает его со всех задач.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Тег не найден"}},
)
async def delete_tag(
    task_tag_id: int,
    service: TagService = Depends(get_tag_service),
) -> None:
    """Удаляет тег."""
    tag = await service.get_by_id(task_tag_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Тег с ID {task_tag_id} не найден",
        )
    await service.delete(tag)
