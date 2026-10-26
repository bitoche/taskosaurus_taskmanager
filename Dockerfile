# syntax=docker/dockerfile:1
# ── Этап сборки зависимостей (Builder) ─────────────────────────────────────────
FROM python:3.13-slim AS builder

# Копируем официальный бинарник uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Настройка переменных окружения для сборщика
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала копируем только файлы зависимостей для эффективного кэширования слоев Docker
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Копируем исходный код и устанавливаем проект в виртуальное окружение
COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

# ── Финальный легковесный этап выполнения (Runtime) ───────────────────────────
FROM python:3.13-slim AS runtime

# Настройка окружения
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Создание непривилегированного пользователя для безопасности (Best Practice)
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Создаем директорию для логов с правами appuser
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app

# Копируем готовое виртуальное окружение и исходный код из этапа сборки
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

# Копируем файлы конфигурации Alembic и метаданные проекта для запуска миграций и CLI
COPY --chown=appuser:appgroup alembic.ini ./
COPY --chown=appuser:appgroup alembic ./alembic
COPY --chown=appuser:appgroup pyproject.toml ./
COPY --chown=appuser:appgroup README.md ./

# Переключаемся на непривилегированного пользователя
USER appuser

# Открываем порт сервиса
EXPOSE 8000

# Проверка работоспособности сервиса (Liveness/Readiness probe)
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

# Запуск Uvicorn через встроенный в .venv python
CMD ["python", "-m", "uvicorn", "taskmanager.main:app", "--host", "0.0.0.0", "--port", "8000"]
