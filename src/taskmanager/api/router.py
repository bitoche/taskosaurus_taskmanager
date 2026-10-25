"""Корневой роутер API приложения.

Объединяет все суб-роутеры под единым префиксом /api.
"""

from fastapi import APIRouter, Depends, Query

from taskmanager.api.dependencies import get_current_user, get_task_service
from taskmanager.api.routes import (
    auth,
    comments,
    health,
    priorities,
    tags,
    tasks,
    users,
)
from taskmanager.api.routes.tasks import execute_query, execute_query_get
from taskmanager.models import User
from taskmanager.schemas import SqlQueryRequest, SqlQueryResponse
from taskmanager.services.task_service import TaskService

api_router = APIRouter()

# Регистрация маршрутов с соответствующими префиксами и тегами OpenAPI
api_router.include_router(auth.router, prefix="/auth", tags=["Аутентификация"])
api_router.include_router(users.router, prefix="/users", tags=["Пользователи"])
api_router.include_router(health.router, tags=["Служебные"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Задачи"])
api_router.include_router(comments.router, prefix="/tasks", tags=["Комментарии"])
api_router.include_router(tags.router, prefix="/task_tags", tags=["Теги"])
api_router.include_router(priorities.router, prefix="/priority", tags=["Приоритеты"])


# Прямые алиасы для выполнения SQL-запросов (/api/query и /api/query/)
@api_router.get(
    "/query",
    response_model=SqlQueryResponse,
    tags=["Задачи"],
    summary="Выполнить SQL-запрос (GET-алиас)",
    description="Прямой алиас для выполнения безопасного SELECT-запроса через query-параметр.",
)
@api_router.get(
    "/query/",
    response_model=SqlQueryResponse,
    include_in_schema=False,
)
async def query_alias_get(
    query: str = Query(..., description="SQL-запрос SELECT", examples=["SELECT * FROM task"]),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SqlQueryResponse:
    """Прямой алиас GET /api/query."""
    return await execute_query_get(query=query, current_user=current_user, service=service)


@api_router.post(
    "/query",
    response_model=SqlQueryResponse,
    tags=["Задачи"],
    summary="Выполнить SQL-запрос (POST-алиас)",
    description="Прямой алиас для выполнения безопасного SELECT-запроса через тело JSON.",
)
@api_router.post(
    "/query/",
    response_model=SqlQueryResponse,
    include_in_schema=False,
)
async def query_alias_post(
    body: SqlQueryRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SqlQueryResponse:
    """Прямой алиас POST /api/query."""
    return await execute_query(body=body, current_user=current_user, service=service)
