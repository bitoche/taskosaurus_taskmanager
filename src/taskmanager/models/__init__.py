"""ORM-модели базы данных для сервиса управления задачами.

Определяет сущности:
- User: пользователь системы (аутентификация, роль, статус).
- InviteToken: одноразовый токен закрытой регистрации по приглашению.
- Task: задача с заголовком, датой выполнения, связями и привязкой к пользователю.
- TaskStatus: статус задачи (активна, завершена).
- TaskPriority: приоритет с весом сортировки, цветом и привязкой к пользователю.
- TaskTag: тег/метка задачи с привязкой к пользователю.
- TaskTagXTask: таблица связи Many-to-Many между задачами и тегами.
- TaskComment: комментарии к задаче.
"""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taskmanager.models.base import Base
from taskmanager.models.enums import TaskStatusEnum


def _utc_now() -> datetime:
    """Возвращает текущую временную метку в UTC без информации о часовом поясе."""
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    """Пользователь системы задач.

    Attributes:
        user_id: Уникальный идентификатор пользователя.
        username: Уникальное имя пользователя для входа.
        email: Электронная почта (опционально).
        hashed_password: Захэшированный пароль.
        role: Роль в системе ('admin' или 'user').
        is_active: Флаг активности аккаунта.
        created_at: Дата и время регистрации.
        tasks: Персональные задачи пользователя.
        priorities: Персональные приоритеты пользователя.
        tags: Персональные теги пользователя.
    """

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="ID пользователя")
    username: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False, doc="Имя пользователя (логин)"
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, doc="Электронная почта")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, doc="Хэш пароля")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user", doc="Роль (admin или user)")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, doc="Флаг активности")
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, doc="Версия токена для инвалидации сессий"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now, doc="Дата и время создания"
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", doc="Задачи пользователя"
    )
    priorities: Mapped[list["TaskPriority"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", doc="Приоритеты пользователя"
    )
    tags: Mapped[list["TaskTag"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", doc="Теги пользователя"
    )


class InviteToken(Base):
    """Одноразовый токен закрытой регистрации.

    Attributes:
        token: Уникальный криптографический строковый токен.
        created_by_user_id: ID создавшего токен администратора.
        expires_at: Срок действия токена (UTC).
        is_used: Флаг использования токена.
        used_by_user_id: ID пользователя, зарегистрировавшегося по токену.
        created_at: Время создания токена.
    """

    __tablename__ = "invite_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True, doc="Токен приглашения")
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, doc="Админ-создатель"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, doc="Дата протухания токена")
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="Флаг погашения")
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, doc="Зарегистрированный пользователь"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, doc="Дата создания токена")

    creator: Mapped[User] = relationship(foreign_keys=[created_by_user_id], doc="Создатель инвайта")
    consumer: Mapped[User | None] = relationship(foreign_keys=[used_by_user_id], doc="Пользователь инвайта")


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
    """Справочник приоритетов задач (персональный для каждого пользователя).

    Attributes:
        priority_id: Уникальный идентификатор приоритета.
        user_id: ID пользователя-владельца приоритета.
        priority_color: Цветовой HEX-код для отображения в интерфейсе.
        priority_name: Название приоритета (например, 'Высокий', 'Критический').
        priority_sorting_weight: Вес для упорядочивания при сортировке.
        tasks: Список связанных задач.
        user: Пользователь-владелец.
    """

    __tablename__ = "task_priority"

    priority_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="ID приоритета")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True, doc="ID владельца"
    )
    priority_color: Mapped[str] = mapped_column(String(50), nullable=False, doc="HEX-код цвета приоритета")
    priority_name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Название приоритета")
    priority_sorting_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0, doc="Вес для сортировки")

    user: Mapped[User] = relationship(back_populates="priorities", doc="Владелец приоритета")
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
    """Тег для категоризации задач (персональный для каждого пользователя).

    Attributes:
        task_tag_id: Уникальный идентификатор тега.
        user_id: ID пользователя-владельца тега.
        tag_color: Цвет отображения бейджа тега в UI.
        tag_text: Текст/название тега.
        user: Пользователь-владелец.
        tasks: Задачи, которым присвоен данный тег.
    """

    __tablename__ = "task_tag"

    task_tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="ID тега")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True, doc="ID владельца"
    )
    tag_color: Mapped[str] = mapped_column(String(50), nullable=False, doc="HEX-код цвета бейджа")
    tag_text: Mapped[str] = mapped_column(String(255), nullable=False, doc="Текстовое значение тега")

    user: Mapped[User] = relationship(back_populates="tags", doc="Владелец тега")
    tasks: Mapped[list["Task"]] = relationship(
        secondary="task_tag_x_task",
        back_populates="tags",
        doc="Список задач с этим тегом",
    )


class Task(Base):
    """Основная сущность задачи в календаре (изолированная по пользователю).

    Attributes:
        task_id: Уникальный идентификатор задачи.
        user_id: Идентификатор пользователя-владельца задачи.
        title: Заголовок / краткое описание задачи.
        description: Подробное описание в формате текста или Markdown.
        link_to_taskmanager: Внешняя ссылка на связанную задачу/тикет.
        due_date: Дата выполнения задачи (индексирована для выборок календаря).
        closed_dttm: Время фактического закрытия задачи.
        created_at: Время создания записи в UTC.
        task_status: Внешний ключ статуса (1 = active, 2 = completed).
        task_priority_id: Внешний ключ приоритета задачи.
        user: Объект пользователя-владельца.
        status: Связанная сущность статуса.
        priority: Связанная сущность приоритета.
        comments: Список комментариев к задаче.
        tags: Список привязанных тегов.
    """

    __tablename__ = "task"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, doc="Идентификатор задачи")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True, doc="ID пользователя"
    )
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

    user: Mapped[User] = relationship(back_populates="tasks", doc="Пользователь-владелец задачи")
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
