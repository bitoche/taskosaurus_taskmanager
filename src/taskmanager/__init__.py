"""Пакет микросервиса taskmanager.

Версия считывается динамически из метаданных пакета (pyproject.toml)
через standard library importlib.metadata — единый источник правды.
"""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("taskmanager")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
