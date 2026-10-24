from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "taskmanager"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "taskmanager"
    db_password: str = "taskmanager"
    db_name: str = "taskmanager"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_prefix": "APP_"}


settings = Settings()
