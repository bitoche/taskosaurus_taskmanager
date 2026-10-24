"""Скрипт конфигурации окружения миграций Alembic в асинхронном режиме."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import taskmanager.models  # noqa: F401 - регистрация всех моделей в Base.metadata
from alembic import context
from taskmanager.core.config import settings
from taskmanager.models.base import Base

# Объект конфигурации Alembic из файла alembic.ini
config = context.config

# Настройка логирования из ini-файла
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Динамическая подстановка URL базы данных из настроек приложения
config.set_main_option("sqlalchemy.url", settings.database_url)

# Метаданные моделей для поддержки автогенерации миграций (--autogenerate)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме (без активного подключения к БД).

    Генерирует SQL-скрипты миграций без непосредственного выполнения.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Вспомогательная функция для применения миграций в открытом соединении."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Создает асинхронный движок и запускает миграции в синхронном контексте."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме с активным подключением к БД."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
