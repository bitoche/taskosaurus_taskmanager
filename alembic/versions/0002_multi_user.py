"""Многопользовательская схема (Multi-user schema with auth and data isolation).

Revision ID: 0002_multi_user
Revises: 0001_initial
Create Date: 2026-10-25 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_multi_user"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создание таблиц пользователей, инвайтов и изоляция существующих сущностей."""
    # 1. Таблица пользователей
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # 2. Таблица инвайт-токенов
    op.create_table(
        "invite_tokens",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_invite_created_by",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by_user_id"],
            ["users.user_id"],
            name="fk_invite_used_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("token", name="pk_invite_tokens"),
    )

    # 3. Добавление колонки user_id в task, task_priority, task_tag
    op.add_column("task_priority", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_task_priority_user",
        "task_priority",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_task_priority_user_id", "task_priority", ["user_id"])

    op.add_column("task_tag", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_task_tag_user",
        "task_tag",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_task_tag_user_id", "task_tag", ["user_id"])

    op.add_column("task", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_task_user",
        "task",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_task_user_id", "task", ["user_id"])


def downgrade() -> None:
    """Откат многопользовательской схемы."""
    op.drop_index("ix_task_user_id", table_name="task")
    op.drop_constraint("fk_task_user", "task", type_="foreignkey")
    op.drop_column("task", "user_id")

    op.drop_index("ix_task_tag_user_id", table_name="task_tag")
    op.drop_constraint("fk_task_tag_user", "task_tag", type_="foreignkey")
    op.drop_column("task_tag", "user_id")

    op.drop_index("ix_task_priority_user_id", table_name="task_priority")
    op.drop_constraint("fk_task_priority_user", "task_priority", type_="foreignkey")
    op.drop_column("task_priority", "user_id")

    op.drop_table("invite_tokens")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
