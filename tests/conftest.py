"""Конфигурация тестового окружения и фикстуры pytest.

Настраивает тестовую in-memory базу данных SQLite (aiosqlite),
переопределяет зависимости FastAPI и предоставляет асинхронный HTTP-клиент.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from taskmanager.core.config import settings
from taskmanager.core.database import get_session
from taskmanager.core.security import create_access_token, hash_password, login_protector
from taskmanager.main import app
from taskmanager.models import User
from taskmanager.models.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Включает поддержку внешних ключей в тестовой SQLite БД."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture
def anyio_backend() -> str:
    """Определяет бэкенд для AnyIO (asyncio)."""
    return "asyncio"


@pytest.fixture(autouse=True)
async def prepare_database() -> AsyncGenerator[None]:
    """Автоматически создает таблицы и сиды перед каждым тестом и очищает после."""
    login_protector.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("INSERT OR IGNORE INTO task_status (status_id, status_name) VALUES (1, 'active'), (2, 'completed')")
        )
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    login_protector.clear()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    """Предоставляет тестовую изолированную асинхронную сессию БД."""
    async with TestingSessionLocal() as sess:
        yield sess


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Создает стандартного тестового пользователя."""
    user = User(
        username="testuser",
        hashed_password=hash_password("Password123!"),
        role="user",
        email="test@example.com",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def admin_user(session: AsyncSession) -> User:
    """Создает тестового администратора."""
    admin = User(
        username="admin",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        email="admin@example.com",
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


@pytest.fixture
async def second_user(session: AsyncSession) -> User:
    """Создает второго тестового пользователя для проверки изоляции."""
    user2 = User(
        username="seconduser",
        hashed_password=hash_password("Password456!"),
        role="user",
        email="second@example.com",
        is_active=True,
    )
    session.add(user2)
    await session.commit()
    await session.refresh(user2)
    return user2


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Предоставляет неавторизованный асинхронный HTTP-клиент."""

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient]:
    """Предоставляет HTTP-клиент с сессией обычного пользователя."""

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield session

    token = create_access_token({"sub": str(test_user.user_id), "role": test_user.role})

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    cookies = {settings.auth_cookie_name: token}
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(session: AsyncSession, admin_user: User) -> AsyncGenerator[AsyncClient]:
    """Предоставляет HTTP-клиент с сессией администратора."""

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield session

    token = create_access_token({"sub": str(admin_user.user_id), "role": admin_user.role})

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    cookies = {settings.auth_cookie_name: token}
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as ac:
        yield ac
    app.dependency_overrides.clear()
