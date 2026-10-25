"""Главный модуль запуска и конфигурации FastAPI приложения.

Содержит:
- Создание и настройку экземпляра FastAPI.
- Настройку промежуточного ПО CORS с поддержкой cookie-аутентификации.
- Регистрацию глобальных обработчиков доменных ошибок.
- Управление жизненным циклом (lifespan): инициализация схемы БД и закрытие пула соединений.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from taskmanager.api.router import api_router
from taskmanager.core.config import settings
from taskmanager.core.database import async_session_factory, engine
from taskmanager.core.exceptions import (
    AuthError,
    EntityNotFoundError,
    RateLimitExceededError,
    SqlSecurityError,
)
from taskmanager.core.logging import setup_logging
from taskmanager.models.base import Base

logger = logging.getLogger("taskmanager")


async def _seed_initial_statuses() -> None:
    """Заполняет справочник начальными статусами задач ('active', 'completed').

    Использует идемпотентную вставку для PostgreSQL и SQLite.
    """
    async with async_session_factory() as session:
        dialect_name = engine.dialect.name
        if dialect_name == "postgresql":
            sql = (
                "INSERT INTO task_status (status_id, status_name) "
                "VALUES (1, 'active'), (2, 'completed') "
                "ON CONFLICT (status_id) DO NOTHING"
            )
        else:
            sql = "INSERT OR IGNORE INTO task_status (status_id, status_name) VALUES (1, 'active'), (2, 'completed')"
        await session.execute(text(sql))
        await session.commit()


def _ensure_schema_columns(conn) -> None:
    """Гарантирует наличие колонок token_version и user_id при старте приложения."""
    from sqlalchemy import inspect
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "users" in tables:
        cols = [c["name"] for c in inspector.get_columns("users")]
        if "token_version" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1 NOT NULL"))

    for tbl in ["task_priority", "task_tag", "task"]:
        if tbl in tables:
            cols = [c["name"] for c in inspector.get_columns(tbl)]
            if "user_id" not in cols:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER"))
                first_user = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar()
                if first_user:
                    conn.execute(text(f"UPDATE {tbl} SET user_id = :uid WHERE user_id IS NULL"), {"uid": first_user})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Управляет жизненным циклом приложения FastAPI.

    Выполняет инициализацию при старте:
    - Создает необходимые таблицы, если они отсутствуют.
    - Гарантирует наличие колонок многопользовательской схемы.
    - Наполняет справочник статусов.

    Выполняет завершение при остановке:
    - Корректно закрывает пул соединений с базой данных.
    """
    logger.info("Запуск приложения %s v%s...", settings.app_name, settings.app_version)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_schema_columns)
    await _seed_initial_statuses()
    logger.info("База данных инициализирована. Сервис готов к приему запросов.")

    yield

    logger.info("Остановка приложения %s...", settings.app_name)
    await engine.dispose()
    logger.info("Пул соединений с БД закрыт.")


def create_app() -> FastAPI:
    """Фабрика создания и конфигурирования экземпляра FastAPI.

    Returns:
        Сконфигурированный объект FastAPI.
    """
    setup_logging()

    # Скрываем Swagger/OpenAPI в не-debug режиме для защиты от исследования ручек сторонними посетителями
    docs_url = "/docs" if settings.debug else None
    redoc_url = "/redoc" if settings.debug else None
    openapi_url = "/openapi.json" if settings.debug else None

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Асинхронный микросервис календаря и управления задачами с авторизацией и защитой от брутфорса.",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Настройка CORS для работы с SPA и сессионными cookie
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Глобальный перехват доменных исключений 'не найдено'
    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )

    # Глобальный перехват ошибок безопасности SQL
    @app.exception_handler(SqlSecurityError)
    async def sql_security_error_handler(request: Request, exc: SqlSecurityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )

    # Глобальный перехват ошибок аутентификации
    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
        )

    # Глобальный перехват превышения лимита запросов (брутфорс)
    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": exc.message},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    # Подключение корневого роутера
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
