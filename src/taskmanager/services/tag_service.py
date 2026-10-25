"""Сервис управления тегами и связями тегов с задачами."""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import Task, TaskTag, TaskTagXTask
from taskmanager.schemas import TagAssign, TagCreate, TagUpdate


class TagService:
    """Сервисный класс для работы с персональными тегами пользователя и связями 'тег-задача'.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, tag_id: int, user_id: int) -> TaskTag | None:
        """Возвращает тег по его ID для указанного пользователя.

        Args:
            tag_id: Идентификатор тега.
            user_id: Идентификатор владельца тега.

        Returns:
            Сущность TaskTag или None.
        """
        stmt = select(TaskTag).where(TaskTag.task_tag_id == tag_id, TaskTag.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_all(self, user_id: int) -> Sequence[TaskTag]:
        """Возвращает все зарегистрированные теги пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список тегов.
        """
        stmt = select(TaskTag).where(TaskTag.user_id == user_id).order_by(TaskTag.tag_text.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_assignments(self, user_id: int) -> Sequence[TaskTagXTask]:
        """Возвращает все связи между тегами и задачами пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Список связок (task_tag_id, task_id).
        """
        stmt = select(TaskTagXTask).join(Task, TaskTagXTask.task_id == Task.task_id).where(Task.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, dto: TagCreate, user_id: int) -> TaskTag:
        """Создает новый тег для пользователя.

        Args:
            dto: Схема с цветом и названием тега.
            user_id: Идентификатор владельца.

        Returns:
            Созданная сущность TaskTag.
        """
        tag = TaskTag(**dto.model_dump(), user_id=user_id)
        self.session.add(tag)
        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def assign_to_task(self, dto: TagAssign, user_id: int) -> TaskTagXTask:
        """Прикрепляет тег к задаче пользователя, проверяя права владения.

        Args:
            dto: Схема с ID тега и ID задачи.
            user_id: Идентификатор пользователя.

        Returns:
            Созданная связь TaskTagXTask.

        Raises:
            EntityNotFoundError: Если задача или тег не принадлежат пользователю.
        """
        # Проверяем владение задачей
        task_stmt = select(Task).where(Task.task_id == dto.task_id, Task.user_id == user_id)
        task_res = await self.session.execute(task_stmt)
        if not task_res.scalars().first():
            raise EntityNotFoundError("Задача", dto.task_id)

        # Проверяем владение тегом
        tag_stmt = select(TaskTag).where(TaskTag.task_tag_id == dto.task_tag_id, TaskTag.user_id == user_id)
        tag_res = await self.session.execute(tag_stmt)
        if not tag_res.scalars().first():
            raise EntityNotFoundError("Тег", dto.task_tag_id)

        link = TaskTagXTask(task_tag_id=dto.task_tag_id, task_id=dto.task_id)
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def unassign_from_task(self, tag_id: int, task_id: int, user_id: int) -> None:
        """Снимает тег с задачи пользователя.

        Args:
            tag_id: ID тега.
            task_id: ID задачи.
            user_id: Идентификатор пользователя.
        """
        # Убеждаемся, что задача принадлежит пользователю
        task_stmt = select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
        task_res = await self.session.execute(task_stmt)
        if not task_res.scalars().first():
            return

        stmt = delete(TaskTagXTask).where(
            TaskTagXTask.task_tag_id == tag_id,
            TaskTagXTask.task_id == task_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update(self, tag: TaskTag, dto: TagUpdate) -> TaskTag:
        """Обновляет цвет и/или название тега.

        Args:
            tag: Существующий объект тега.
            dto: Схема с обновляемыми полями.

        Returns:
            Обновленный объект тега.
        """
        for key, value in dto.model_dump(exclude_unset=True).items():
            setattr(tag, key, value)

        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def delete(self, tag: TaskTag) -> None:
        """Удаляет тег (каскадно удаляя связи с задачами).

        Args:
            tag: Объект тега для удаления.
        """
        await self.session.delete(tag)
        await self.session.flush()
