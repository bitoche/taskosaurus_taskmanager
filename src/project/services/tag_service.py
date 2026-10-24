"""Сервис управления тегами и связями тегов с задачами."""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from project.models import TaskTag, TaskTagXTask
from project.schemas import TagAssign, TagCreate, TagUpdate


class TagService:
    """Сервисный класс для работы с тегами и связями 'тег-задача'.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, tag_id: int) -> TaskTag | None:
        """Возвращает тег по его ID.

        Args:
            tag_id: Идентификатор тега.

        Returns:
            Сущность TaskTag или None.
        """
        return await self.session.get(TaskTag, tag_id)

    async def list_all(self) -> Sequence[TaskTag]:
        """Возвращает все зарегистрированные теги.

        Returns:
            Список тегов.
        """
        result = await self.session.execute(select(TaskTag))
        return result.scalars().all()

    async def list_assignments(self) -> Sequence[TaskTagXTask]:
        """Возвращает все связи между тегами и задачами.

        Returns:
            Список связок (task_tag_id, task_id).
        """
        result = await self.session.execute(select(TaskTagXTask))
        return result.scalars().all()

    async def create(self, dto: TagCreate) -> TaskTag:
        """Создает новый тег.

        Args:
            dto: Схема с цветом и названием тега.

        Returns:
            Созданная сущность TaskTag.
        """
        tag = TaskTag(**dto.model_dump())
        self.session.add(tag)
        await self.session.flush()
        await self.session.refresh(tag)
        return tag

    async def assign_to_task(self, dto: TagAssign) -> TaskTagXTask:
        """Прикрепляет тег к задаче.

        Args:
            dto: Схема с ID тега и ID задачи.

        Returns:
            Созданная связь TaskTagXTask.
        """
        link = TaskTagXTask(task_tag_id=dto.task_tag_id, task_id=dto.task_id)
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def unassign_from_task(self, tag_id: int, task_id: int) -> None:
        """Снимает тег с задачи.

        Args:
            tag_id: ID тега.
            task_id: ID задачи.
        """
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
        """Удаляет тег глобально (каскадно удаляя связи с задачами).

        Args:
            tag: Объект тега для удаления.
        """
        await self.session.delete(tag)
        await self.session.flush()
