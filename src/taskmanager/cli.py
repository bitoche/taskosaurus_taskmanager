"""Консольная утилита администрирования taskmanager.

Позволяет:
- Создать первичного администратора системы:
    taskmanager-cli create-admin --username admin --password "StrongPass123"
- Сгенерировать одноразовый инвайт-токен:
    taskmanager-cli create-invite --admin admin --hours 48
- Вывести список зарегистрированных пользователей:
    taskmanager-cli list-users
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from taskmanager.core.database import async_session_factory, engine
from taskmanager.models import Base, User
from taskmanager.services.auth_service import AuthService


async def _init_db() -> None:
    """Создает таблицы базы данных при их отсутствии."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def cmd_create_admin(args: argparse.Namespace) -> None:
    """Создание учетной записи администратора."""
    await _init_db()
    async with async_session_factory() as session:
        auth = AuthService(session)
        existing = await auth.get_by_username(args.username)
        if existing:
            print(f"Ошибка: пользователь с логином '{args.username}' уже существует.", file=sys.stderr)
            sys.exit(1)

        user = await auth.create_user(
            username=args.username,
            password=args.password,
            role="admin",
            email=args.email,
        )
        await session.commit()
        print(f"[OK] Администратор '{user.username}' (ID: {user.user_id}) успешно создан.")


async def cmd_create_invite(args: argparse.Namespace) -> None:
    """Генерация закрытого одноразового инвайт-токена."""
    await _init_db()
    async with async_session_factory() as session:
        auth = AuthService(session)
        admin = await auth.get_by_username(args.admin)
        if not admin or admin.role != "admin":
            print(
                f"Ошибка: администратор '{args.admin}' не найден или не обладает правами админа.",
                file=sys.stderr,
            )
            sys.exit(1)

        invite = await auth.create_invite(admin_user=admin, hours_valid=args.hours)
        await session.commit()
        print("[OK] Инвайт-токен создан успешно:")
        print(f"  Токен: {invite.token}")
        print(f"  Действителен до (UTC): {invite.expires_at}")
        print(f"  Ссылка для регистрации: /?invite={invite.token}")


async def cmd_delete_invite(args: argparse.Namespace) -> None:
    """Удаление инвайт-токена."""
    await _init_db()
    async with async_session_factory() as session:
        auth = AuthService(session)
        deleted = await auth.delete_invite(args.token)
        if not deleted:
            print(f"[ERROR] Инвайт '{args.token}' не найден.", file=sys.stderr)
            sys.exit(1)
        await session.commit()
        print(f"[OK] Инвайт '{args.token}' успешно удален.")


async def cmd_list_users(_args: argparse.Namespace) -> None:
    """Вывод списка пользователей."""
    await _init_db()
    async with async_session_factory() as session:
        stmt = select(User).order_by(User.user_id.asc())
        result = await session.execute(stmt)
        users = result.scalars().all()
        if not users:
            print("Пользователи не найдены.")
            return

        print(f"{'ID':<6} {'Логин':<20} {'Роль':<10} {'Активен':<10} {'Создан'}")
        print("-" * 65)
        for u in users:
            print(f"{u.user_id:<6} {u.username:<20} {u.role:<10} {str(u.is_active):<10} {u.created_at}")


def cli() -> None:
    """Точка входа CLI утилиты."""
    parser = argparse.ArgumentParser(description="Утилита администрирования TaskManager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    p_admin = subparsers.add_parser("create-admin", help="Создать администратора")
    p_admin.add_argument("--username", "-u", required=True, help="Логин администратора")
    p_admin.add_argument("--password", "-p", required=True, help="Пароль администратора")
    p_admin.add_argument("--email", "-e", required=False, default=None, help="Электронная почта")

    # create-invite
    p_inv = subparsers.add_parser("create-invite", help="Создать одноразовый инвайт")
    p_inv.add_argument("--admin", "-a", required=True, help="Логин администратора-создателя")
    p_inv.add_argument("--hours", "-t", type=int, default=48, help="Срок жизни в часах (по умолчанию 48)")

    # delete-invite
    p_del_inv = subparsers.add_parser("delete-invite", help="Удалить инвайт")
    p_del_inv.add_argument("--token", "-k", required=True, help="Токен инвайта для удаления")

    # list-users
    subparsers.add_parser("list-users", help="Список пользователей")

    args = parser.parse_args()

    if args.command == "create-admin":
        asyncio.run(cmd_create_admin(args))
    elif args.command == "create-invite":
        asyncio.run(cmd_create_invite(args))
    elif args.command == "delete-invite":
        asyncio.run(cmd_delete_invite(args))
    elif args.command == "list-users":
        asyncio.run(cmd_list_users(args))


if __name__ == "__main__":
    cli()
