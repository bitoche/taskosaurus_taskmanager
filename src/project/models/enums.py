"""Перечисления (Enums) для моделей предметной области."""

from enum import IntEnum


class TaskStatusEnum(IntEnum):
    """Статусы жизненного цикла задачи.

    Атрибуты:
        ACTIVE (1): Задача активна / в работе.
        COMPLETED (2): Задача выполнена / закрыта.
    """

    ACTIVE = 1
    COMPLETED = 2
