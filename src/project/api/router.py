"""Корневой роутер API приложения.

Объединяет все суб-роутеры под единым префиксом /api.
"""

from fastapi import APIRouter

from project.api.routes import (
    comments,
    health,
    priorities,
    remote_db,
    tags,
    tasks,
)

api_router = APIRouter()

# Регистрация маршрутов с соответствующими префиксами и тегами OpenAPI
api_router.include_router(health.router, tags=["Служебные"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Задачи"])
api_router.include_router(comments.router, prefix="/tasks", tags=["Комментарии"])
api_router.include_router(tags.router, prefix="/task_tags", tags=["Теги"])
api_router.include_router(priorities.router, prefix="/priority", tags=["Приоритеты"])
api_router.include_router(remote_db.router, prefix="/remote_db", tags=["Синхронизация (Legacy)"])
