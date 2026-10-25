"""Сервис экспорта и импорта данных пользователя в структурированном JSON-формате."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from taskmanager.core.exceptions import EntityNotFoundError
from taskmanager.models import Task, TaskComment, TaskPriority, TaskTag, TaskTagXTask, User
from taskmanager.schemas import (
    ExportComment,
    ExportPriority,
    ExportTag,
    ExportTask,
    ImportSummary,
    UserDataExport,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DataTransferService:
    """Сервис для резервного копирования и восстановления данных пользователя."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def export_data(self, user_id: int) -> UserDataExport:
        """Экспортирует все задачи, комментарии, теги и приоритеты указанного пользователя."""
        user = await self.session.get(User, user_id)
        if not user:
            raise EntityNotFoundError("Пользователь", user_id)

        # 1. Приоритеты
        p_stmt = select(TaskPriority).where(TaskPriority.user_id == user_id)
        p_res = await self.session.execute(p_stmt)
        priorities = [
            ExportPriority(
                priority_name=p.priority_name,
                priority_color=p.priority_color,
                priority_sorting_weight=p.priority_sorting_weight,
            )
            for p in p_res.scalars().all()
        ]

        # 2. Теги
        t_stmt = select(TaskTag).where(TaskTag.user_id == user_id)
        t_res = await self.session.execute(t_stmt)
        tags = [
            ExportTag(
                tag_text=t.tag_text,
                tag_color=t.tag_color,
            )
            for t in t_res.scalars().all()
        ]

        # 3. Задачи со связями
        task_stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .options(
                selectinload(Task.priority),
                selectinload(Task.tags),
                selectinload(Task.comments),
            )
            .order_by(Task.task_id.asc())
        )
        task_res = await self.session.execute(task_stmt)
        tasks = []
        for task in task_res.scalars().all():
            exp_task = ExportTask(
                title=task.title,
                description=task.description,
                link_to_taskmanager=task.link_to_taskmanager,
                due_date=task.due_date,
                closed_dttm=task.closed_dttm,
                task_status=task.task_status,
                priority_name=task.priority.priority_name if task.priority else None,
                tags=[tag.tag_text for tag in task.tags],
                comments=[ExportComment(text=c.text, created_at=c.created_at) for c in task.comments],
            )
            tasks.append(exp_task)

        return UserDataExport(
            version="1.0",
            exported_at=_utc_now(),
            username=user.username,
            priorities=priorities,
            tags=tags,
            tasks=tasks,
        )

    async def import_data(self, user_id: int, data: UserDataExport) -> ImportSummary:
        """Импортирует данные в аккаунт указанного пользователя с сохранением связей."""
        user = await self.session.get(User, user_id)
        if not user:
            raise EntityNotFoundError("Пользователь", user_id)

        summary = ImportSummary()

        # 1. Приоритеты: маппинг существующих и создание недостающих
        existing_p_stmt = select(TaskPriority).where(TaskPriority.user_id == user_id)
        existing_p = {p.priority_name: p for p in (await self.session.execute(existing_p_stmt)).scalars().all()}
        priority_map: dict[str, int] = {name: p.priority_id for name, p in existing_p.items()}

        for p_dto in data.priorities:
            if p_dto.priority_name not in priority_map:
                new_p = TaskPriority(
                    user_id=user_id,
                    priority_name=p_dto.priority_name,
                    priority_color=p_dto.priority_color,
                    priority_sorting_weight=p_dto.priority_sorting_weight,
                )
                self.session.add(new_p)
                await self.session.flush()
                priority_map[p_dto.priority_name] = new_p.priority_id
                summary.priorities_imported += 1

        # 2. Теги: маппинг существующих и создание недостающих
        existing_t_stmt = select(TaskTag).where(TaskTag.user_id == user_id)
        existing_t = {t.tag_text: t for t in (await self.session.execute(existing_t_stmt)).scalars().all()}
        tag_map: dict[str, int] = {text: t.task_tag_id for text, t in existing_t.items()}

        for t_dto in data.tags:
            if t_dto.tag_text not in tag_map:
                new_t = TaskTag(
                    user_id=user_id,
                    tag_text=t_dto.tag_text,
                    tag_color=t_dto.tag_color,
                )
                self.session.add(new_t)
                await self.session.flush()
                tag_map[t_dto.tag_text] = new_t.task_tag_id
                summary.tags_imported += 1

        # 3. Задачи, комментарии и теги
        for task_dto in data.tasks:
            p_id = priority_map.get(task_dto.priority_name) if task_dto.priority_name else None
            new_task = Task(
                user_id=user_id,
                title=task_dto.title,
                description=task_dto.description,
                link_to_taskmanager=task_dto.link_to_taskmanager,
                due_date=task_dto.due_date,
                closed_dttm=task_dto.closed_dttm,
                task_status=task_dto.task_status or 1,
                task_priority_id=p_id,
            )
            self.session.add(new_task)
            await self.session.flush()
            summary.tasks_imported += 1

            # Привязка тегов
            for tag_name in task_dto.tags:
                tag_id = tag_map.get(tag_name)
                if tag_id:
                    self.session.add(TaskTagXTask(task_id=new_task.task_id, task_tag_id=tag_id))

            # Комментарии
            for c_dto in task_dto.comments:
                comment = TaskComment(
                    task_id=new_task.task_id,
                    text=c_dto.text,
                    created_at=c_dto.created_at or _utc_now(),
                )
                self.session.add(comment)
                summary.comments_imported += 1

        await self.session.flush()
        return summary
