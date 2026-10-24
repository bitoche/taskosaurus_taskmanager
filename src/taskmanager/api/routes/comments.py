"""Маршруты API для управления комментариями к задачам."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.database import get_session
from taskmanager.models import TaskComment
from taskmanager.schemas import CommentCreate, CommentRead, CommentUpdate
from taskmanager.services.comment_service import CommentService

router = APIRouter()


def get_comment_service(
    session: AsyncSession = Depends(get_session),
) -> CommentService:
    """Внедрение зависимости сервиса комментариев.

    Args:
        session: Сессия SQLAlchemy из контекста запроса.

    Returns:
        Экземпляр CommentService.
    """
    return CommentService(session)


@router.get(
    "/{task_id}/comments",
    response_model=list[CommentRead],
    status_code=status.HTTP_200_OK,
    summary="Получить комментарии задачи",
    description="Возвращает хронологический список комментариев для указанной задачи.",
    response_description="Список комментариев",
)
async def get_task_comments(
    task_id: int,
    service: CommentService = Depends(get_comment_service),
) -> Sequence[TaskComment]:
    """Возвращает все комментарии к конкретной задаче."""
    return await service.list_by_task(task_id)


@router.post(
    "/comment",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить комментарий к задаче",
    description="Создает новый комментарий и прикрепляет его к задаче.",
    response_description="Созданный комментарий",
)
async def create_comment(
    body: CommentCreate,
    service: CommentService = Depends(get_comment_service),
) -> TaskComment:
    """Добавляет новый комментарий к задаче."""
    return await service.create(body)


@router.put(
    "/comment/{comment_id}",
    response_model=CommentRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить комментарий",
    description="Обновляет текст комментария по его идентификатору.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Комментарий не найден"}},
)
async def update_comment(
    comment_id: int,
    body: CommentUpdate,
    service: CommentService = Depends(get_comment_service),
) -> TaskComment:
    """Обновляет текст комментария."""
    comment = await service.get_by_id(comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Комментарий с ID {comment_id} не найден",
        )
    return await service.update(comment, body)


@router.delete(
    "/comment/delete/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить комментарий",
    description="Удаляет комментарий по его идентификатору.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Комментарий не найден"}},
)
async def delete_comment(
    comment_id: int,
    service: CommentService = Depends(get_comment_service),
) -> None:
    """Удаляет комментарий."""
    comment = await service.get_by_id(comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Комментарий с ID {comment_id} не найден",
        )
    await service.delete(comment)
