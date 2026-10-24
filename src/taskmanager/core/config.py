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

    # Параметры логирования
    log_dir: str = Field(
        default="logs",
        description="Каталог для сохранения файлов логов",
    )
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file_name: str = Field(
        default="taskmanager.log",
        description="Имя основного файла логов",
    )
    log_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        description="Максимальный размер файла логов перед ротацией в байтах (по умолчанию 10 МБ)",
    )
    log_backup_count: int = Field(
        default=5,
        ge=0,
        description="Количество архивных файлов логов при ротации",
    )

    # Параметры подключения к базе данных
    database_url: str | None = Field(
        default=None,
        description="Полная строка подключения к БД (если не задана, формируется из параметров db_*)",
    )
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
    def effective_database_url(self) -> str:
        """Возвращает строку подключения к базе данных.

        Если задана явная `database_url` (или переменная APP_DATABASE_URL), используется она.
        Иначе формируется URL к PostgreSQL по умолчанию.
        """
        if self.database_url:
            return self.database_url
        from urllib.parse import quote_plus

        safe_password = quote_plus(self.db_password)
        safe_user = quote_plus(self.db_user)
        return f"postgresql+asyncpg://{safe_user}:{safe_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
