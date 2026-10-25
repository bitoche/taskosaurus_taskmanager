"""Сервис управления комментариями к задачам."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import Task, TaskComment
from taskmanager.schemas import CommentCreate, CommentUpdate


class CommentService:
    """Сервисный класс для работы с комментариями к задачам пользователя.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, comment_id: int, user_id: int) -> TaskComment | None:
        """Возвращает комментарий по его идентификатору с проверкой принадлежности пользователю.

        Args:
            comment_id: ID комментария.
            user_id: ID пользователя-владельца.

        Returns:
            Сущность TaskComment или None, если запись не найдена или чужая.
        """
        stmt = (
            select(TaskComment)
            .join(Task, TaskComment.task_id == Task.task_id)
            .where(TaskComment.comment_id == comment_id, Task.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_task(self, task_id: int, user_id: int) -> Sequence[TaskComment]:
        """Возвращает список всех комментариев задачи пользователя, отсортированных хронологически.

        Args:
            task_id: ID задачи.
            user_id: ID пользователя-владельца.

        Returns:
            Список комментариев к указанной задаче.

        Raises:
            EntityNotFoundError: Если задача не принадлежит пользователю.
        """
        # Проверяем, что задача принадлежит пользователю
        task = await self.session.get(Task, task_id)
        if not task or task.user_id != user_id:
            raise EntityNotFoundError("Задача", task_id)

        stmt = select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, dto: CommentCreate, user_id: int) -> TaskComment:
        """Создает новый комментарий к задаче пользователя.

        Args:
            dto: Схема с ID задачи и текстом комментария.
            user_id: ID пользователя-владельца.

        Returns:
            Созданная сущность TaskComment.

        Raises:
            EntityNotFoundError: Если задача не найдена или принадлежит другому пользователю.
        """
        task = await self.session.get(Task, dto.task_id)
        if not task or task.user_id != user_id:
            raise EntityNotFoundError("Задача", dto.task_id)

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
