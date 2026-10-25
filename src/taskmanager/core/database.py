"""Модуль управления подключением к базе данных и сессиями SQLAlchemy.

Предоставляет асинхронный движок (AsyncEngine), фабрику сессий
и зависимость FastAPI для безопасной работы с сессиями базы данных.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from taskmanager.core.config import settings

# Асинхронный движок базы данных (PostgreSQL или SQLite для локального запуска)
if settings.effective_database_url.startswith("sqlite"):
    engine = create_async_engine(
        settings.effective_database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
        """Включает поддержку внешних ключей и каскадного удаления для SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()
else:
    engine = create_async_engine(
        settings.effective_database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # Автоматический пинг соединений перед их выдачей из пула
    )

# Фабрика асинхронных сессий
async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Зависимость FastAPI для предоставления асинхронной сессии SQLAlchemy.

    Гарантирует автоматический коммит при успешном выполнении запроса
    или откат (rollback) изменений в случае возникновения исключения.

    Yields:
        AsyncSession: Активная сессия базы данных.

    Raises:
        Exception: Любая ошибка транзакции пробрасывается выше после rollback.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
