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


@pytest.mark.anyio
async def test_sql_query_select_all(client: AsyncClient) -> None:
    """Проверка успешного выполнения запроса SELECT * FROM task и алиаса с trailing slash."""
    # Подготовка данных
    await client.post("/api/tasks/", json={"title": "Задача 1 для SQL", "due_date": "2026-10-25"})
    await client.post("/api/tasks/", json={"title": "Задача 2 для SQL", "due_date": "2026-10-26"})

    # Запрос без trailing slash
    resp = await client.post("/api/tasks/query", json={"query": "SELECT * FROM task ORDER BY task_id"})
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data
    assert "rows" in data
    assert "count" in data
    assert "task_id" in data["columns"]
    assert "title" in data["columns"]
    assert data["count"] >= 2
    assert len(data["rows"]) == data["count"]

    # Проверка алиаса с trailing slash и завершающей точкой с запятой
    resp_slash = await client.post("/api/tasks/query/", json={"query": "SELECT task_id, title FROM task;"})
    assert resp_slash.status_code == 200
    data_slash = resp_slash.json()
    assert data_slash["columns"] == ["task_id", "title"]
    assert data_slash["count"] >= 2


@pytest.mark.anyio
async def test_sql_query_get_and_aliases(client: AsyncClient) -> None:
    """Проверка выполнения GET /query, а также прямых алиасов /api/query."""
    # Подготовка данных
    await client.post("/api/tasks/", json={"title": "Тест GET query", "due_date": "2026-10-27"})

    # GET /api/tasks/query с query параметром
    resp_get = await client.get("/api/tasks/query", params={"query": "SELECT task_id, title FROM task"})
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert "task_id" in data_get["columns"]
    assert data_get["count"] >= 1

    # GET /api/tasks/query/ (trailing slash)
    resp_get_slash = await client.get("/api/tasks/query/", params={"query": "SELECT task_id FROM task"})
    assert resp_get_slash.status_code == 200
    assert "task_id" in resp_get_slash.json()["columns"]

    # Прямой алиас POST /api/query
    resp_alias_post = await client.post("/api/query", json={"query": "SELECT task_id, title FROM task"})
    assert resp_alias_post.status_code == 200
    assert resp_alias_post.json()["count"] >= 1

    # Прямой алиас GET /api/query
    resp_alias_get = await client.get("/api/query", params={"query": "SELECT task_id, title FROM task"})
    assert resp_alias_get.status_code == 200
    assert resp_alias_get.json()["count"] >= 1


@pytest.mark.anyio
async def test_sql_query_with_where_and_joins(client: AsyncClient) -> None:
    """Проверка выполнения запроса SELECT с фильтрацией WHERE и JOIN связями."""
    # Создаем приоритет
    p_resp = await client.post(
        "/api/priority/",
        json={"priority_name": "Высокий SQL", "priority_color": "#ffaa00", "priority_sorting_weight": 5},
    )
    priority_id = p_resp.json()["priority_id"]

    # Создаем тег
    t_resp = await client.post(
        "/api/task_tags/",
        json={"tag_text": "backend-sql", "tag_color": "#00ff00"},
    )
    tag_id = t_resp.json()["task_tag_id"]

    # Создаем задачу
    task_resp = await client.post(
        "/api/tasks/",
        json={"title": "Комплексный SQL тест", "task_priority_id": priority_id},
    )
    task_id = task_resp.json()["task_id"]

    # Привязываем тег
    await client.post(
        "/api/task_tags/assign",
        json={"task_id": task_id, "task_tag_id": tag_id},
    )

    # Выполняем сложный SELECT с JOIN
    query = f"""
    SELECT
        t.task_id,
        t.title,
        s.status_name,
        p.priority_name,
        tag.tag_text
    FROM task t
    JOIN task_status s ON t.task_status = s.status_id
    JOIN task_priority p ON t.task_priority_id = p.priority_id
    JOIN task_tag_x_task tt ON t.task_id = tt.task_id
    JOIN task_tag tag ON tt.task_tag_id = tag.task_tag_id
    WHERE t.task_id = {task_id}
    """
    resp = await client.post("/api/tasks/query", json={"query": query})
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["count"] == 1
    row = res_data["rows"][0]
    assert row["task_id"] == task_id
    assert row["title"] == "Комплексный SQL тест"
    assert row["status_name"] == "active"
    assert row["priority_name"] == "Высокий SQL"
    assert row["tag_text"] == "backend-sql"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "destructive_query",
    [
        "INSERT INTO task (title) VALUES ('Взлом')",
        "UPDATE task SET title = 'Взлом'",
        "DELETE FROM task",
        "DROP TABLE task",
        "ALTER TABLE task ADD COLUMN test text",
        "TRUNCATE TABLE task",
        "CREATE TABLE hack (id int)",
        "ATTACH DATABASE 'hack.db' AS hack",
        "PRAGMA table_info(task)",
        "SELECT * INTO task_backup FROM task",
    ],
)
async def test_sql_query_rejection_modifications(client: AsyncClient, destructive_query: str) -> None:
    """Проверка отклонения модифицирующих, DDL и опасных SQL-запросов (400 Bad Request)."""
    resp = await client.post("/api/tasks/query", json={"query": destructive_query})
    assert resp.status_code == 400
    assert "detail" in resp.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "multiquery",
    [
        "SELECT 1; DROP TABLE task",
        "SELECT * FROM task; SELECT * FROM task",
        "SELECT 1; ;",
        "SELECT 1; DELETE FROM task;",
    ],
)
async def test_sql_query_rejection_multiple_statements(client: AsyncClient, multiquery: str) -> None:
    """Проверка отклонения множественных запросов через точку с запятой."""
    resp = await client.post("/api/tasks/query", json={"query": multiquery})
    assert resp.status_code == 400
    assert "Множественные SQL-запросы" in resp.json()["detail"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "comment_query",
    [
        "SELECT * FROM task -- DROP TABLE task",
        "SELECT * FROM task -- внедрение",
        "SELECT * FROM task /* комментарий с инъекцией */ WHERE 1=1",
        "SELECT * FROM task; -- DROP TABLE task",
    ],
)
async def test_sql_query_rejection_comments(client: AsyncClient, comment_query: str) -> None:
    """Проверка отклонения запросов с комментариями, скрывающими инъекции."""
    resp = await client.post("/api/tasks/query", json={"query": comment_query})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "комментариев" in detail or "Множественные SQL-запросы" in detail


@pytest.mark.anyio
async def test_sql_query_cte_and_syntax_error(client: AsyncClient) -> None:
    """Проверка корректной обработки CTE (WITH ... SELECT) и синтаксических ошибок."""
    # Корректный CTE
    cte_query = "WITH recent_tasks AS (SELECT task_id, title FROM task) SELECT * FROM recent_tasks"
    resp = await client.post("/api/tasks/query", json={"query": cte_query})
    assert resp.status_code == 200

    # Опасный CTE с модификацией
    bad_cte = "WITH del AS (DELETE FROM task RETURNING *) SELECT * FROM del"
    bad_resp = await client.post("/api/tasks/query", json={"query": bad_cte})
    assert bad_resp.status_code == 400

    # Синтаксическая ошибка SQL (несуществующая таблица)
    err_resp = await client.post("/api/tasks/query", json={"query": "SELECT * FROM nonexistent_table_42"})
    assert err_resp.status_code == 400

    # Пустой запрос
    empty_resp = await client.post("/api/tasks/query", json={"query": "   "})
    assert empty_resp.status_code == 400
