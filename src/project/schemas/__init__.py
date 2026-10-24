"""Pydantic-схемы (DTO) для валидации входных и сериализации выходных данных API.

Содержит контракты для:
- Задач (создание, обновление, чтение).
- Комментариев к задачам.
- Тегов и их привязки к задачам.
- Приоритетов задач.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Задачи (Tasks) ─────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    """Схема для создания новой задачи.

    Attributes:
        title: Название задачи (обязательное поле).
        description: Подробное описание задачи (Markdown или текст).
        link_to_taskmanager: Внешняя ссылка на задачу в стороннем трекере.
        due_date: Дата планируемого выполнения (YYYY-MM-DD).
        task_status: Идентификатор статуса (по умолчанию 1 - active).
        task_priority_id: Идентификатор приоритета задачи.
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Заголовок задачи",
        examples=["Подготовить релиз v1.0"],
    )
    description: str | None = Field(
        default=None,
        max_length=10000,
        description="Подробное описание задачи",
        examples=["Проверить миграции БД и запустить смоук-тесты."],
    )
    link_to_taskmanager: str | None = Field(
        default=None,
        max_length=500,
        description="Внешняя ссылка на сторонний сервис или таск-трекер",
        examples=["https://tracker.example.com/issue/PROJ-123"],
    )
    due_date: date | str | None = Field(
        default=None,
        description="Дата срока выполнения задачи (YYYY-MM-DD)",
        examples=["2026-10-31"],
    )
    task_status: int | None = Field(
        default=1,
        description="Идентификатор статуса задачи (1 = active, 2 = completed)",
        examples=[1],
    )
    task_priority_id: int | None = Field(
        default=None,
        description="Идентификатор приоритета задачи",
        examples=[1],
    )


class TaskUpdate(BaseModel):
    """Схема для обновления существующей задачи.

    Все поля являются опциональными. Обновляются только переданные поля.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Новый заголовок задачи",
    )
    description: str | None = Field(
        default=None,
        max_length=10000,
        description="Новое описание задачи",
    )
    link_to_taskmanager: str | None = Field(
        default=None,
        max_length=500,
        description="Обновленная ссылка на внешний трекер",
    )
    due_date: date | str | None = Field(
        default=None,
        description="Новая дата срока выполнения (YYYY-MM-DD)",
    )
    closed_dttm: datetime | str | None = Field(
        default=None,
        description="Дата и время фактического закрытия задачи",
    )
    task_status: int | None = Field(
        default=None,
        description="Новый статус задачи (1 = active, 2 = completed)",
    )
    task_priority_id: int | None = Field(
        default=None,
        description="Новый идентификатор приоритета",
    )


class TaskRead(BaseModel):
    """Схема ответа с данными задачи.

    Attributes:
        task_id: Уникальный идентификатор задачи.
        title: Заголовок задачи.
        description: Описание задачи.
        link_to_taskmanager: Ссылка на сторонний трекер.
        due_date: Дата выполнения.
        closed_dttm: Время закрытия.
        created_at: Время создания записи.
        task_status: Идентификатор статуса.
        task_priority_id: Идентификатор приоритета.
    """

    task_id: int = Field(description="Уникальный ID задачи")
    title: str = Field(description="Заголовок задачи")
    description: str | None = Field(default=None, description="Описание задачи")
    link_to_taskmanager: str | None = Field(default=None, description="Внешняя ссылка")
    due_date: date | None = Field(default=None, description="Дата выполнения (YYYY-MM-DD)")
    closed_dttm: datetime | None = Field(default=None, description="Дата и время закрытия задачи")
    created_at: datetime = Field(description="Дата и время создания")
    task_status: int | None = Field(default=None, description="Статус задачи")
    task_priority_id: int | None = Field(default=None, description="ID приоритета")

    model_config = ConfigDict(from_attributes=True)


# ── Комментарии (Comments) ─────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    """Схема добавления комментария к задаче."""

    task_id: int = Field(..., description="ID задачи, к которой добавляется комментарий")
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Текст комментария",
        examples=["Согласовали перенос релиза на пятницу."],
    )


class CommentUpdate(BaseModel):
    """Схема изменения текста комментария."""

    text: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
        description="Обновленный текст комментария",
    )


class CommentRead(BaseModel):
    """Схема ответа с информацией о комментарии."""

    comment_id: int = Field(description="Уникальный ID комментария")
    task_id: int = Field(description="ID задачи")
    text: str = Field(description="Текст комментария")
    created_at: datetime = Field(description="Дата и время создания комментария")

    model_config = ConfigDict(from_attributes=True)


# ── Теги (Tags) ────────────────────────────────────────────────────────────────


class TagCreate(BaseModel):
    """Схема создания нового тега."""

    tag_color: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="HEX-код цвета или CSS-имя цвета бейджа",
        examples=["#4CAF50"],
    )
    tag_text: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Текстовое название тега",
        examples=["Backend"],
    )


class TagUpdate(BaseModel):
    """Схема изменения существующего тега."""

    tag_color: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Новый цвет бейджа",
    )
    tag_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Новое текстовое название тега",
    )


class TagRead(BaseModel):
    """Схема ответа с данными тега."""

    task_tag_id: int = Field(description="Уникальный ID тега")
    tag_color: str = Field(description="Цвет тега")
    tag_text: str = Field(description="Название тега")

    model_config = ConfigDict(from_attributes=True)


class TagAssign(BaseModel):
    """Схема назначения тега на задачу."""

    task_tag_id: int = Field(..., description="ID тега")
    task_id: int = Field(..., description="ID задачи")


class TagWithTasks(BaseModel):
    """Схема представления связи между тегом и задачей."""

    task_tag_id: int = Field(description="ID тега")
    task_id: int = Field(description="ID задачи")

    model_config = ConfigDict(from_attributes=True)


# ── Приоритеты (Priorities) ───────────────────────────────────────────────────


class PriorityCreate(BaseModel):
    """Схема создания нового приоритета."""

    priority_color: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="HEX-код цвета приоритета",
        examples=["#FF0000"],
    )
    priority_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название приоритета",
        examples=["Критический"],
    )
    priority_sorting_weight: int = Field(
        default=0,
        description="Вес для сортировки в интерфейсе (чем больше, тем выше)",
        examples=[100],
    )


class PriorityUpdate(BaseModel):
    """Схема изменения существующего приоритета."""

    priority_color: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Новый цвет приоритета",
    )
    priority_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Новое название приоритета",
    )
    priority_sorting_weight: int | None = Field(
        default=None,
        description="Новый вес сортировки",
    )


class PriorityRead(BaseModel):
    """Схема ответа с данными приоритета."""

    priority_id: int = Field(description="Уникальный ID приоритета")
    priority_color: str = Field(description="Цвет приоритета")
    priority_name: str = Field(description="Название приоритета")
    priority_sorting_weight: int = Field(description="Вес для сортировки")

    model_config = ConfigDict(from_attributes=True)
