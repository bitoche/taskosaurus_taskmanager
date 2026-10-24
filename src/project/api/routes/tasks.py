from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import Task
from project.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter()

COMPLETED_STATUS_ID = 2
ACTIVE_STATUS_ID = 1


def _parse_date(val: date | str | None) -> date | None:
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(val[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {val}. Expected YYYY-MM-DD")


def _parse_datetime(val: datetime | str | None) -> datetime | None:
    if val is None or isinstance(val, datetime):
        return val
    try:
        clean = val.replace("T", " ")
        if len(clean) > 19:
            clean = clean[:19]
        return datetime.fromisoformat(clean)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format: {val}. Expected YYYY-MM-DD HH:MM:SS or ISO",
        )


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    date_from: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    """Get tasks, optionally filtered by date range."""
    stmt = select(Task).order_by(Task.due_date.asc().nulls_last(), Task.task_id.asc())

    if date_from and date_to:
        d_from = _parse_date(date_from)
        d_to = _parse_date(date_to)
        stmt = stmt.where(Task.due_date >= d_from, Task.due_date <= d_to)

    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/between", response_model=list[TaskRead])
async def list_tasks_between(
    date_from: str = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(..., description="End date (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_session),
):
    """Get tasks within a date range (compatible with legacy /between endpoint)."""
    return await list_tasks(date_from=date_from, date_to=date_to, session=session)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """Get a single task by ID."""
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new task."""
    data = body.model_dump(exclude_unset=True)
    if "due_date" in data:
        data["due_date"] = _parse_date(data["due_date"])

    task = Task(**data)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a task. Preserves completion and status business logic."""
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    data = body.model_dump(exclude_unset=True)

    if "due_date" in data:
        data["due_date"] = _parse_date(data["due_date"])
    if "closed_dttm" in data:
        data["closed_dttm"] = _parse_datetime(data["closed_dttm"])

    # If closed_dttm is provided, mark status as completed (2)
    if data.get("closed_dttm") is not None:
        data["task_status"] = COMPLETED_STATUS_ID

    # Status transitions
    if "task_status" in data and data["task_status"] is not None:
        if data["task_status"] == ACTIVE_STATUS_ID:
            data["closed_dttm"] = None
        elif data["task_status"] == COMPLETED_STATUS_ID:
            if task.closed_dttm is None and data.get("closed_dttm") is None:
                data["closed_dttm"] = datetime.now(UTC).replace(tzinfo=None)

    for key, value in data.items():
        setattr(task, key, value)

    await session.commit()
    await session.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a task and its comments."""
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await session.delete(task)
    await session.commit()
