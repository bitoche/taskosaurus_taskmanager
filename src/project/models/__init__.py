from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.models.base import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TaskStatus(Base):
    __tablename__ = "task_status"

    status_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    tasks: Mapped[list["Task"]] = relationship(back_populates="status")


class TaskPriority(Base):
    __tablename__ = "task_priority"

    priority_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    priority_color: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority_sorting_weight: Mapped[int] = mapped_column(Integer, nullable=False)

    tasks: Mapped[list["Task"]] = relationship(back_populates="priority")


class TaskTagXTask(Base):
    """Many-to-many association between tags and tasks."""

    __tablename__ = "task_tag_x_task"

    task_tag_id: Mapped[int] = mapped_column(ForeignKey("task_tag.task_tag_id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.task_id", ondelete="CASCADE"), primary_key=True)


class TaskTag(Base):
    __tablename__ = "task_tag"

    task_tag_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_color: Mapped[str] = mapped_column(String(50), nullable=False)
    tag_text: Mapped[str] = mapped_column(String(255), nullable=False)

    tasks: Mapped[list["Task"]] = relationship(secondary="task_tag_x_task", back_populates="tags")


class Task(Base):
    __tablename__ = "task"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_to_taskmanager: Mapped[str | None] = mapped_column(String(500), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_dttm: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    task_status: Mapped[int | None] = mapped_column(ForeignKey("task_status.status_id"), nullable=True, default=1)
    task_priority_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_priority.priority_id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[TaskStatus | None] = relationship(back_populates="tasks")
    priority: Mapped[TaskPriority | None] = relationship(back_populates="tasks")
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    tags: Mapped[list[TaskTag]] = relationship(secondary="task_tag_x_task", back_populates="tasks")


class TaskComment(Base):
    __tablename__ = "task_comment"

    comment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)

    task: Mapped[Task] = relationship(back_populates="comments")
