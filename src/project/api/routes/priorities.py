from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import Task, TaskPriority
from project.schemas import PriorityCreate, PriorityRead, PriorityUpdate

router = APIRouter()


@router.get("/", response_model=list[PriorityRead])
async def get_all_priorities(session: AsyncSession = Depends(get_session)):
    """Get all priorities ordered by sorting weight."""
    result = await session.execute(select(TaskPriority).order_by(TaskPriority.priority_sorting_weight))
    return result.scalars().all()


@router.get("/{priority_id}", response_model=PriorityRead)
async def get_priority(
    priority_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single priority by ID."""
    priority = await session.get(TaskPriority, priority_id)
    if priority is None:
        raise HTTPException(status_code=404, detail="Priority not found")
    return priority


@router.post("/", response_model=PriorityRead, status_code=201)
async def create_priority(
    body: PriorityCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new priority."""
    priority = TaskPriority(**body.model_dump())
    session.add(priority)
    await session.commit()
    await session.refresh(priority)
    return priority


@router.put("/{priority_id}", response_model=PriorityRead)
async def update_priority(
    priority_id: int,
    body: PriorityUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a priority."""
    priority = await session.get(TaskPriority, priority_id)
    if priority is None:
        raise HTTPException(status_code=404, detail="Priority not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(priority, key, value)

    await session.commit()
    await session.refresh(priority)
    return priority


@router.delete("/{priority_id}", status_code=204)
async def delete_priority(
    priority_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a priority. Nullifies task_priority_id on related tasks."""
    priority = await session.get(TaskPriority, priority_id)
    if priority is None:
        raise HTTPException(status_code=404, detail="Priority not found")

    # Nullify FK on tasks that reference this priority
    result = await session.execute(select(Task).where(Task.task_priority_id == priority_id))
    for task in result.scalars().all():
        task.task_priority_id = None

    await session.delete(priority)
    await session.commit()
