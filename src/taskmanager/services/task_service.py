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
from taskmanager.models import Task, User
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
        user_id: int,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
        no_date: bool = False,
    ) -> Sequence[Task]:
        """Возвращает список задач пользователя, опционально отфильтрованный по диапазону дат.

        Сортировка производится по дате срока выполнения (nulls last)
        и идентификатору задачи.

        Args:
            user_id: Идентификатор владельца задач.
            date_from: Начальная дата диапазона (включительно).
            date_to: Конечная дата диапазона (включительно).
            no_date: Если True, возвращаются только задачи без даты (due_date is NULL).

        Returns:
            Последовательность найденных сущностей Task.
        """
        stmt = (
            select(Task).where(Task.user_id == user_id).order_by(Task.due_date.asc().nulls_last(), Task.task_id.asc())
        )

        if no_date:
            stmt = stmt.where(Task.due_date.is_(None))
        else:
            if date_from:
                d_from = self._parse_date(date_from)
                stmt = stmt.where(Task.due_date >= d_from)
            if date_to:
                d_to = self._parse_date(date_to)
                stmt = stmt.where(Task.due_date <= d_to)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, task_id: int, user_id: int) -> Task | None:
        """Ищет задачу по её уникальному идентификатору и владельцу.

        Args:
            task_id: ID задачи.
            user_id: ID владельца задачи.

        Returns:
            Сущность Task или None, если задача не найдена или принадлежит другому пользователю.
        """
        stmt = select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, dto: TaskCreate, user_id: int) -> Task:
        """Создает новую задачу для указанного пользователя.

        Args:
            dto: Схема с данными новой задачи.
            user_id: Идентификатор пользователя-создателя.

        Returns:
            Созданная сущность Task с присвоенным ID.
        """
        data = dto.model_dump(exclude_unset=True)
        if "closed_dttm" in data and isinstance(data["closed_dttm"], datetime):
            if data["closed_dttm"].tzinfo is not None:
                data["closed_dttm"] = data["closed_dttm"].astimezone(UTC).replace(tzinfo=None)
        task = Task(**data, user_id=user_id)
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

    async def execute_query(
        self,
        query: str,
        user: User,
        limit: int = 1000,
    ) -> tuple[list[str], list[dict[str, Any]], int, bool, bool]:
        """Выполняет безопасный пользовательский SQL-запрос только для чтения.

        Запрос предварительно проверяется на отсутствие запрещенных конструкций,
        комментариев и множественных инструкций. Выполнение происходит в контексте
        READ ONLY на уровне транзакции / подключения.

        Для администраторов запрос выполняется по всей базе данных без ограничений.
        Для обычных пользователей запрос изолируется через безопасную CTE-обертку,
        ограничивающую выборку только строками текущего пользователя.

        Args:
            query: Текст SQL-запроса от пользователя.
            user: Текущий аутентифицированный пользователь.
            limit: Максимальное количество строк для выборки (по умолчанию 1000).

        Returns:
            Кортеж (columns, rows, count, has_more, is_isolated).

        Raises:
            SqlSecurityError: Если запрос нарушает правила безопасности или произошла ошибка выполнения SQL.
        """
        clean_sql = validate_and_clean_sql(query)

        conn = await self.session.connection()
        dialect_name = conn.dialect.name
        is_sqlite = dialect_name == "sqlite"
        is_postgres = dialect_name == "postgresql"

        is_admin = user.role == "admin"
        is_isolated = not is_admin

        params: dict[str, Any] = {}
        target_sql = clean_sql

        if is_isolated:
            params["current_user_id"] = user.user_id
            schema_p = "main." if is_sqlite else "public."
            cte_prefix = (
                f"WITH task AS (SELECT * FROM {schema_p}task WHERE user_id = :current_user_id),\n"
                f"     task_priority AS (SELECT * FROM {schema_p}task_priority WHERE user_id = :current_user_id),\n"
                f"     task_tag AS (SELECT * FROM {schema_p}task_tag WHERE user_id = :current_user_id),\n"
                f"     task_comment AS (\n"
                f"         SELECT tc.* FROM {schema_p}task_comment tc\n"
                f"         JOIN {schema_p}task t ON tc.task_id = t.task_id\n"
                f"         WHERE t.user_id = :current_user_id\n"
                f"     ),\n"
                f"     task_tag_x_task AS (\n"
                f"         SELECT xt.* FROM {schema_p}task_tag_x_task xt\n"
                f"         JOIN {schema_p}task t ON xt.task_id = t.task_id\n"
                f"         WHERE t.user_id = :current_user_id\n"
                f"     ),\n"
                f"     users AS (\n"
                f"         SELECT user_id, username, email, role, created_at\n"
                f"         FROM {schema_p}users WHERE user_id = :current_user_id\n"
                f"     )\n"
            )
            trimmed = clean_sql.lstrip()
            if trimmed.upper().startswith("WITH"):
                # Объединяем существующий WITH с нашими CTE
                rest_of_query = trimmed[4:].lstrip()
                target_sql = f"{cte_prefix}, {rest_of_query}"
            else:
                target_sql = f"{cte_prefix} {clean_sql}"

        try:
            if is_sqlite:
                await self.session.execute(text("PRAGMA query_only = ON"))
            elif is_postgres:
                await self.session.execute(text("SET TRANSACTION READ ONLY"))

            stmt = text(target_sql)
            result = await self.session.execute(stmt, params)
            columns = list(result.keys())
            raw_rows = result.mappings().fetchmany(limit + 1)
            has_more = len(raw_rows) > limit
            if has_more:
                raw_rows = raw_rows[:limit]
            rows = [dict(r) for r in raw_rows]
            return columns, rows, len(rows), has_more, is_isolated
        except SQLAlchemyError as err:
            orig_msg = str(getattr(err, "orig", err))
            raise SqlSecurityError(f"Ошибка выполнения SQL-запроса: {orig_msg}") from err
        finally:
            if is_sqlite:
                try:
                    await self.session.execute(text("PRAGMA query_only = OFF"))
                except Exception:
                    pass
