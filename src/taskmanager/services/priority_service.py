"""Сервис управления приоритетами задач."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.models import Task, TaskPriority
from taskmanager.schemas import PriorityCreate, PriorityUpdate


class PriorityService:
    """Сервисный класс для работы с персональными приоритетами пользователя.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, priority_id: int, user_id: int) -> TaskPriority | None:
        """Возвращает приоритет по ID для указанного пользователя.

        Args:
            priority_id: ID приоритета.
            user_id: ID пользователя-владельца.

        Returns:
            Сущность TaskPriority или None.
        """
        stmt = select(TaskPriority).where(
            TaskPriority.priority_id == priority_id,
            TaskPriority.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_all(self, user_id: int) -> Sequence[TaskPriority]:
        """Возвращает все приоритеты пользователя, отсортированные по весу (sorting_weight).

        Args:
            user_id: ID пользователя.

        Returns:
            Список приоритетов пользователя.
        """
        stmt = (
            select(TaskPriority)
            .where(TaskPriority.user_id == user_id)
            .order_by(TaskPriority.priority_sorting_weight.asc(), TaskPriority.priority_id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, dto: PriorityCreate, user_id: int) -> TaskPriority:
        """Создает новый приоритет для пользователя.

        Args:
            dto: Схема создания приоритета.
            user_id: ID владельца.

        Returns:
            Созданная сущность TaskPriority.
        """
        priority = TaskPriority(**dto.model_dump(), user_id=user_id)
        self.session.add(priority)
        await self.session.flush()
        await self.session.refresh(priority)
        return priority

    async def update(self, priority: TaskPriority, dto: PriorityUpdate) -> TaskPriority:
        """Обновляет параметры приоритета.

        Args:
            priority: Существующий объект приоритета.
            dto: Схема с обновленными полями.

        Returns:
            Обновленный объект приоритета.
        """
        for key, value in dto.model_dump(exclude_unset=True).items():
            setattr(priority, key, value)

        await self.session.flush()
        await self.session.refresh(priority)
        return priority

    async def delete(self, priority: TaskPriority) -> None:
        """Удаляет приоритет и сбрасывает (nullify) ссылки в задачах.

        Args:
            priority: Объект приоритета для удаления.
        """
        # Сброс ссылки на удаляемый приоритет у задач
        stmt = select(Task).where(Task.task_priority_id == priority.priority_id)
        result = await self.session.execute(stmt)
        for task in result.scalars().all():
            task.task_priority_id = None

        await self.session.delete(priority)
        await self.session.flush()
