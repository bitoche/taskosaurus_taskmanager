from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import TaskTag, TaskTagXTask
from project.schemas import TagAssign, TagCreate, TagRead, TagUpdate, TagWithTasks

router = APIRouter()


@router.get("/", response_model=list[TagRead])
async def get_all_tags(session: AsyncSession = Depends(get_session)):
    """Get all tags."""
    result = await session.execute(select(TaskTag))
    return result.scalars().all()


@router.get("/tasks", response_model=list[TagWithTasks])
async def get_all_tags_with_tasks(session: AsyncSession = Depends(get_session)):
    """Get all tag ↔ task assignments."""
    result = await session.execute(select(TaskTagXTask))
    return result.scalars().all()


@router.post("/", response_model=TagRead, status_code=201)
async def create_tag(
    body: TagCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new tag."""
    tag = TaskTag(**body.model_dump())
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return tag


@router.post("/assign", response_model=TagWithTasks, status_code=201)
async def assign_tag_to_task(
    body: TagAssign,
    session: AsyncSession = Depends(get_session),
):
    """Assign a tag to a task."""
    link = TaskTagXTask(task_tag_id=body.task_tag_id, task_id=body.task_id)
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


@router.put("/{task_tag_id}", response_model=TagRead)
async def update_tag(
    task_tag_id: int,
    body: TagUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a tag."""
    tag = await session.get(TaskTag, task_tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(tag, key, value)

    await session.commit()
    await session.refresh(tag)
    return tag


@router.delete("/unassign/{task_tag_id}/task/{task_id}", status_code=204)
async def unassign_tag_from_task(
    task_tag_id: int,
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove a tag from a task."""
    await session.execute(
        delete(TaskTagXTask).where(
            TaskTagXTask.task_tag_id == task_tag_id,
            TaskTagXTask.task_id == task_id,
        )
    )
    await session.commit()


@router.delete("/{task_tag_id}", status_code=204)
async def delete_tag(
    task_tag_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a tag globally (cascade removes assignments)."""
    tag = await session.get(TaskTag, task_tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    await session.delete(tag)
    await session.commit()
