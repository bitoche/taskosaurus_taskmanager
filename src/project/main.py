from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from project.api.router import api_router
from project.core.config import settings
from project.core.database import async_session_factory, engine
from project.models.base import Base


async def _seed_statuses() -> None:
    """Insert default task statuses if they don't exist."""
    async with async_session_factory() as session:
        # Check dialect: PostgreSQL supports ON CONFLICT, SQLite supports INSERT OR IGNORE
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
async def lifespan(app: FastAPI):
    # Startup: create tables & seed initial data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_statuses()
    yield
    # Shutdown: cleanly dispose connection pool
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Enable CORS for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
