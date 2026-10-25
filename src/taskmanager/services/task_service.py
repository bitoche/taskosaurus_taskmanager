"""Сервис управления задачами (бизнес-логика и доступ к данным).

Содержит операции создания, поиска, фильтрации по календарю, обновления статусов,
удаления задач и выполнения безопасных пользовательских SQL-запросов.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.exceptions import SqlSecurityError
from taskmanager.models import Task
from taskmanager.models.enums import TaskStatusEnum
from taskmanager.schemas import TaskCreate, TaskUpdate
from taskmanager.services.sql_guard import validate_and_clean_sql


class TaskService:
    """Сервисный класс для работы с задачами.

    Args:
        session: Асинхронная сессия SQLAlchemy.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _parse_date(val: date | str | None) -> date | None:
        """Безопасно преобразует строку или объект даты в date.

        Args:
            val: Исходное значение даты.

        Returns:
            Объект date или None.

        Raises:
            ValueError: Если формат строки не соответствует YYYY-MM-DD.
        """
        if val is None or isinstance(val, date):
            return val
        return date.fromisoformat(val[:10])

    @staticmethod
    def _parse_datetime(val: datetime | str | None) -> datetime | None:
        """Безопасно преобразует строку или объект datetime в datetime.

        Args:
            val: Исходное значение даты и времени.

        Returns:
            Объект datetime или None.

        Raises:
            ValueError: Если формат строки не удается распарсить.
        """
        if val is None or isinstance(val, datetime):
            return val
        clean = val.replace("T", " ")
        if len(clean) > 19:
            clean = clean[:19]
        return datetime.fromisoformat(clean)

    async def list_tasks(
        self,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
    ) -> Sequence[Task]:
        """Возвращает список задач, опционально отфильтрованный по диапазону дат.

        Сортировка производится по дате срока выполнения (nulls last)
        и идентификатору задачи.

        Args:
            date_from: Начальная дата диапазона (включительно).
            date_to: Конечная дата диапазона (включительно).

        Returns:
            Последовательность найденных сущностей Task.
        """
        stmt = select(Task).order_by(Task.due_date.asc().nulls_last(), Task.task_id.asc())

        if date_from:
            d_from = self._parse_date(date_from)
            stmt = stmt.where(Task.due_date >= d_from)
        if date_to:
            d_to = self._parse_date(date_to)
            stmt = stmt.where(Task.due_date <= d_to)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, task_id: int) -> Task | None:
        """Ищет задачу по её уникальному идентификатору.

        Args:
            task_id: ID задачи.

        Returns:
            Сущность Task или None, если задача не найдена.
        """
        return await self.session.get(Task, task_id)

    async def create(self, dto: TaskCreate) -> Task:
        """Создает новую задачу в базе данных.

        Args:
            dto: Схема с данными новой задачи.

        Returns:
            Созданная сущность Task с присвоенным ID.
        """
        data = dto.model_dump(exclude_unset=True)
        task = Task(**data)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update(self, task: Task, dto: TaskUpdate) -> Task:
        """Обновляет поля задачи с соблюдением бизнес-логики статусов.

        Бизнес-правила:
        - Если передана дата закрытия `closed_dttm`, статус автоматически
          становится COMPLETED (2).
        - Если статус изменен на ACTIVE (1), дата `closed_dttm` сбрасывается в None.
        - Если статус изменен на COMPLETED (2), дата `closed_dttm` выставляется в текущее
          время (если ранее не была задана).

        Args:
            task: Существующая сущность Task из БД.
            dto: Схема с обновляемыми полями.

        Returns:
            Обновленная сущность Task.
        """
        data = dto.model_dump(exclude_unset=True)

        if "closed_dttm" in data and isinstance(data["closed_dttm"], datetime):
            if data["closed_dttm"].tzinfo is not None:
                data["closed_dttm"] = data["closed_dttm"].astimezone(UTC).replace(tzinfo=None)

        # Автоматическая смена статуса при явной передаче даты закрытия
        if data.get("closed_dttm") is not None:
            data["task_status"] = TaskStatusEnum.COMPLETED.value

        # Логика перехода между статусами
        if "task_status" in data and data["task_status"] is not None:
            if data["task_status"] == TaskStatusEnum.ACTIVE.value:
                data["closed_dttm"] = None
            elif data["task_status"] == TaskStatusEnum.COMPLETED.value:
                if task.closed_dttm is None and data.get("closed_dttm") is None:
                    data["closed_dttm"] = datetime.now(UTC).replace(tzinfo=None)

        for key, value in data.items():
            setattr(task, key, value)

        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        """Удаляет задачу и связанные с ней комментарии (каскадно).

        Args:
            task: Сущность Task для удаления.
        """
        await self.session.delete(task)
        await self.session.flush()

    async def execute_query(self, query: str, limit: int = 1000) -> tuple[list[str], list[dict[str, Any]], int, bool]:
        """Выполняет безопасный пользовательский SQL-запрос только для чтения.

        Запрос предварительно проверяется на отсутствие запрещенных конструкций,
        комментариев и множественных инструкций. Выполнение происходит в контексте
        READ ONLY на уровне транзакции / подключения.
        Выборка ограничена безопасным максимумом строк (параметр limit) для предотвращения
        переполнения оперативной памяти.

        Args:
            query: Текст SQL-запроса от пользователя.
            limit: Максимальное количество строк для выборки (по умолчанию 1000).

        Returns:
            Кортеж из списка имен колонок, списка строк-словарей, общего количества строк и флага has_more.

        Raises:
            SqlSecurityError: Если запрос нарушает правила безопасности или произошла ошибка выполнения SQL.
        """
        clean_sql = validate_and_clean_sql(query)

        conn = await self.session.connection()
        dialect_name = conn.dialect.name
        is_sqlite = dialect_name == "sqlite"
        is_postgres = dialect_name == "postgresql"

        try:
            if is_sqlite:
                await self.session.execute(text("PRAGMA query_only = ON"))
            elif is_postgres:
                await self.session.execute(text("SET TRANSACTION READ ONLY"))

            result = await self.session.execute(text(clean_sql))
            columns = list(result.keys())
            raw_rows = result.mappings().fetchmany(limit + 1)
            has_more = len(raw_rows) > limit
            if has_more:
                raw_rows = raw_rows[:limit]
            rows = [dict(r) for r in raw_rows]
            return columns, rows, len(rows), has_more
        except SQLAlchemyError as err:
            orig_msg = str(getattr(err, "orig", err))
            raise SqlSecurityError(f"Ошибка выполнения SQL-запроса: {orig_msg}") from err
        finally:
            if is_sqlite:
                try:
                    await self.session.execute(text("PRAGMA query_only = OFF"))
                except Exception:
                    pass
