import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_tasks_crud_and_status_logic(client: AsyncClient):
    # 1. Create task
    payload = {
        "title": "Migrate to PostgreSQL",
        "description": "Port DuckDB to PostgreSQL with FastAPI",
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

    # 2. Get task by ID
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id

    # 3. Filter tasks by date range
    resp = await client.get("/api/tasks/?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    tasks = resp.json()
    assert any(t["task_id"] == task_id for t in tasks)

    # Legacy /between route
    resp = await client.get("/api/tasks/between?date_from=2026-10-01&date_to=2026-10-31")
    assert resp.status_code == 200
    assert any(t["task_id"] == task_id for t in resp.json())

    # 4. Mark task as completed (status 2) -> closed_dttm should be auto-set
    resp = await client.put(f"/api/tasks/{task_id}", json={"task_status": 2})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["task_status"] == 2
    assert updated["closed_dttm"] is not None

    # 5. Re-open task (status 1) -> closed_dttm should be cleared
    resp = await client.put(f"/api/tasks/{task_id}", json={"task_status": 1})
    assert resp.status_code == 200
    reopened = resp.json()
    assert reopened["task_status"] == 1
    assert reopened["closed_dttm"] is None

    # 6. Delete task
    resp = await client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204

    # 7. Confirm 404
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_comments_flow(client: AsyncClient):
    # Create task first
    task_resp = await client.post("/api/tasks/", json={"title": "Commented Task"})
    task_id = task_resp.json()["task_id"]

    # Add comment
    c_resp = await client.post(
        "/api/tasks/comment",
        json={"task_id": task_id, "text": "Initial feedback"},
    )
    assert c_resp.status_code == 201
    comment = c_resp.json()
    comment_id = comment["comment_id"]
    assert comment["text"] == "Initial feedback"

    # Get task comments
    list_resp = await client.get(f"/api/tasks/{task_id}/comments")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Update comment
    upd_resp = await client.put(
        f"/api/tasks/comment/{comment_id}",
        json={"text": "Updated feedback"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["text"] == "Updated feedback"

    # Delete comment
    del_resp = await client.delete(f"/api/tasks/comment/delete/{comment_id}")
    assert del_resp.status_code == 204

    # Cleanup task
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_tags_and_assignment(client: AsyncClient):
    # Create tag
    tag_resp = await client.post(
        "/api/task_tags/",
        json={"tag_text": "Backend", "tag_color": "#ff5500"},
    )
    assert tag_resp.status_code == 201
    tag_id = tag_resp.json()["task_tag_id"]

    # Create task
    task_resp = await client.post("/api/tasks/", json={"title": "Tag test"})
    task_id = task_resp.json()["task_id"]

    # Assign tag
    assign_resp = await client.post(
        "/api/task_tags/assign",
        json={"task_tag_id": tag_id, "task_id": task_id},
    )
    assert assign_resp.status_code == 201

    # Check assignment list
    assignments = await client.get("/api/task_tags/tasks")
    assert assignments.status_code == 200
    assert any(a["task_tag_id"] == tag_id and a["task_id"] == task_id for a in assignments.json())

    # Unassign
    unassign_resp = await client.delete(f"/api/task_tags/unassign/{tag_id}/task/{task_id}")
    assert unassign_resp.status_code == 204

    # Delete tag globally
    del_tag = await client.delete(f"/api/task_tags/{tag_id}")
    assert del_tag.status_code == 204

    # Cleanup
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_priorities_flow(client: AsyncClient):
    # Create priority
    p_resp = await client.post(
        "/api/priority/",
        json={
            "priority_name": "Critical",
            "priority_color": "#ff0000",
            "priority_sorting_weight": 10,
        },
    )
    assert p_resp.status_code == 201
    p_id = p_resp.json()["priority_id"]

    # List priorities
    list_resp = await client.get("/api/priority/")
    assert list_resp.status_code == 200
    assert any(p["priority_id"] == p_id for p in list_resp.json())

    # Create task with this priority
    task_resp = await client.post(
        "/api/tasks/",
        json={"title": "Urgent task", "task_priority_id": p_id},
    )
    task_id = task_resp.json()["task_id"]
    assert task_resp.json()["task_priority_id"] == p_id

    # Delete priority -> task priority should be set to None
    del_p = await client.delete(f"/api/priority/{p_id}")
    assert del_p.status_code == 204

    # Verify task priority is cleared
    check_task = await client.get(f"/api/tasks/{task_id}")
    assert check_task.json()["task_priority_id"] is None

    # Cleanup
    await client.delete(f"/api/tasks/{task_id}")


@pytest.mark.anyio
async def test_remote_db_stubs(client: AsyncClient):
    resp = await client.get("/api/remote_db/check_updates")
    assert resp.status_code == 200
    assert resp.json()["updates"] is False

    resp = await client.get("/api/remote_db/sync_download")
    assert resp.status_code == 200

    resp = await client.get("/api/remote_db/sync_upload")
    assert resp.status_code == 200
