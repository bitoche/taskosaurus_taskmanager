"""Интеграционные тесты для проверки API, авторизации, брутфорса и изоляции пользователей."""

import pytest
from httpx import AsyncClient

from taskmanager.core.config import settings
from taskmanager.models import User


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    """Проверка доступности эндпоинта /api/health без авторизации."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_unauthorized_access_blocked(client: AsyncClient) -> None:
    """Проверка, что неавторизованный пользователь не может вызвать ни одну рабочую ручку."""
    # Задачи
    resp = await client.get("/api/tasks/")
    assert resp.status_code == 401

    resp = await client.post("/api/tasks/", json={"title": "Test"})
    assert resp.status_code == 401

    # Приоритеты
    resp = await client.get("/api/priority/")
    assert resp.status_code == 401

    # Теги
    resp = await client.get("/api/task_tags/")
    assert resp.status_code == 401

    # SQL запросы
    resp = await client.get("/api/query?query=SELECT+1")
    assert resp.status_code == 401

    resp = await client.post("/api/query", json={"query": "SELECT 1"})
    assert resp.status_code == 401

    # Инвайты (только для админа)
    resp = await client.get("/api/auth/invites")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_auth_login_and_logout(client: AsyncClient, test_user: User) -> None:
    """Проверка успешного логина, установки HttpOnly cookie и выхода."""
    # 1. Попытка входа с неверным паролем
    bad_resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "WrongPassword"})
    assert bad_resp.status_code == 401

    # 2. Успешный вход
    good_resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "Password123!"})
    assert good_resp.status_code == 200
    assert good_resp.json()["username"] == "testuser"
    assert settings.auth_cookie_name in good_resp.cookies

    # 3. Запрос /api/auth/me с полученной cookie
    me_resp = await client.get("/api/auth/me", cookies=good_resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["user_id"] == test_user.user_id

    # 4. Выход
    logout_resp = await client.post("/api/auth/logout", cookies=good_resp.cookies)
    assert logout_resp.status_code == 200


@pytest.mark.anyio
async def test_brute_force_protection(client: AsyncClient, test_user: User) -> None:
    """Проверка блокировки брутфорса после 5 неудачных попыток входа."""
    for attempt in range(5):
        resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "WrongPassword"})
        if attempt < 4:
            assert resp.status_code == 401
        else:
            # 5-я попытка активирует блокировку
            assert resp.status_code in (401, 429)

    # 6-я попытка должна быть заблокирована по 429 Too Many Requests
    blocked_resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "Password123!"})
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers


@pytest.mark.anyio
async def test_invite_creation_and_registration(
    auth_client: AsyncClient,
    admin_client: AsyncClient,
    client: AsyncClient,
) -> None:
    """Проверка генерации инвайта только администратором и регистрации нового пользователя."""
    # Обычный пользователь не может создать инвайт
    forbidden = await auth_client.post("/api/auth/invites", json={"expires_hours": 12})
    assert forbidden.status_code == 403

    # Администратор создает инвайт
    created = await admin_client.post("/api/auth/invites", json={"expires_hours": 24})
    assert created.status_code == 201
    invite_token = created.json()["token"]

    # Регистрация нового пользователя по инвайту
    reg_resp = await client.post(
        "/api/auth/register-with-invite",
        json={
            "token": invite_token,
            "username": "new_team_member",
            "password": "SecurePassword999!",
        },
    )
    assert reg_resp.status_code == 201
    assert reg_resp.json()["username"] == "new_team_member"
    assert settings.auth_cookie_name in reg_resp.cookies

    # Проверяем, что новый пользователь сразу авторизован
    me_resp = await client.get("/api/auth/me", cookies=reg_resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "new_team_member"


@pytest.mark.anyio
async def test_tasks_crud_and_status_logic(auth_client: AsyncClient) -> None:
    """Комплексная проверка CRUD задач и бизнес-логики переходов статусов для авторизованного пользователя."""
    # 1. Создание задачи
    payload = {
        "title": "Миграция на PostgreSQL",
        "description": "Перенос DuckDB на PostgreSQL с FastAPI",
        "due_date": "2026-10-30",
        "link_to_taskmanager": "https://github.com/bitoche/taskmanager",
    }
    resp = await auth_client.post("/api/tasks/", json=payload)
    assert resp.status_code == 201
    task = resp.json()
    task_id = task["task_id"]
    assert task["title"] == payload["title"]
    assert task["due_date"] == "2026-10-30"
    assert task["task_status"] == 1
    assert task["closed_dttm"] is None

    # 2. Получение задачи по ID
    resp = await auth_client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id

    # 3. Фильтрация задач по диапазону дат
    resp = await auth_client.get("/api/tasks/?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    tasks = resp.json()
    assert any(t["task_id"] == task_id for t in tasks)

    # 4. Проверка маршрута /between
    resp = await auth_client.get("/api/tasks/between?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    assert any(t["task_id"] == task_id for t in resp.json())

    # 5. Завершение задачи (status 2) -> closed_dttm выставляется автоматически
    resp = await auth_client.put(f"/api/tasks/{task_id}", json={"task_status": 2})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["task_status"] == 2
    assert updated["closed_dttm"] is not None

    # 6. Повторное открытие задачи (status 1) -> closed_dttm сбрасывается в None
    resp = await auth_client.put(f"/api/tasks/{task_id}", json={"task_status": 1})
    assert resp.status_code == 200
    reopened = resp.json()
    assert reopened["task_status"] == 1
    assert reopened["closed_dttm"] is None

    # 7. Удаление задачи
    resp = await auth_client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204

    # 8. Проверка отсутствия удаленной задачи (404)
    resp = await auth_client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_tags_and_priorities_flow(auth_client: AsyncClient) -> None:
    """Проверка работы с тегами и приоритетами."""
    # 1. Создание приоритета
    resp_p = await auth_client.post(
        "/api/priority/",
        json={"priority_name": "Высокий", "priority_color": "#ff0000", "priority_sorting_weight": 10},
    )
    assert resp_p.status_code == 201
    p_id = resp_p.json()["priority_id"]

    # 2. Создание тега
    resp_t = await auth_client.post("/api/task_tags/", json={"tag_text": "Backend", "tag_color": "#00ff00"})
    assert resp_t.status_code == 201
    t_id = resp_t.json()["task_tag_id"]

    # 3. Создание задачи с приоритетом
    resp_task = await auth_client.post(
        "/api/tasks/",
        json={"title": "Тестовая задача", "task_priority_id": p_id},
    )
    assert resp_task.status_code == 201
    task_id = resp_task.json()["task_id"]

    # 4. Привязка тега к задаче
    resp_assign = await auth_client.post("/api/task_tags/assign", json={"task_id": task_id, "task_tag_id": t_id})
    assert resp_assign.status_code == 201

    # 5. Получение связей
    resp_links = await auth_client.get("/api/task_tags/tasks")
    assert resp_links.status_code == 200
    assert any(link["task_id"] == task_id and link["task_tag_id"] == t_id for link in resp_links.json())

    # 6. Отвязка тега
    resp_unassign = await auth_client.delete(f"/api/task_tags/unassign/{t_id}/task/{task_id}")
    assert resp_unassign.status_code == 204


@pytest.mark.anyio
async def test_sql_query_scoping_via_api(
    auth_client: AsyncClient,
    admin_client: AsyncClient,
) -> None:
    """Проверка эндпоинта /api/query: обычный пользователь получает is_isolated=True, админ — is_isolated=False."""
    # Создаем задачу от обычного пользователя
    await auth_client.post("/api/tasks/", json={"title": "Моя персональная задача"})

    # Обычный пользователь выполняет SELECT
    user_res = await auth_client.post("/api/query", json={"query": "SELECT task_id, title FROM task"})
    assert user_res.status_code == 200
    data = user_res.json()
    assert data["is_isolated"] is True
    assert any(r["title"] == "Моя персональная задача" for r in data["rows"])

    # Администратор выполняет SELECT
    admin_res = await admin_client.post("/api/query", json={"query": "SELECT task_id, title FROM task"})
    assert admin_res.status_code == 200
    assert admin_res.json()["is_isolated"] is False
