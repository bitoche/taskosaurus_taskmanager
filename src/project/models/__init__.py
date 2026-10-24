"""ORM-модели базы данных для сервиса управления задачами.

Определяет сущности:
- Task: задача с заголовком, датой выполнения и связями.
- TaskStatus: статус задачи (активна, завершена).
- TaskPriority: приоритет с весом сортировки и цветовой меткой.
- TaskTag: тег/метка задачи.
- TaskTagXTask: таблица связи Many-to-Many между задачами и тегами.
- TaskComment: комментарии к задаче.
"""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from project.models.base import Base
from project.models.enums import TaskStatusEnum


def _utc_now() -> datetime:
    """Возвращает текущую временную метку в UTC без информации о часовом поясе."""
    return datetime.now(UTC).replace(tzinfo=None)


class TaskStatus(Base):
    """Справочник статусов задач.

    Attributes:
        status_id: Уникальный идентификатор статуса.
        status_name: Наименование статуса (например, 'active', 'completed').
        tasks: Список связанных задач.
    """

    __tablename__ = "task_status"

    status_id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Идентификатор статуса")
    status_name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, doc="Уникальное название статуса"
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="status", doc="Связанные задачи")


class TaskPriority(Base):
    """Справочник приоритетов задач.

    Attributes:
        priority_id: Уникальный идентификатор приоритета.
        priority_color: Цветовой HEX-код для отображения в интерфейсе.
        priority_name: Название приоритета (например, 'Высокий', 'Критический').
        priority_sorting_weight: Вес для упорядочивания при сортировке.
        tasks: Список связанных задач.
    """

    __tablename__ = "task_priority"

    priority_id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Идентификатор приоритета")
    priority_color: Mapped[str] = mapped_column(String(50), nullable=False, doc="HEX-код цвета приоритета")
    priority_name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Название приоритета")
    priority_sorting_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0, doc="Вес для сортировки")

    tasks: Mapped[list["Task"]] = relationship(back_populates="priority", doc="Связанные задачи")


class TaskTagXTask(Base):
    """Таблица связи 'многие-ко-многим' между тегами и задачами.

    Attributes:
        task_tag_id: Идентификатор тега.
        task_id: Идентификатор задачи.
    """

    __tablename__ = "task_tag_x_task"

    task_tag_id: Mapped[int] = mapped_column(
        ForeignKey("task_tag.task_tag_id", ondelete="CASCADE"),
        primary_key=True,
        doc="Внешний ключ на тег",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("task.task_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Внешний ключ на задачу с индексом для быстрого поиска",
    )


class TaskTag(Base):
    """Тег для категоризации задач.

    Attributes:
        task_tag_id: Уникальный идентификатор тега.
        tag_color: Цвет отображения бейджа тега в UI.
        tag_text: Текст/название тега.
        tasks: Задачи, которым присвоен данный тег.
    """

    __tablename__ = "task_tag"

    task_tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Идентификатор тега")
    tag_color: Mapped[str] = mapped_column(String(50), nullable=False, doc="HEX-код цвета бейджа")
    tag_text: Mapped[str] = mapped_column(String(255), nullable=False, doc="Текстовое значение тега")

    tasks: Mapped[list["Task"]] = relationship(
        secondary="task_tag_x_task",
        back_populates="tags",
        doc="Список задач с этим тегом",
    )


class Task(Base):
    """Основная сущность задачи в календаре.

    Attributes:
        task_id: Уникальный идентификатор задачи.
        title: Заголовок / краткое описание задачи.
        description: Подробное описание в формате текста или Markdown.
        link_to_taskmanager: Внешняя ссылка на связанную задачу/тикет.
        due_date: Дата выполнения задачи (индексирована для выборок календаря).
        closed_dttm: Время фактического закрытия задачи.
        created_at: Время создания записи в UTC.
        task_status: Внешний ключ статуса (1 = active, 2 = completed).
        task_priority_id: Внешний ключ приоритета задачи.
        status: Связанная сущность статуса.
        priority: Связанная сущность приоритета.
        comments: Список комментариев к задаче.
        tags: Список привязанных тегов.
    """

    __tablename__ = "task"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="Идентификатор задачи")
    title: Mapped[str] = mapped_column(String(255), nullable=False, doc="Заголовок задачи")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, doc="Детальное описание задачи")
    link_to_taskmanager: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="Внешняя ссылка на сторонний таск-трекер"
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True, doc="Дата срока выполнения (индексирована)"
    )
    closed_dttm: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, doc="Дата и время фактического закрытия"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        doc="Дата и время создания записи",
    )
    task_status: Mapped[int | None] = mapped_column(
        ForeignKey("task_status.status_id"),
        nullable=True,
        default=TaskStatusEnum.ACTIVE.value,
        index=True,
        doc="Внешний ключ статуса задачи",
    )
    task_priority_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_priority.priority_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Внешний ключ приоритета задачи",
    )

    status: Mapped[TaskStatus | None] = relationship(back_populates="tasks", doc="Объект статуса задачи")
    priority: Mapped[TaskPriority | None] = relationship(back_populates="tasks", doc="Объект приоритета задачи")
    comments: Mapped[list["TaskComment"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        doc="Комментарии к задаче (каскадное удаление)",
    )
    tags: Mapped[list[TaskTag]] = relationship(
        secondary="task_tag_x_task",
        back_populates="tasks",
        doc="Прикреплённые к задаче теги",
    )


class TaskComment(Base):
    """Комментарий или заметка к задаче.

    Attributes:
        comment_id: Уникальный идентификатор комментария.
        task_id: Идентификатор задачи, к которой оставлен комментарий.
        text: Текст комментария.
        created_at: Дата и время публикации комментария.
        task: Связанная задача.
    """

    __tablename__ = "task_comment"

    comment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, doc="Идентификатор комментария"
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("task.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Внешний ключ на задачу (индексирован)",
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, doc="Текст комментария")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        doc="Дата и время добавления комментария",
    )

    task: Mapped[Task] = relationship(back_populates="comments", doc="Родительская задача")
