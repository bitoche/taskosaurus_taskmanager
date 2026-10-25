"""Зависимости FastAPI для аутентификации, сессий и сервисов."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from taskmanager.core.config import settings
from taskmanager.core.database import get_session
from taskmanager.core.security import decode_access_token
from taskmanager.models import User
from taskmanager.services.auth_service import AuthService
from taskmanager.services.comment_service import CommentService
from taskmanager.services.priority_service import PriorityService
from taskmanager.services.tag_service import TagService
from taskmanager.services.task_service import TaskService


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    """Провайдер сервиса аутентификации."""
    return AuthService(session)


def get_task_service(session: AsyncSession = Depends(get_session)) -> TaskService:
    """Провайдер сервиса задач."""
    return TaskService(session)


def get_priority_service(session: AsyncSession = Depends(get_session)) -> PriorityService:
    """Провайдер сервиса приоритетов."""
    return PriorityService(session)


def get_tag_service(session: AsyncSession = Depends(get_session)) -> TagService:
    """Провайдер сервиса тегов."""
    return TagService(session)


def get_comment_service(session: AsyncSession = Depends(get_session)) -> CommentService:
    """Провайдер сервиса комментариев."""
    return CommentService(session)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Извлекает и валидирует токен сессии из HttpOnly Cookie (или заголовка Authorization).

    Raises:
        HTTPException(401): Если сессия отсутствует, токен недействителен или протух.
    """
    token: str | None = request.cookies.get(settings.auth_cookie_name)

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла или недействительна",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная полезная нагрузка сессии",
        )

    try:
        user_id = int(user_id_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный ID пользователя в сессии",
        )

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь заблокирован или не найден",
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Проверяет, обладает ли текущий пользователь правами администратора.

    Raises:
        HTTPException(403): Если роль пользователя отлична от 'admin'.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав: операция доступна только администраторам",
        )
    return current_user
