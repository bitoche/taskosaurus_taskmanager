# Taskmanager API Service (Polyrepo Microservice)

Современный асинхронный REST API микросервис для ведения задач и календаря.
Перенесён с Flask + DuckDB на **FastAPI + SQLAlchemy 2.0 (Async) + PostgreSQL** с управлением зависимостями через **`uv`**.

---

## 🚀 Стек технологий

* **Язык**: Python 3.13+
* **Пакетный менеджер**: [uv](https://docs.astral.sh/uv/) (быстрее Poetry в 10–100 раз)
* **Web-фреймворк**: FastAPI + Uvicorn
* **ORM & БД**: SQLAlchemy 2.0 (asyncio) + `asyncpg` + PostgreSQL 17
* **Миграции**: Alembic
* **Линтер и форматтер**: Ruff
* **Тестирование**: Pytest + AnyIO + aiosqlite (мгновенные in-memory тесты)
* **Контейнеризация**: Docker & Docker Compose

---

## 📁 Структура проекта

```
project/
├── alembic/                      # Миграции базы данных
│   ├── versions/
│   └── env.py
├── src/project/
│   ├── main.py                   # Точка входа, lifespan, CORS, автосоздание таблиц
│   ├── core/
│   │   ├── config.py             # Настройки из env (Pydantic Settings)
│   │   └── database.py           # Async engine и фабрика сессий get_session
│   ├── models/                   # Модели SQLAlchemy
│   │   ├── base.py
│   │   └── __init__.py           # Task, TaskComment, TaskTag, TaskPriority, TaskStatus
│   ├── schemas/                  # Pydantic-схемы запросов и ответов
│   │   └── __init__.py
│   └── api/
│       ├── router.py             # Корневой роутер
│       └── routes/
│           ├── health.py         # GET /api/health
│           ├── tasks.py          # /api/tasks (CRUD, фильтрация по датам, статусы)
│           ├── comments.py       # /api/tasks/{task_id}/comments, /api/tasks/comment
│           ├── tags.py           # /api/task_tags (CRUD, assign, unassign)
│           ├── priorities.py     # /api/priority (CRUD, cascade nullify)
│           └── remote_db.py      # Заглушки синхронизации для совместимости с webui
├── tests/
│   ├── conftest.py               # Async фикстуры с in-memory SQLite
│   └── test_api.py               # E2E тесты всех эндпоинтов
├── docker-compose.yml            # Сервис + PostgreSQL 17
├── Dockerfile                    # Multi-stage сборка на базе uv
├── pyproject.toml                # Зависимости и конфигурация инструментов
└── uv.lock                       # Детерминированный lock-файл
```

---

## 🛠️ Быстрый старт

### Вариант 1: Запуск всего через Docker Compose

Поднимает PostgreSQL 17 и API-сервис:

```bash
docker compose up --build
```

API будет доступен по адресу: `http://localhost:8000`  
Интерактивная документация Swagger: `http://localhost:8000/docs`

---

### Вариант 2: Локальная разработка с `uv`

1. **Установите зависимости**:
   ```bash
   uv sync
   ```

2. **Запустите PostgreSQL** (например, только базу из docker-compose):
   ```bash
   docker compose up -d db
   ```

3. **Запустите сервер в режиме разработки**:
   ```bash
   uv run uvicorn project.main:app --reload --port 8000
   ```

---

## 🧪 Запуск тестов

Тесты используют `aiosqlite` в памяти и не требуют запущенного PostgreSQL:

```bash
uv run pytest -v
```

Проверка кода линтером:

```bash
uv run ruff check .
```

---

## 🔌 API Контракт (100% совместим с webui)

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/health` | Проверка жизнеспособности |
| `GET` | `/api/tasks?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` | Список задач (с фильтрацией по дате) |
| `GET` | `/api/tasks/between?date_from=...&date_to=...` | Алиас для обратной совместимости |
| `GET` | `/api/tasks/{task_id}` | Получить задачу по ID |
| `POST` | `/api/tasks` | Создать задачу |
| `PUT` | `/api/tasks/{task_id}` | Обновить задачу (автоматика закрытия/открытия) |
| `DELETE` | `/api/tasks/{task_id}` | Удалить задачу |
| `GET` | `/api/tasks/{task_id}/comments` | Список комментариев задачи |
| `POST` | `/api/tasks/comment` | Добавить комментарий к задаче |
| `PUT` | `/api/tasks/comment/{comment_id}` | Изменить комментарий |
| `DELETE` | `/api/tasks/comment/delete/{comment_id}` | Удалить комментарий |
| `GET` | `/api/task_tags` | Все теги |
| `POST` | `/api/task_tags` | Создать тег |
| `GET` | `/api/task_tags/tasks` | Связи тегов и задач |
| `POST` | `/api/task_tags/assign` | Привязать тег к задаче |
| `DELETE` | `/api/task_tags/unassign/{tag_id}/task/{task_id}` | Отвязать тег от задачи |
| `DELETE` | `/api/task_tags/{tag_id}` | Удалить тег глобально |
| `GET` | `/api/priority` | Список приоритетов |
| `POST` | `/api/priority` | Создать приоритет |
| `PUT` | `/api/priority/{priority_id}` | Обновить приоритет |
| `DELETE` | `/api/priority/{priority_id}` | Удалить приоритет |
| `GET` | `/api/remote_db/check_updates` | Заглушка проверки синхронизации |

---

## ⚙️ Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_DB_HOST` | `localhost` | Хост PostgreSQL |
| `APP_DB_PORT` | `5432` | Порт PostgreSQL |
| `APP_DB_USER` | `taskmanager` | Пользователь БД |
| `APP_DB_PASSWORD` | `taskmanager` | Пароль БД |
| `APP_DB_NAME` | `taskmanager` | Имя базы данных |
| `APP_DEBUG` | `false` | Режим отладки (SQL echo) |
| `APP_PORT` | `8000` | Порт HTTP-сервера |
