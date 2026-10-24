"""Конфигурация приложения и управление переменными окружения.

Использует Pydantic Settings для загрузки настроек из переменных окружения
и .env-файлов с автоматической валидацией типов.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from taskmanager import __version__


class Settings(BaseSettings):
    """Класс настроек микросервиса управления задачами.

    Все параметры могут быть переопределены переменными окружения с префиксом `APP_`.
    Пример: `APP_DB_HOST=pg-server`, `APP_PORT=8080`.
    """

    app_name: str = Field(
        default="taskmanager",
        description="Название приложения для OpenAPI и логов",
    )
    app_version: str = Field(
        default=__version__,
        description="Версия микросервиса (считывается из pyproject.toml)",
    )
    debug: bool = Field(
        default=False,
        description="Флаг режима отладки (включает эхо SQL-запросов)",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Сетевой интерфейс для прослушивания HTTP-сервером",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Сетевой порт для HTTP-сервера",
    )

    # Параметры подключения к PostgreSQL
    db_host: str = Field(
        default="localhost",
        description="Хост сервера PostgreSQL",
    )
    db_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Порт сервера PostgreSQL",
    )
    db_user: str = Field(
        default="taskmanager",
        description="Имя пользователя базы данных",
    )
    db_password: str = Field(
        default="taskmanager",
        description="Пароль пользователя базы данных",
    )
    db_name: str = Field(
        default="taskmanager",
        description="Имя базы данных PostgreSQL",
    )

    # Пул подключений
    db_pool_size: int = Field(
        default=10,
        ge=1,
        description="Базовый размер пула подключений к БД",
    )
    db_max_overflow: int = Field(
        default=20,
        ge=0,
        description="Максимальное количество дополнительных подключений сверх pool_size",
    )

    @property
    def database_url(self) -> str:
        """Формирует строку подключения к PostgreSQL для асинхронного драйвера asyncpg.

        Returns:
            Строка подключения вида: postgresql+asyncpg://user:pass@host:port/dbname
        """
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
