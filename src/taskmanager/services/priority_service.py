"""Сервис управления приоритетами задач."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.models import Task, TaskPriority
from taskmanager.schemas import PriorityCreate, PriorityUpdate


class PriorityService:
    """Сервисный класс для работы с приоритетами.

    Args:
        session: Асинхронная сессия базы данных.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, priority_id: int) -> TaskPriority | None:
        """Возвращает приоритет по ID.

        Args:
            priority_id: ID приоритета.

        Returns:
            Сущность TaskPriority или None.
        """
        return await self.session.get(TaskPriority, priority_id)

    async def list_all(self) -> Sequence[TaskPriority]:
        """Возвращает все приоритеты, отсортированные по весу (sorting_weight).

        Returns:
            Список приоритетов.
        """
        stmt = select(TaskPriority).order_by(TaskPriority.priority_sorting_weight.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, dto: PriorityCreate) -> TaskPriority:
        """Создает новый приоритет.

        Args:
            dto: Схема создания приоритета.

        Returns:
            Созданная сущность TaskPriority.
        """
        priority = TaskPriority(**dto.model_dump())
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
