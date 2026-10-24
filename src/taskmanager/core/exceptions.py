"""Кастомные доменные исключения приложения.

Позволяют изолировать слой бизнес-логики от HTTP-кодов ответа.
"""


class DomainError(Exception):
    """Базовое исключение предметной области."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    """Исключение, выбрасываемое когда сущность не найдена в базе данных."""

    def __init__(self, entity_name: str, entity_id: int | str) -> None:
        message = f"{entity_name} с идентификатором {entity_id} не найден(а)"
        super().__init__(message)
        self.entity_name = entity_name
        self.entity_id = entity_id


class TaskNotFoundError(EntityNotFoundError):
    """Задача не найдена."""

    def __init__(self, task_id: int) -> None:
        super().__init__("Задача", task_id)


class CommentNotFoundError(EntityNotFoundError):
    """Комментарий не найден."""

    def __init__(self, comment_id: int) -> None:
        super().__init__("Комментарий", comment_id)


class TagNotFoundError(EntityNotFoundError):
    """Тег не найден."""

    def __init__(self, tag_id: int) -> None:
        super().__init__("Тег", tag_id)


class PriorityNotFoundError(EntityNotFoundError):
    """Приоритет не найден."""

    def __init__(self, priority_id: int) -> None:
        super().__init__("Приоритет", priority_id)
