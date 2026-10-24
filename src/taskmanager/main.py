"""Главный модуль запуска и конфигурации FastAPI приложения.

Содержит:
- Создание и настройку экземпляра FastAPI.
- Настройку промежуточного ПО CORS.
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
from taskmanager.core.exceptions import EntityNotFoundError, SqlSecurityError
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Управляет жизненным циклом приложения FastAPI.

    Выполняет инициализацию при старте:
    - Создает необходимые таблицы, если они отсутствуют.
    - Наполняет справочник статусов.

    Выполняет завершение при остановке:
    - Корректно закрывает пул соединений с базой данных.

    Args:
        app: Экземпляр приложения FastAPI.

    Yields:
        None во время работы приложения.
    """
    logger.info("Запуск приложения %s v%s...", settings.app_name, settings.app_version)
    # Старт приложения
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_initial_statuses()
    logger.info("База данных инициализирована. Сервис готов к приему запросов.")

    yield

    # Завершение работы приложения
    logger.info("Остановка приложения %s...", settings.app_name)
    await engine.dispose()
    logger.info("Пул соединений с БД закрыт.")


def create_app() -> FastAPI:
    """Фабрика создания и конфигурирования экземпляра FastAPI.

    Returns:
        Сконфигурированный объект FastAPI.
    """
    # Инициализация логирования перед стартом приложения
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Асинхронный микросервис календаря и управления задачами на FastAPI и PostgreSQL.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Настройка CORS для работы с SPA (React/Vite)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Глобальный перехват доменных исключений 'не найдено' (Best Practice)
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

    # Подключение корневого роутера
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
