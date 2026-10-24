from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Tasks ──────────────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    link_to_taskmanager: str | None = None
    due_date: date | str | None = None
    task_status: int | None = 1
    task_priority_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    link_to_taskmanager: str | None = None
    due_date: date | str | None = None
    closed_dttm: datetime | str | None = None
    task_status: int | None = None
    task_priority_id: int | None = None


class TaskRead(BaseModel):
    task_id: int
    title: str
    description: str | None = None
    link_to_taskmanager: str | None = None
    due_date: date | None = None
    closed_dttm: datetime | None = None
    created_at: datetime
    task_status: int | None = None
    task_priority_id: int | None = None

    model_config = {"from_attributes": True}


# ── Comments ───────────────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    task_id: int
    text: str = Field(..., min_length=1)


class CommentUpdate(BaseModel):
    text: str | None = None


class CommentRead(BaseModel):
    comment_id: int
    task_id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tags ───────────────────────────────────────────────────────────────────────


class TagCreate(BaseModel):
    tag_color: str = Field(..., min_length=1, max_length=50)
    tag_text: str = Field(..., min_length=1, max_length=255)


class TagUpdate(BaseModel):
    tag_color: str | None = None
    tag_text: str | None = None


class TagRead(BaseModel):
    task_tag_id: int
    tag_color: str
    tag_text: str

    model_config = {"from_attributes": True}


class TagAssign(BaseModel):
    task_tag_id: int
    task_id: int


class TagWithTasks(BaseModel):
    task_tag_id: int
    task_id: int

    model_config = {"from_attributes": True}


# ── Priorities ─────────────────────────────────────────────────────────────────


class PriorityCreate(BaseModel):
    priority_color: str = Field(..., min_length=1, max_length=50)
    priority_name: str = Field(..., min_length=1, max_length=255)
    priority_sorting_weight: int


class PriorityUpdate(BaseModel):
    priority_color: str | None = None
    priority_name: str | None = None
    priority_sorting_weight: int | None = None


class PriorityRead(BaseModel):
    priority_id: int
    priority_color: str
    priority_name: str
    priority_sorting_weight: int

    model_config = {"from_attributes": True}
