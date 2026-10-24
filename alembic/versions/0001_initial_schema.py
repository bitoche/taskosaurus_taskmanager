"""Начальная схема базы данных (Initial schema).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-24 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# Ревизионные идентификаторы, используемые Alembic
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применение миграции (создание таблиц, индексов и первичных данных)."""
    # 1. Таблица статусов задач
    op.create_table(
        "task_status",
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("status_name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("status_id", name="pk_task_status"),
        sa.UniqueConstraint("status_name", name="uq_task_status_status_name"),
    )

    # 2. Таблица приоритетов задач
    op.create_table(
        "task_priority",
        sa.Column("priority_id", sa.Integer(), nullable=False),
        sa.Column("priority_color", sa.String(length=50), nullable=False),
        sa.Column("priority_name", sa.String(length=255), nullable=False),
        sa.Column(
            "priority_sorting_weight",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.PrimaryKeyConstraint("priority_id", name="pk_task_priority"),
    )

    # 3. Таблица тегов
    op.create_table(
        "task_tag",
        sa.Column("task_tag_id", sa.Integer(), nullable=False),
        sa.Column("tag_color", sa.String(length=50), nullable=False),
        sa.Column("tag_text", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("task_tag_id", name="pk_task_tag"),
    )

    # 4. Основная таблица задач
    op.create_table(
        "task",
        sa.Column("task_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("link_to_taskmanager", sa.String(length=500), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("closed_dttm", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("task_status", sa.Integer(), nullable=True),
        sa.Column("task_priority_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_status"],
            ["task_status.status_id"],
            name="fk_task_task_status_task_status",
        ),
        sa.ForeignKeyConstraint(
            ["task_priority_id"],
            ["task_priority.priority_id"],
            name="fk_task_task_priority_id_task_priority",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("task_id", name="pk_task"),
    )
    op.create_index("ix_task_due_date", "task", ["due_date"], unique=False)
    op.create_index("ix_task_task_status", "task", ["task_status"], unique=False)
    op.create_index("ix_task_task_priority_id", "task", ["task_priority_id"], unique=False)

    # 5. Таблица связи тегов и задач (Many-to-Many)
    op.create_table(
        "task_tag_x_task",
        sa.Column("task_tag_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_tag_id"],
            ["task_tag.task_tag_id"],
            name="fk_task_tag_x_task_task_tag_id_task_tag",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.task_id"],
            name="fk_task_tag_x_task_task_id_task",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_tag_id", "task_id", name="pk_task_tag_x_task"),
    )
    op.create_index(
        "ix_task_tag_x_task_task_id",
        "task_tag_x_task",
        ["task_id"],
        unique=False,
    )

    # 6. Таблица комментариев
    op.create_table(
        "task_comment",
        sa.Column("comment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.task_id"],
            name="fk_task_comment_task_id_task",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("comment_id", name="pk_task_comment"),
    )
    op.create_index("ix_task_comment_task_id", "task_comment", ["task_id"], unique=False)

    # Заполнение справочника базовыми статусами
    op.execute(
        "INSERT INTO task_status (status_id, status_name) VALUES (1, 'active'), (2, 'completed') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    """Откат миграции (удаление таблиц в правильном порядке зависимостей)."""
    op.drop_index("ix_task_comment_task_id", table_name="task_comment")
    op.drop_table("task_comment")
    op.drop_index("ix_task_tag_x_task_task_id", table_name="task_tag_x_task")
    op.drop_table("task_tag_x_task")
    op.drop_index("ix_task_task_priority_id", table_name="task")
    op.drop_index("ix_task_task_status", table_name="task")
    op.drop_index("ix_task_due_date", table_name="task")
    op.drop_table("task")
    op.drop_table("task_tag")
    op.drop_table("task_priority")
    op.drop_table("task_status")
