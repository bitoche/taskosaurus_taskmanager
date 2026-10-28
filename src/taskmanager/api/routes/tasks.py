"""Маршруты API для управления задачами."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status

from taskmanager.api.dependencies import get_current_user, get_task_service
from taskmanager.core.exceptions import SqlSecurityError
from taskmanager.models import Task, User
from taskmanager.schemas import (
    SqlQueryRequest,
    SqlQueryResponse,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from taskmanager.services.task_service import TaskService

router = APIRouter()


@router.get(
    "",
    response_model=list[TaskRead],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=list[TaskRead],
    status_code=status.HTTP_200_OK,
    summary="Получить список задач",
    description="Возвращает список всех задач текущего пользователя. Поддерживает фильтрацию по диапазону дат.",
    response_description="Список задач",
)
async def list_tasks(
    date_from: str | None = Query(
        None,
        description="Начальная дата в формате YYYY-MM-DD",
        examples=["2026-10-01"],
    ),
    date_to: str | None = Query(
        None,
        description="Конечная дата в формате YYYY-MM-DD",
        examples=["2026-10-31"],
    ),
    no_date: bool = Query(
        False,
        description="Только задачи без даты (due_date is NULL)",
    ),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Sequence[Task]:
    """Получает список задач текущего пользователя с опциональной фильтрацией по диапазону дат."""
    is_no_date = no_date if isinstance(no_date, bool) else False
    try:
        return await service.list_tasks(
            user_id=current_user.user_id,
            date_from=date_from,
            date_to=date_to,
            no_date=is_no_date,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректный формат даты: {err}. Ожидается YYYY-MM-DD",
        ) from err


@router.get(
    "/between",
    response_model=list[TaskRead],
    status_code=status.HTTP_200_OK,
    summary="Получить задачи за период (совместимость со старым API)",
    description="Эндпоинт обратной совместимости. Возвращает задачи за указанный диапазон дат.",
    response_description="Список задач в диапазоне",
)
async def list_tasks_between(
    date_from: str = Query(
        ...,
        description="Начальная дата (YYYY-MM-DD)",
        examples=["2026-10-01"],
    ),
    date_to: str = Query(
        ...,
        description="Конечная дата (YYYY-MM-DD)",
        examples=["2026-10-31"],
    ),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Sequence[Task]:
    """Возвращает задачи в диапазоне дат (алиас эндпоинта /between)."""
    return await list_tasks(
        date_from=date_from,
        date_to=date_to,
        no_date=False,
        current_user=current_user,
        service=service,
    )


@router.get(
    "/query",
    response_model=SqlQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Выполнить безопасный SQL-запрос к базе данных задач (GET)",
    description=(
        "Выполняет пользовательский SELECT SQL-запрос к базе данных задач через GET-параметр. "
        "Для обычных пользователей результат изолирован их данными; для администратора доступна вся БД."
    ),
    response_description="Результаты запроса (колонки, строки, количество, признак изоляции)",
)
@router.get(
    "/query/",
    response_model=SqlQueryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def execute_query_get(
    query: str = Query(..., description="SQL-запрос SELECT", examples=["SELECT * FROM task"]),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SqlQueryResponse:
    """Выполняет безопасный пользовательский SQL-запрос через query-параметр."""
    try:
        columns, rows, count, has_more, is_isolated = await service.execute_query(query, user=current_user)
        return SqlQueryResponse(
            columns=columns,
            rows=rows,
            count=count,
            has_more=has_more,
            is_isolated=is_isolated,
        )
    except SqlSecurityError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.message,
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка валидации SQL-запроса: {err}",
        ) from err


@router.post(
    "/query",
    response_model=SqlQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Выполнить безопасный SQL-запрос к базе данных задач (POST)",
    description=(
        "Выполняет пользовательский SELECT SQL-запрос к базе данных в режиме только для чтения. "
        "Для обычных пользователей результат изолирован их данными; для администратора доступна вся БД."
    ),
    response_description="Результаты запроса (колонки, строки, количество, признак изоляции)",
)
@router.post(
    "/query/",
    response_model=SqlQueryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def execute_query(
    body: SqlQueryRequest,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> SqlQueryResponse:
    """Выполняет безопасный пользовательский SQL-запрос через тело запроса."""
    try:
        columns, rows, count, has_more, is_isolated = await service.execute_query(body.query, user=current_user)
        return SqlQueryResponse(
            columns=columns,
            rows=rows,
            count=count,
            has_more=has_more,
            is_isolated=is_isolated,
        )
    except SqlSecurityError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.message,
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка валидации SQL-запроса: {err}",
        ) from err


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Получить задачу по ID",
    description="Возвращает детальную информацию о конкретной задаче текущего пользователя.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Задача не найдена"}},
)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Ищет и возвращает задачу по её ID и владельцу."""
    task = await service.get_by_id(task_id, user_id=current_user.user_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена",
        )
    return task


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую задачу",
    description="Создает задачу для текущего пользователя и возвращает созданный объект.",
    response_description="Созданная задача",
)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Создает новую задачу для текущего пользователя."""
    try:
        return await service.create(body, user_id=current_user.user_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка валидации данных: {err}",
        ) from err


@router.put(
    "/{task_id}",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Обновить задачу",
    description="Обновляет переданные поля задачи. Автоматически управляет статусом и датой закрытия.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Задача не найдена"}},
)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Обновляет задачу текущего пользователя по идентификатору."""
    task = await service.get_by_id(task_id, user_id=current_user.user_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена",
        )
    try:
        return await service.update(task, body)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка в формате переданных дат: {err}",
        ) from err


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу",
    description="Удаляет задачу текущего пользователя и все связанные с ней комментарии.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Задача не найдена"}},
)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> None:
    """Удаляет задачу текущего пользователя."""
    task = await service.get_by_id(task_id, user_id=current_user.user_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена",
        )
    await service.delete(task)
