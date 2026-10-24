"""Модуль централизованной настройки логирования приложения.

Настраивает вывод логов:
1. В консоль (stdout/stderr) для стандартных потоков 12-factor.
2. В ротируемый файл (RotatingFileHandler) в настраиваемой директории.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from taskmanager.core.config import settings

# Стандартный формат сообщений логов
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Инициализирует и настраивает систему логирования приложения.

    Создает каталог логов, если он не существует, и подключает:
    - Консольный обработчик (StreamHandler);
    - Файловый обработчик с автоматической ротацией (RotatingFileHandler).
    """
    # Создаем директорию для логов при необходимости
    log_dir_path = Path(settings.log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    log_file_path = log_dir_path / settings.log_file_name

    # Получаем численный уровень логирования
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # 1. Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 2. Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очищаем старые обработчики, чтобы избежать дублирования записей
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Настраиваем вывод логгеров Uvicorn в наш файл
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.handlers.clear()
        u_logger.addHandler(console_handler)
        u_logger.addHandler(file_handler)
        u_logger.propagate = False

    logger = logging.getLogger("taskmanager")
    logger.info(
        "Логирование инициализировано. Запись ведется в файл: %s (уровень: %s)",
        log_file_path.resolve(),
        settings.log_level.upper(),
    )
