"""Модульные тесты для сервисного слоя с проверкой многопользовательской изоляции."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import User
from taskmanager.models.enums import TaskStatusEnum
from taskmanager.schemas import (
    CommentCreate,
    CommentUpdate,
    PriorityCreate,
    TagAssign,
    TagCreate,
    TaskCreate,
    TaskUpdate,
)
from taskmanager.services import (
    AuthService,
    CommentService,
    PriorityService,
    TagService,
    TaskService,
)


@pytest.mark.anyio
async def test_auth_service_and_invite(session: AsyncSession, admin_user: User) -> None:
    """Тестирование AuthService: создание инвайта и регистрация по инвайту."""
    auth_service = AuthService(session)

    # Создание инвайта админом
    invite = await auth_service.create_invite(admin_user=admin_user, hours_valid=24)
    assert invite.token is not None
    assert invite.is_used is False

    # Регистрация по инвайту
    new_user = await auth_service.register_with_invite(
        token_str=invite.token,
        username="invited_user",
        password="ValidPassword123!",
    )
    assert new_user.username == "invited_user"
    assert new_user.role == "user"

    # Повторная попытка использовать тот же инвайт должна провалиться
    with pytest.raises(Exception):
        await auth_service.register_with_invite(
            token_str=invite.token,
            username="second_attempt",
            password="ValidPassword123!",
        )


@pytest.mark.anyio
async def test_task_service_crud_and_isolation(
    session: AsyncSession,
    test_user: User,
    second_user: User,
) -> None:
    """Тестирование CRUD задач и строгой изоляции между пользователями."""
    service = TaskService(session)

    # 1. Создание задачи пользователем 1
    task1 = await service.create(
        TaskCreate(
            title="Задача User 1",
            description="Секретные данные",
            due_date="2026-11-15",
        ),
        user_id=test_user.user_id,
    )
    assert task1.task_id is not None
    assert task1.user_id == test_user.user_id

    # 2. Пользователь 2 не может найти задачу Пользователя 1
    found_by_other = await service.get_by_id(task1.task_id, user_id=second_user.user_id)
    assert found_by_other is None

    # 3. Пользователь 1 находит свою задачу
    found_by_owner = await service.get_by_id(task1.task_id, user_id=test_user.user_id)
    assert found_by_owner is not None

    # 4. Список задач пользователя 2 не содержит задач пользователя 1
    tasks_u2 = await service.list_tasks(user_id=second_user.user_id)
    assert len(tasks_u2) == 0

    tasks_u1 = await service.list_tasks(user_id=test_user.user_id)
    assert len(tasks_u1) == 1

    # 5. Обновление статуса
    updated = await service.update(task1, TaskUpdate(task_status=TaskStatusEnum.COMPLETED.value))
    assert updated.task_status == TaskStatusEnum.COMPLETED.value
    assert updated.closed_dttm is not None

    # 6. Удаление
    await service.delete(task1)
    assert await service.get_by_id(task1.task_id, user_id=test_user.user_id) is None


@pytest.mark.anyio
async def test_comment_service(session: AsyncSession, test_user: User, second_user: User) -> None:
    """Тестирование сервиса комментариев и проверки владения задачей."""
    task_service = TaskService(session)
    comment_service = CommentService(session)

    # Подготовка родительской задачи
    task = await task_service.create(TaskCreate(title="Задача для комментов"), user_id=test_user.user_id)

    # Создание комментария владельцем
    comment = await comment_service.create(
        CommentCreate(task_id=task.task_id, text="Заметка 1"),
        user_id=test_user.user_id,
    )
    assert comment.comment_id is not None
    assert comment.text == "Заметка 1"

    # Чужой пользователь не может получить комментарии к задаче
    with pytest.raises(EntityNotFoundError):
        await comment_service.list_by_task(task.task_id, user_id=second_user.user_id)

    # Владелец получает список
    comments = await comment_service.list_by_task(task.task_id, user_id=test_user.user_id)
    assert len(comments) == 1

    # Редактирование
    updated = await comment_service.update(comment, CommentUpdate(text="Заметка 1 отредактирована"))
    assert updated.text == "Заметка 1 отредактирована"

    # Удаление
    await comment_service.delete(comment)
    assert await comment_service.get_by_id(comment.comment_id, user_id=test_user.user_id) is None


@pytest.mark.anyio
async def test_tag_service_isolation(session: AsyncSession, test_user: User, second_user: User) -> None:
    """Тестирование изоляции тегов."""
    task_service = TaskService(session)
    tag_service = TagService(session)

    # Пользователь 1 создает тег
    tag1 = await tag_service.create(TagCreate(tag_text="Frontend", tag_color="#336699"), user_id=test_user.user_id)
    task1 = await task_service.create(TaskCreate(title="Задача под тег"), user_id=test_user.user_id)

    # Привязка тега
    assignment = await tag_service.assign_to_task(
        TagAssign(task_tag_id=tag1.task_tag_id, task_id=task1.task_id),
        user_id=test_user.user_id,
    )
    assert assignment.task_tag_id == tag1.task_tag_id

    # Пользователь 2 не видит теги пользователя 1
    tags_u2 = await tag_service.list_all(user_id=second_user.user_id)
    assert len(tags_u2) == 0

    # Пользователь 2 не может назначить чужой тег
    task2 = await task_service.create(TaskCreate(title="Задача User 2"), user_id=second_user.user_id)
    with pytest.raises(EntityNotFoundError):
        await tag_service.assign_to_task(
            TagAssign(task_tag_id=tag1.task_tag_id, task_id=task2.task_id),
            user_id=second_user.user_id,
        )


@pytest.mark.anyio
async def test_priority_service_isolation(session: AsyncSession, test_user: User, second_user: User) -> None:
    """Тестирование персональных приоритетов пользователей."""
    priority_service = PriorityService(session)

    # Пользователь 1 создает приоритет
    await priority_service.create(
        PriorityCreate(priority_name="Срочно", priority_color="#FF0000", priority_sorting_weight=10),
        user_id=test_user.user_id,
    )

    # Пользователь 2 видит пустой список приоритетов (согласно принятому решению)
    p_u2 = await priority_service.list_all(user_id=second_user.user_id)
    assert len(p_u2) == 0

    p_u1 = await priority_service.list_all(user_id=test_user.user_id)
    assert len(p_u1) == 1
    assert p_u1[0].priority_name == "Срочно"


@pytest.mark.anyio
async def test_task_service_execute_query_scoping(
    session: AsyncSession,
    test_user: User,
    second_user: User,
    admin_user: User,
) -> None:
    """Тестирование изоляции произвольных SQL-запросов (CTE-фильтрация для обычных пользователей и доступ админу)."""
    service = TaskService(session)

    # Создаем задачу для пользователя 1 и задачу для пользователя 2
    await service.create(TaskCreate(title="Задача Первого"), user_id=test_user.user_id)
    await service.create(TaskCreate(title="Задача Второго"), user_id=second_user.user_id)

    # 1. Запрос от обычного пользователя 1: должен вернуть ТОЛЬКО задачу пользователя 1
    cols, rows, count, has_more, is_isolated = await service.execute_query(
        "SELECT task_id, title FROM task",
        user=test_user,
    )
    assert is_isolated is True
    titles = [r["title"] for r in rows]
    assert "Задача Первого" in titles
    assert "Задача Второго" not in titles

    # 2. Запрос от обычного пользователя 2: должен вернуть ТОЛЬКО задачу пользователя 2
    cols, rows, count, has_more, is_isolated = await service.execute_query(
        "SELECT task_id, title FROM task",
        user=second_user,
    )
    assert is_isolated is True
    titles = [r["title"] for r in rows]
    assert "Задача Второго" in titles
    assert "Задача Первого" not in titles

    # 3. Запрос от администратора: видит обе задачи без изоляции
    cols, rows, count, has_more, is_isolated = await service.execute_query(
        "SELECT task_id, title FROM task",
        user=admin_user,
    )
    assert is_isolated is False
    titles = [r["title"] for r in rows]
    assert "Задача Первого" in titles
    assert "Задача Второго" in titles
