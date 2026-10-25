"""Модульные тесты для сервисного слоя (TaskService, CommentService, TagService, PriorityService)."""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.models.enums import TaskStatusEnum
from taskmanager.schemas import (
    CommentCreate,
    CommentUpdate,
    PriorityCreate,
    PriorityUpdate,
    TagAssign,
    TagCreate,
    TagUpdate,
    TaskCreate,
    TaskUpdate,
)
from taskmanager.services import (
    CommentService,
    PriorityService,
    TagService,
    TaskService,
)


@pytest.mark.anyio
async def test_task_service_crud_and_status(session: AsyncSession) -> None:
    """Тестирование бизнес-логики сервиса задач напрямую через сессию БД."""
    service = TaskService(session)

    # 1. Создание задачи
    create_dto = TaskCreate(
        title="Сервисная задача",
        description="Тест без HTTP-слоя",
        due_date="2026-11-15",
    )
    task = await service.create(create_dto)
    assert task.task_id is not None
    assert task.title == "Сервисная задача"
    assert task.due_date == date(2026, 11, 15)
    assert task.task_status == TaskStatusEnum.ACTIVE.value
    assert task.closed_dttm is None

    # 2. Поиск по ID
    found = await service.get_by_id(task.task_id)
    assert found is not None
    assert found.task_id == task.task_id

    # 3. Фильтрация по дате
    tasks = await service.list_tasks(date_from="2026-11-01", date_to="2026-11-30")
    assert any(t.task_id == task.task_id for t in tasks)

    # 4. Обновление статуса на COMPLETED (авто-выставление даты закрытия)
    updated = await service.update(task, TaskUpdate(task_status=TaskStatusEnum.COMPLETED.value))
    assert updated.task_status == TaskStatusEnum.COMPLETED.value
    assert updated.closed_dttm is not None

    # 5. Возврат в статус ACTIVE (сброс даты закрытия)
    reopened = await service.update(task, TaskUpdate(task_status=TaskStatusEnum.ACTIVE.value))
    assert reopened.task_status == TaskStatusEnum.ACTIVE.value
    assert reopened.closed_dttm is None

    # 6. Удаление задачи
    await service.delete(task)
    assert await service.get_by_id(task.task_id) is None


@pytest.mark.anyio
async def test_comment_service(session: AsyncSession) -> None:
    """Тестирование сервиса комментариев."""
    task_service = TaskService(session)
    comment_service = CommentService(session)

    # Подготовка родительской задачи
    task = await task_service.create(TaskCreate(title="Задача для комментов"))

    # Создание комментария
    comment = await comment_service.create(CommentCreate(task_id=task.task_id, text="Заметка 1"))
    assert comment.comment_id is not None
    assert comment.text == "Заметка 1"

    # Получение по задаче
    comments = await comment_service.list_by_task(task.task_id)
    assert len(comments) == 1

    # Редактирование
    updated = await comment_service.update(comment, CommentUpdate(text="Заметка 1 отредактирована"))
    assert updated.text == "Заметка 1 отредактирована"

    # Удаление
    await comment_service.delete(comment)
    assert await comment_service.get_by_id(comment.comment_id) is None


@pytest.mark.anyio
async def test_tag_service(session: AsyncSession) -> None:
    """Тестирование сервиса тегов и связывания с задачами."""
    task_service = TaskService(session)
    tag_service = TagService(session)

    # Создание тега
    tag = await tag_service.create(TagCreate(tag_text="Frontend", tag_color="#336699"))
    assert tag.task_tag_id is not None

    # Создание задачи
    task = await task_service.create(TaskCreate(title="Задача под тег"))

    # Привязка тега
    assignment = await tag_service.assign_to_task(TagAssign(task_tag_id=tag.task_tag_id, task_id=task.task_id))
    assert assignment.task_tag_id == tag.task_tag_id

    # Проверка списка назначений
    assignments = await tag_service.list_assignments()
    assert any(a.task_tag_id == tag.task_tag_id and a.task_id == task.task_id for a in assignments)

    # Отвязка
    await tag_service.unassign_from_task(tag.task_tag_id, task.task_id)

    # Обновление тега
    updated_tag = await tag_service.update(tag, TagUpdate(tag_text="UI/UX"))
    assert updated_tag.tag_text == "UI/UX"

    # Удаление
    await tag_service.delete(tag)
    assert await tag_service.get_by_id(tag.task_tag_id) is None


@pytest.mark.anyio
async def test_priority_service(session: AsyncSession) -> None:
    """Тестирование сервиса приоритетов и безопасного обнуления ссылок."""
    task_service = TaskService(session)
    priority_service = PriorityService(session)

    # Создание приоритета
    priority = await priority_service.create(
        PriorityCreate(
            priority_name="Блокер",
            priority_color="#ff1100",
            priority_sorting_weight=99,
        )
    )

    # Привязка к задаче
    task = await task_service.create(
        TaskCreate(
            title="Блокирующая задача",
            task_priority_id=priority.priority_id,
        )
    )
    assert task.task_priority_id == priority.priority_id

    # Обновление приоритета
    updated_p = await priority_service.update(priority, PriorityUpdate(priority_name="Блокирующий баг"))
    assert updated_p.priority_name == "Блокирующий баг"

    # Удаление приоритета должно сбросить task.task_priority_id в None
    await priority_service.delete(priority)
    refreshed_task = await task_service.get_by_id(task.task_id)
    assert refreshed_task is not None
    assert refreshed_task.task_priority_id is None


@pytest.mark.anyio
async def test_task_service_execute_query(session: AsyncSession) -> None:
    """Тестирование выполнения безопасных запросов и блокировки атак в TaskService."""
    from taskmanager.core.exceptions import SqlSecurityError

    service = TaskService(session)

    # Создаем задачу
    await service.create(TaskCreate(title="SQL юнит тест", description="Проверка сервиса"))

    # Успешный SELECT
    columns, rows, count, has_more = await service.execute_query("SELECT task_id, title FROM task")
    assert columns == ["task_id", "title"]
    assert count >= 1
    assert has_more is False
    assert any(r["title"] == "SQL юнит тест" for r in rows)

    # Проверка работы лимита строк
    columns, rows, count, has_more = await service.execute_query("SELECT task_id, title FROM task", limit=1)
    assert count == 1
    assert len(rows) == 1

    # Проверка вызова исключения при опасном запросе
    with pytest.raises(SqlSecurityError):
        await service.execute_query("DROP TABLE task")

    with pytest.raises(SqlSecurityError):
        await service.execute_query("SELECT * FROM task -- коммент")

    with pytest.raises(SqlSecurityError):
        await service.execute_query("SELECT 1; DROP TABLE task")


@pytest.mark.anyio
async def test_task_cascade_deletion_on_sqlite(session: AsyncSession) -> None:
    """Проверка каскадного удаления связанных записей task_tag_x_task в SQLite."""
    from sqlalchemy import select

    from taskmanager.models import TaskTagXTask
    from taskmanager.schemas import TagAssign, TagCreate
    from taskmanager.services.tag_service import TagService

    task_service = TaskService(session)
    tag_service = TagService(session)

    # Создаем задачу и тег
    task = await task_service.create(TaskCreate(title="Задача для каскада"))
    tag = await tag_service.create(TagCreate(tag_color="#FF0000", tag_text="Важное"))
    await tag_service.assign_to_task(TagAssign(task_tag_id=tag.task_tag_id, task_id=task.task_id))

    # Проверяем, что связь существует
    links_before = (
        (await session.execute(select(TaskTagXTask).where(TaskTagXTask.task_id == task.task_id))).scalars().all()
    )
    assert len(links_before) == 1

    # Удаляем задачу
    await task_service.delete(task)

    # Проверяем, что связь удалилась каскадно на уровне базы
    links_after = (
        (await session.execute(select(TaskTagXTask).where(TaskTagXTask.task_id == task.task_id))).scalars().all()
    )
    assert len(links_after) == 0
