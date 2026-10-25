"""Маршруты аутентификации, сессий и управления инвайтами."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from taskmanager.api.dependencies import (
    get_auth_service,
    get_current_admin,
    get_current_user,
)
from taskmanager.core.config import settings
from taskmanager.core.exceptions import AuthError, RateLimitExceededError, UserAlreadyExistsError
from taskmanager.core.security import create_access_token
from taskmanager.models import User
from taskmanager.schemas import (
    InviteCreate,
    InviteRead,
    RegisterWithInvite,
    UserLogin,
    UserRead,
)
from taskmanager.services.auth_service import AuthService

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Извлекает реальный IP клиента с учетом прокси."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.post(
    "/login",
    response_model=UserRead,
    summary="Вход в систему",
    description="Проверяет логин и пароль с защитой от брутфорса и устанавливает защищенную HttpOnly cookie сессии.",
)
async def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> UserRead:
    """Аутентификация пользователя и установка сессии."""
    client_ip = _get_client_ip(request)
    try:
        user = await service.authenticate(
            username=credentials.username,
            password=credentials.password,
            client_ip=client_ip,
        )
    except RateLimitExceededError as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=err.message,
            headers={"Retry-After": str(err.retry_after_seconds)},
        ) from err
    except AuthError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err.message,
        ) from err

    token = create_access_token({"sub": str(user.user_id), "role": user.role})
    max_age = settings.access_token_expire_minutes * 60

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return UserRead.model_validate(user)


@router.post(
    "/logout",
    summary="Выход из системы",
    description="Сбрасывает сессионную cookie.",
)
async def logout(response: Response) -> dict[str, str]:
    """Сброс сессии."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )
    return {"message": "Успешный выход из системы"}


@router.get(
    "/me",
    response_model=UserRead,
    summary="Текущий пользователь",
    description="Возвращает профиль аутентифицированного пользователя.",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Получение профиля текущего пользователя."""
    return UserRead.model_validate(current_user)


@router.post(
    "/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать инвайт (только для админа)",
    description="Генерирует криптографический одноразовый токен для регистрации нового пользователя.",
)
async def create_invite(
    dto: InviteCreate,
    current_admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
) -> InviteRead:
    """Создание одноразового инвайта."""
    invite = await service.create_invite(admin_user=current_admin, hours_valid=dto.expires_hours)
    return InviteRead.model_validate(invite)


@router.get(
    "/invites",
    response_model=list[InviteRead],
    summary="Список активных инвайтов (только для админа)",
    description="Возвращает неиспользованные и непросроченные инвайты.",
)
async def list_invites(
    _admin: User = Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
) -> Sequence[InviteRead]:
    """Получение списка активных инвайтов."""
    invites = await service.list_active_invites()
    return [InviteRead.model_validate(inv) for inv in invites]


@router.post(
    "/register-with-invite",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация по инвайт-токену",
    description="Создает нового пользователя по валидному одноразовому токену приглашения.",
)
async def register_with_invite(
    dto: RegisterWithInvite,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> UserRead:
    """Регистрация по закрытому инвайту и автоматический вход."""
    try:
        user = await service.register_with_invite(
            token_str=dto.token,
            username=dto.username,
            password=dto.password,
        )
    except (AuthError, UserAlreadyExistsError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    # Автоматически устанавливаем сессионную cookie новому пользователю
    token = create_access_token({"sub": str(user.user_id), "role": user.role})
    max_age = settings.access_token_expire_minutes * 60

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return UserRead.model_validate(user)
