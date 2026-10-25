"""Сервис управления пользователями, аутентификацией и инвайтами."""

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.config import settings
from taskmanager.core.exceptions import AuthError, RateLimitExceededError, UserAlreadyExistsError
from taskmanager.core.security import hash_password, login_protector, verify_password
from taskmanager.models import InviteToken, User


class AuthService:
    """Сервис бизнес-логики пользователей и аутентификации."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """Находит пользователя по идентификатору."""
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        """Находит пользователя по имени пользователя."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def authenticate(self, username: str, password: str, client_ip: str) -> User:
        """Проверяет логин и пароль с защитой от брутфорса.

        Args:
            username: Логин.
            password: Введенный пароль.
            client_ip: IP-адрес клиента.

        Returns:
            Сущность пользователя при успешном входе.

        Raises:
            RateLimitExceededError: Если аккаунт или IP заблокированы из-за частых неудачных попыток.
            AuthError: При неверном пароле или отсутствии пользователя.
        """
        ip_key = f"ip:{client_ip}"
        user_key = f"{client_ip}:{username}"

        # 1. Проверяем блокировку IP или пары IP:username
        blocked_ip, remaining_ip = login_protector.is_blocked(ip_key)
        if blocked_ip:
            raise RateLimitExceededError(remaining_ip)

        blocked_user, remaining_user = login_protector.is_blocked(user_key)
        if blocked_user:
            raise RateLimitExceededError(remaining_user)

        # 2. Поиск пользователя
        user = await self.get_by_username(username)
        if not user or not user.is_active or not verify_password(password, user.hashed_password):
            login_protector.register_failure(ip_key)
            _, rem = login_protector.register_failure(user_key)
            if rem > 0:
                raise RateLimitExceededError(rem)
            raise AuthError("Неверное имя пользователя или пароль")

        # 3. Сброс счетчика неудач при успехе
        login_protector.register_success(ip_key)
        login_protector.register_success(user_key)
        return user

    async def create_user(
        self,
        username: str,
        password: str,
        role: str = "user",
        email: str | None = None,
    ) -> User:
        """Создает нового пользователя системы."""
        existing = await self.get_by_username(username)
        if existing:
            raise UserAlreadyExistsError(username)

        hashed = hash_password(password)
        user = User(
            username=username,
            hashed_password=hashed,
            role=role,
            email=email,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def create_invite(self, admin_user: User, hours_valid: int | None = None) -> InviteToken:
        """Генерирует криптографический одноразовый инвайт-токен."""
        if admin_user.role != "admin":
            raise AuthError("Только администраторы могут создавать инвайты")

        duration_hours = hours_valid or settings.invite_token_expire_hours
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=duration_hours)

        invite = InviteToken(
            token=token,
            created_by_user_id=admin_user.user_id,
            expires_at=expires_at,
            is_used=False,
        )
        self.session.add(invite)
        await self.session.flush()
        await self.session.refresh(invite)
        return invite

    async def register_with_invite(self, token_str: str, username: str, password: str) -> User:
        """Регистрирует нового пользователя по закрытому инвайт-токену."""
        invite = await self.session.get(InviteToken, token_str)
        now = datetime.now(UTC).replace(tzinfo=None)

        if not invite or invite.is_used or invite.expires_at < now:
            raise AuthError("Инвайт-токен недействителен или срок его действия истек")

        user = await self.create_user(username=username, password=password, role="user")

        invite.is_used = True
        invite.used_by_user_id = user.user_id
        await self.session.flush()
        return user

    async def list_active_invites(self) -> Sequence[InviteToken]:
        """Возвращает все активные (неиспользованные и непросроченные) инвайты."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stmt = (
            select(InviteToken)
            .where(InviteToken.is_used.is_(False), InviteToken.expires_at > now)
            .order_by(InviteToken.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
