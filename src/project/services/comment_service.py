"""Сервис управления комментариями к задачам."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project.models import TaskComment
from project.schemas import CommentCreate, CommentUpdate


class CommentService:
    """Сервисный класс для работы с комментариями.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, comment_id: int) -> TaskComment | None:
        """Возвращает комментарий по его идентификатору.

        Args:
            comment_id: ID комментария.

        Returns:
            Сущность TaskComment или None, если запись не найдена.
        """
        return await self.session.get(TaskComment, comment_id)

    async def list_by_task(self, task_id: int) -> Sequence[TaskComment]:
        """Возвращает список всех комментариев задачи, отсортированных хронологически.

        Args:
            task_id: ID задачи.

        Returns:
            Список комментариев к указанной задаче.
        """
        stmt = select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, dto: CommentCreate) -> TaskComment:
        """Создает новый комментарий к задаче.

        Args:
            dto: Схема с ID задачи и текстом комментария.

        Returns:
            Созданная сущность TaskComment.
        """
        comment = TaskComment(**dto.model_dump())
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def update(self, comment: TaskComment, dto: CommentUpdate) -> TaskComment:
        """Обновляет текст комментария.

        Args:
            comment: Существующий объект комментария.
            dto: Схема с новым текстом.

        Returns:
            Обновленный объект комментария.
        """
        for key, value in dto.model_dump(exclude_unset=True).items():
            setattr(comment, key, value)

        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def delete(self, comment: TaskComment) -> None:
        """Удаляет комментарий.

        Args:
            comment: Объект комментария для удаления.
        """
        await self.session.delete(comment)
        await self.session.flush()
