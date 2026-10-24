"""Маршруты API для управления задачами."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from project.core.database import get_session
from project.models import Task
from project.schemas import TaskCreate, TaskRead, TaskUpdate
from project.services.task_service import TaskService

router = APIRouter()


def get_task_service(session: AsyncSession = Depends(get_session)) -> TaskService:
    """Внедрение зависимости сервиса задач.

    Args:
        session: Сессия SQLAlchemy из контекста запроса.

    Returns:
        Экземпляр TaskService.
    """
    return TaskService(session)


@router.get(
    "/",
    response_model=list[TaskRead],
    status_code=status.HTTP_200_OK,
    summary="Получить список задач",
    description="Возвращает список всех задач. Поддерживает фильтрацию по диапазону дат выполнения (due_date).",
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
    service: TaskService = Depends(get_task_service),
) -> Sequence[Task]:
    """Получает список задач с опциональной фильтрацией по диапазону дат."""
    try:
        return await service.list_tasks(date_from=date_from, date_to=date_to)
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
    service: TaskService = Depends(get_task_service),
) -> Sequence[Task]:
    """Возвращает задачи в диапазоне дат (алиас эндпоинта /between)."""
    return await list_tasks(date_from=date_from, date_to=date_to, service=service)


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Получить задачу по ID",
    description="Возвращает детальную информацию о конкретной задаче.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Задача не найдена"}},
)
async def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Ищет и возвращает задачу по её первичному ключу."""
    task = await service.get_by_id(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена",
        )
    return task


@router.post(
    "/",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую задачу",
    description="Создает задачу с переданными параметрами и возвращает созданный объект.",
    response_description="Созданная задача",
)
async def create_task(
    body: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Создает новую задачу."""
    try:
        return await service.create(body)
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
    service: TaskService = Depends(get_task_service),
) -> Task:
    """Обновляет задачу по идентификатору."""
    task = await service.get_by_id(task_id)
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
    description="Удаляет задачу и все связанные с ней комментарии.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Задача не найдена"}},
)
async def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> None:
    """Удаляет задачу по её идентификатору."""
    task = await service.get_by_id(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с ID {task_id} не найдена",
        )
    await service.delete(task)
