"""Интеграционные тесты для проверки API, авторизации, брутфорса и изоляции пользователей."""

import pytest
from httpx import AsyncClient

from taskmanager.core.config import settings
from taskmanager.core.security import create_access_token
from taskmanager.models import User


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    """Проверка доступности эндпоинта /api/health без авторизации."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == settings.app_version


@pytest.mark.anyio
async def test_version(client: AsyncClient) -> None:
    """Проверка доступности эндпоинта /api/version без авторизации."""
    resp = await client.get("/api/version")
    assert resp.status_code == 200
    assert resp.json() == {"version": settings.app_version}


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

    # Создание инвайта и его удаление администратором
    created2 = await admin_client.post("/api/auth/invites", json={"expires_hours": 12})
    assert created2.status_code == 201
    tok2 = created2.json()["token"]

    # Обычный пользователь не может удалить инвайт
    forb_del = await auth_client.delete(f"/api/auth/invites/{tok2}")
    assert forb_del.status_code == 403

    # Админ удаляет инвайт
    del_resp = await admin_client.delete(f"/api/auth/invites/{tok2}")
    assert del_resp.status_code == 204

    # Повторная попытка удаления возвращает 404
    del_again = await admin_client.delete(f"/api/auth/invites/{tok2}")
    assert del_again.status_code == 404

    # Попытка регистрации по удаленному инвайту отклоняется
    reg_failed = await client.post(
        "/api/auth/register-with-invite",
        json={
            "token": tok2,
            "username": "intruder_user",
            "password": "Password123!",
        },
    )
    assert reg_failed.status_code == 400


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
async def test_tasks_no_date_filter(auth_client: AsyncClient) -> None:
    """Проверка фильтрации задач без даты через no_date=true."""
    # 1. Создаем задачу с датой
    resp_dated = await auth_client.post(
        "/api/tasks/",
        json={"title": "Задача с датой", "due_date": "2026-10-30"},
    )
    assert resp_dated.status_code == 201
    dated_id = resp_dated.json()["task_id"]

    # 2. Создаем задачу без даты
    resp_nodate = await auth_client.post(
        "/api/tasks/",
        json={"title": "Задача без даты", "due_date": None},
    )
    assert resp_nodate.status_code == 201
    nodate_id = resp_nodate.json()["task_id"]

    # 3. Запрос GET /api/tasks?no_date=true
    resp = await auth_client.get("/api/tasks?no_date=true")
    assert resp.status_code == 200
    tasks = resp.json()

    task_ids = [t["task_id"] for t in tasks]
    assert nodate_id in task_ids
    assert dated_id not in task_ids
    for t in tasks:
        assert t["due_date"] is None


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


@pytest.mark.anyio
async def test_admin_user_management(
    auth_client: AsyncClient,
    admin_client: AsyncClient,
    second_user: User,
) -> None:
    """Проверка админского меню пользователей: список, отзыв сессий и удаление."""
    # 1. Обычный пользователь не имеет доступа
    forbidden = await auth_client.get("/api/users")
    assert forbidden.status_code == 403

    # 2. Администратор получает список
    list_res = await admin_client.get("/api/users")
    assert list_res.status_code == 200
    users = list_res.json()
    assert len(users) >= 2
    assert any(u["username"] == second_user.username for u in users)

    # 3. Администратор отзывает сессии пользователя second_user
    revoke_res = await admin_client.post(f"/api/users/{second_user.user_id}/revoke-sessions")
    assert revoke_res.status_code == 200
    assert revoke_res.json()["token_version"] == 2

    # 4. Администратор не может удалить самого себя
    self_del = await admin_client.delete("/api/users/1")  # admin id is 1 or admin_user.user_id
    # Получим id текущего админа из me
    me = (await admin_client.get("/api/auth/me")).json()
    self_del = await admin_client.delete(f"/api/users/{me['user_id']}")
    assert self_del.status_code == 400

    # 5. Администратор удаляет second_user
    del_res = await admin_client.delete(f"/api/users/{second_user.user_id}")
    assert del_res.status_code == 204


@pytest.mark.anyio
async def test_session_revocation_enforced(
    client: AsyncClient,
    admin_client: AsyncClient,
    session,
) -> None:
    """Проверка, что после отзыва сессии старый токен действительно перестает работать (401)."""
    from taskmanager.core.security import create_access_token, hash_password
    from taskmanager.models import User

    # Создаем тестового пользователя
    u = User(username="victim", hashed_password=hash_password("Pass123!"), role="user", is_active=True, token_version=1)
    session.add(u)
    await session.commit()
    await session.refresh(u)

    # Выдаем токен версии 1
    token_v1 = create_access_token({"sub": str(u.user_id), "role": u.role, "ver": 1})
    cookies = {settings.auth_cookie_name: token_v1}

    # Запрос с токеном v1 работает
    r1 = await client.get("/api/auth/me", cookies=cookies)
    assert r1.status_code == 200

    # Админ отзывает сессии
    revoke = await admin_client.post(f"/api/users/{u.user_id}/revoke-sessions")
    assert revoke.status_code == 200

    # Запрос со старым токеном v1 теперь возвращает 401
    r2 = await client.get("/api/auth/me", cookies=cookies)
    assert r2.status_code == 401
    assert "Сессия была отозвана" in r2.json()["detail"]


@pytest.mark.anyio
async def test_export_and_import_data(
    auth_client: AsyncClient,
    admin_client: AsyncClient,
    test_user: User,
    second_user: User,
) -> None:
    """Проверка экспорта и импорта данных: как самим пользователем, так и админом для чужого аккаунта."""
    # 1. Создаем тег, приоритет и задачу для test_user
    p_res = await auth_client.post(
        "/api/priority/",
        json={"priority_name": "Критично", "priority_color": "#ff0000", "priority_sorting_weight": 1},
    )
    p_id = p_res.json()["priority_id"]

    t_res = await auth_client.post(
        "/api/task_tags/",
        json={"tag_text": "Релиз", "tag_color": "#00ff00"},
    )
    t_id = t_res.json()["task_tag_id"]

    task_res = await auth_client.post(
        "/api/tasks/",
        json={"title": "Релиз v3.1", "description": "План релиза", "task_priority_id": p_id},
    )
    task_id = task_res.json()["task_id"]

    await auth_client.post("/api/task_tags/assign", json={"task_id": task_id, "task_tag_id": t_id})
    await auth_client.post("/api/tasks/comment", json={"task_id": task_id, "text": "Тестовый комментарий"})

    # 2. Пользователь экспортирует свои данные
    exp_res = await auth_client.get("/api/users/me/export")
    assert exp_res.status_code == 200
    export_json = exp_res.json()
    assert export_json["username"] == test_user.username
    assert len(export_json["tasks"]) == 1
    assert export_json["tasks"][0]["title"] == "Релиз v3.1"
    assert export_json["tasks"][0]["priority_name"] == "Критично"
    assert "Релиз" in export_json["tasks"][0]["tags"]
    assert len(export_json["tasks"][0]["comments"]) == 1

    # 3. Администратор может экспортировать чужие данные
    admin_exp = await admin_client.get(f"/api/users/{test_user.user_id}/export")
    assert admin_exp.status_code == 200
    assert admin_exp.json()["username"] == test_user.username

    # 4. Администратор импортирует эти данные в аккаунт second_user
    admin_imp = await admin_client.post(f"/api/users/{second_user.user_id}/import", json=export_json)
    assert admin_imp.status_code == 200
    summary = admin_imp.json()
    assert summary["tasks_imported"] == 1
    assert summary["comments_imported"] == 1
    assert summary["priorities_imported"] == 1
    assert summary["tags_imported"] == 1

    # 5. Проверяем, что у second_user теперь есть эта задача
    u2_token = create_access_token(
        {"sub": str(second_user.user_id), "role": second_user.role, "ver": second_user.token_version}
    )
    u2_res = await auth_client.get("/api/tasks/", cookies={settings.auth_cookie_name: u2_token})
    assert u2_res.status_code == 200
    u2_tasks = u2_res.json()
    assert any(t["title"] == "Релиз v3.1" for t in u2_tasks)

    # 6. Проверяем импорт задачи с ISO-таймзоной (Z / +03:00) в closed_dttm и created_at
    tz_payload = {
        "version": "1.0",
        "username": test_user.username,
        "priorities": [],
        "tags": [],
        "tasks": [
            {
                "title": "Задача с таймзоной",
                "closed_dttm": "2026-10-25T18:00:00Z",
                "task_status": 2,
                "comments": [{"text": "Коммент с таймзоной", "created_at": "2026-10-25T18:30:00+03:00"}],
            }
        ],
    }
    tz_res = await auth_client.post("/api/users/me/import", json=tz_payload)
    assert tz_res.status_code == 200
    assert tz_res.json()["tasks_imported"] == 1
    assert tz_res.json()["comments_imported"] == 1
