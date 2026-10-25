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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Таблица пользователей
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("user_id", name="pk_users"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
    else:
        users_cols = [c["name"] for c in inspector.get_columns("users")]
        if "token_version" not in users_cols:
            op.add_column(
                "users",
                sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
            )

    # 2. Таблица инвайт-токенов
    if "invite_tokens" not in tables:
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

    # 3. Добавление колонки user_id в task_priority, task_tag, task
    for tbl in ["task_priority", "task_tag", "task"]:
        if tbl in tables:
            cols = [c["name"] for c in inspector.get_columns(tbl)]
            if "user_id" not in cols:
                op.add_column(tbl, sa.Column("user_id", sa.Integer(), nullable=True))
                if bind.dialect.name != "sqlite":
                    op.create_foreign_key(
                        f"fk_{tbl}_user",
                        tbl,
                        "users",
                        ["user_id"],
                        ["user_id"],
                        ondelete="CASCADE",
                    )
                op.create_index(f"ix_{tbl}_user_id", tbl, ["user_id"])

    # 4. Привязка существующих записей без владельца к первому пользователю
    try:
        first_user = bind.execute(sa.text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar()
        if first_user:
            for tbl in ["task_priority", "task_tag", "task"]:
                if tbl in tables:
                    bind.execute(
                        sa.text(f"UPDATE {tbl} SET user_id = :uid WHERE user_id IS NULL"),
                        {"uid": first_user},
                    )
    except Exception:
        pass


def downgrade() -> None:
    """Откат многопользовательской схемы."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    for tbl in ["task", "task_tag", "task_priority"]:
        if tbl in tables:
            cols = [c["name"] for c in inspector.get_columns(tbl)]
            if "user_id" in cols:
                op.drop_index(f"ix_{tbl}_user_id", table_name=tbl)
                if bind.dialect.name != "sqlite":
                    op.drop_constraint(f"fk_{tbl}_user", tbl, type_="foreignkey")
                op.drop_column(tbl, "user_id")

    if "invite_tokens" in tables:
        op.drop_table("invite_tokens")
    if "users" in tables:
        op.drop_index("ix_users_username", table_name="users")
        op.drop_table("users")
