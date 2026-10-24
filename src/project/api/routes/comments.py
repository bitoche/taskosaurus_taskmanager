from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import TaskComment
from project.schemas import CommentCreate, CommentRead, CommentUpdate

router = APIRouter()


@router.get("/{task_id}/comments", response_model=list[CommentRead])
async def get_task_comments(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all comments for a task."""
    result = await session.execute(
        select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.created_at)
    )
    return result.scalars().all()


@router.post("/comment", response_model=CommentRead, status_code=201)
async def create_comment(
    body: CommentCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a comment on a task."""
    comment = TaskComment(**body.model_dump())
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment


@router.put("/comment/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: int,
    body: CommentUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a comment."""
    comment = await session.get(TaskComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(comment, key, value)

    await session.commit()
    await session.refresh(comment)
    return comment


@router.delete("/comment/delete/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a comment."""
    comment = await session.get(TaskComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    await session.delete(comment)
    await session.commit()
