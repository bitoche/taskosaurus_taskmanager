"""Интеграционные тесты для проверки всех эндпоинтов REST API."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    """Проверка доступности эндпоинта /api/health."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_tasks_crud_and_status_logic(client: AsyncClient) -> None:
    """Комплексная проверка CRUD задач и бизнес-логики переходов статусов."""
    # 1. Создание задачи
    payload = {
        "title": "Миграция на PostgreSQL",
        "description": "Перенос DuckDB на PostgreSQL с FastAPI",
        "due_date": "2026-10-30",
        "link_to_taskmanager": "https://github.com/bitoche/taskmanager",
    }
    resp = await client.post("/api/tasks/", json=payload)
    assert resp.status_code == 201
    task = resp.json()
    task_id = task["task_id"]
    assert task["title"] == payload["title"]
    assert task["due_date"] == "2026-10-30"
    assert task["task_status"] == 1
    assert task["closed_dttm"] is None

    # 2. Получение задачи по ID
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id

    # 3. Фильтрация задач по диапазону дат
    resp = await client.get("/api/tasks/?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    tasks = resp.json()
    assert any(t["task_id"] == task_id for t in tasks)

    # 4. Проверка устаревшего маршрута /between
    resp = await client.get("/api/tasks/between?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    assert any(t["task_id"] == task_id for t in resp.json())

    # 5. Завершение задачи (status 2) -> closed_dttm должно выставиться автоматически
    resp = await client.put(f"/api/tasks/{task_id}", json={"task_status": 2})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["task_status"] == 2
    assert updated["closed_dttm"] is not None

    # 6. Повторное открытие задачи (status 1) -> closed_dttm должно сброситься в None
    resp = await client.put(f"/api/tasks/{task_id}", json={"task_status": 1})
    assert resp.status_code == 200
    reopened = resp.json()
    assert reopened["task_status"] == 1
    assert reopened["closed_dttm"] is None

    # 7. Удаление задачи
    resp = await client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204

    # 8. Проверка отсутствия после удаления
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_comments_flow(client: AsyncClient) -> None:
    """Проверка жизненного цикла комментариев к задаче."""
    # Создание задачи
    task_resp = await client.post("/api/tasks/", json={"title": "Тест комментариев"})
    task_id = task_resp.json()["task_id"]

    # Добавление комментария
    c_resp = await client.post(
        "/api/tasks/comment",
        json={"task_id": task_id, "text": "Первый комментарий"},
    )
    assert c_resp.status_code == 201
    comment = c_resp.json()
    comment_id = comment["comment_id"]
    assert comment["text"] == "Первый комментарий"

    # Получение списка комментариев
    list_resp = await client.get(f"/api/tasks/{task_id}/comments")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Редактирование комментария
    upd_resp = await client.put(
        f"/api/tasks/comment/{comment_id}",
        json={"text": "Обновленный комментарий"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["text"] == "Обновленный комментарий"

    # Удаление комментария
    del_resp = await client.delete(f"/api/tasks/comment/delete/{comment_id}")
    assert del_resp.status_code == 204

    # Очистка задачи
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_tags_and_assignment(client: AsyncClient) -> None:
    """Проверка создания тегов и их привязки к задачам."""
    # Создание тега
    tag_resp = await client.post(
        "/api/task_tags/",
        json={"tag_text": "Backend", "tag_color": "#ff5500"},
    )
    assert tag_resp.status_code == 201
    tag_id = tag_resp.json()["task_tag_id"]

    # Создание задачи
    task_resp = await client.post("/api/tasks/", json={"title": "Тест тегов"})
    task_id = task_resp.json()["task_id"]

    # Привязка тега к задаче
    assign_resp = await client.post(
        "/api/task_tags/assign",
        json={"task_tag_id": tag_id, "task_id": task_id},
    )
    assert assign_resp.status_code == 201

    # Проверка списка связей
    assignments = await client.get("/api/task_tags/tasks")
    assert assignments.status_code == 200
    assert any(a["task_tag_id"] == tag_id and a["task_id"] == task_id for a in assignments.json())

    # Снятие тега с задачи
    unassign_resp = await client.delete(f"/api/task_tags/unassign/{tag_id}/task/{task_id}")
    assert unassign_resp.status_code == 204

    # Глобальное удаление тега
    del_tag = await client.delete(f"/api/task_tags/{tag_id}")
    assert del_tag.status_code == 204

    # Очистка задачи
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_priorities_flow(client: AsyncClient) -> None:
    """Проверка жизненного цикла приоритетов и безопасного обнуления при удалении."""
    # Создание приоритета
    p_resp = await client.post(
        "/api/priority/",
        json={
            "priority_name": "Критический",
            "priority_color": "#ff0000",
            "priority_sorting_weight": 10,
        },
    )
    assert p_resp.status_code == 201
    p_id = p_resp.json()["priority_id"]

    # Получение списка приоритетов
    list_resp = await client.get("/api/priority/")
    assert list_resp.status_code == 200
    assert any(p["priority_id"] == p_id for p in list_resp.json())

    # Создание задачи с этим приоритетом
    task_resp = await client.post(
        "/api/tasks/",
        json={"title": "Срочная задача", "task_priority_id": p_id},
    )
    task_id = task_resp.json()["task_id"]
    assert task_resp.json()["task_priority_id"] == p_id

    # Удаление приоритета -> у задачи приоритет должен обнулиться в None
    del_p = await client.delete(f"/api/priority/{p_id}")
    assert del_p.status_code == 204

    # Проверка обнуления
    check_task = await client.get(f"/api/tasks/{task_id}")
    assert check_task.json()["task_priority_id"] is None

    # Очистка задачи
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_remote_db_stubs(client: AsyncClient) -> None:
    """Проверка работоспособности эндпоинтов-заглушек синхронизации для webui."""
    resp = await client.get("/api/remote_db/check_updates")
    assert resp.status_code == 200
    assert resp.json()["updates"] is False

    resp = await client.get("/api/remote_db/sync_download")
    assert resp.status_code == 200

    resp = await client.get("/api/remote_db/sync_upload")
    assert resp.status_code == 200
