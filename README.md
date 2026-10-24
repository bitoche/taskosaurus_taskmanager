# Taskmanager API Service (Polyrepo Microservice)

Современный асинхронный REST API микросервис для ведения задач и календаря.
Перенесён с Flask + DuckDB на **FastAPI + SQLAlchemy 2.0 (Async) + PostgreSQL** с управлением зависимостями через **`uv`**.

---

## 🚀 Стек технологий

* **Версия сервиса**: `2.0.0` (Semantic Versioning)
* **Язык**: Python 3.13+
* **Пакетный менеджер**: [uv](https://docs.astral.sh/uv/) (быстрее Poetry в 10–100 раз)
* **Web-фреймворк**: FastAPI + Uvicorn
* **ORM & БД**: SQLAlchemy 2.0 (asyncio) + `asyncpg` + PostgreSQL 17
* **Миграции**: Alembic
* **Линтер и форматтер**: Ruff
* **Тестирование**: Pytest + AnyIO + aiosqlite (32 теста, in-memory SQLite)
* **Контейнеризация**: Docker & Docker Compose (с непривилегированным пользователем `appuser`)

---

## 📌 Версионирование (Единственный источник правды)

Подробный архитектурный регламент и правила ведения проекта описаны в [ARCHITECTURE.md](./ARCHITECTURE.md) и [AGENTS.md](./AGENTS.md).

Версия проекта задается **строго в одном месте**:
- [pyproject.toml](file:///c:/Users/bitoche/Desktop/project/pyproject.toml) (`version = "2.0.0"`).

Во всех остальных местах (в коде FastAPI, Swagger-документации, `taskmanager.__version__`) версия подтягивается автоматически через стандартную библиотеку `importlib.metadata`. В `.env` или коде вручную менять ничего не нужно.

Чтобы поднять версию:
1. Меняем `version = "X.Y.Z"` в `pyproject.toml`.
2. Выполняем `uv sync`.
3. Всё приложение уже работает на новой версии!

---

## 📁 Структура проекта

```
project/
├── alembic/                      # Миграции базы данных
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   └── env.py
├── src/taskmanager/
│   ├── __init__.py               # __version__ = "2.0.0"
│   ├── main.py                   # Точка входа, lifespan, CORS, автосоздание таблиц
│   ├── core/
│   │   ├── config.py             # Настройки из env (Pydantic Settings)
│   │   ├── database.py           # Async engine и фабрика сессий get_session
│   │   └── exceptions.py         # Кастомные доменные исключения (DomainError)
│   ├── models/                   # Модели SQLAlchemy
│   │   ├── base.py               # Naming conventions
│   │   ├── enums.py              # TaskStatusEnum
│   │   └── __init__.py           # Task, TaskComment, TaskTag, TaskPriority, TaskStatus
│   ├── schemas/                  # Pydantic DTO с валидацией
│   │   └── __init__.py
│   ├── services/                 # Сервисный слой (бизнес-логика)
│   │   ├── task_service.py
│   │   ├── comment_service.py
│   │   ├── tag_service.py
│   │   ├── priority_service.py
│   │   └── sql_guard.py          # Валидация безопасности пользовательских SQL-запросов
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
│   ├── test_api.py               # E2E тесты эндпоинтов
│   └── test_services.py          # Юнит-тесты сервисного слоя
├── docker-compose.yml            # Сервис + PostgreSQL 17
├── Dockerfile                    # Multi-stage сборка на базе uv (от пользователя appuser)
├── pyproject.toml                # Зависимости и конфигурация инструментов
└── uv.lock                       # Детерминированный lock-файл
```

---

## 🛠️ Быстрый старт

### Вариант 1: Запуск всего через Docker Compose

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
   uv run uvicorn taskmanager.main:app --reload --port 8000
   ```

---

## 🧪 Запуск тестов

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
| `POST` | `/api/tasks/query` | Выполнить безопасный SQL-запрос только для чтения (алиас `/api/tasks/query/`) |
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

## 🔒 Безопасный SQL-интерфейс (`POST /api/tasks/query`)

Микросервис предоставляет защищенный эндпоинт для выполнения произвольных аналитических SQL-запросов к базе данных задач (например, для построения динамических отчетов, графиков и фильтрации):
* **Маршруты**: `POST /api/tasks/query` и алиас `POST /api/tasks/query/`.
* **Входные данные (`SqlQueryRequest`)**:
  ```json
  {
    "query": "SELECT task_id, title, due_date FROM task WHERE task_status = 1"
  }
  ```
* **Выходные данные (`SqlQueryResponse`)**:
  ```json
  {
    "columns": ["task_id", "title", "due_date"],
    "rows": [
      {"task_id": 1, "title": "Подготовить релиз", "due_date": "2026-10-31"}
    ],
    "count": 1
  }
  ```

### Многоуровневая система защиты:
1. **Только чтение (SELECT / WITH ... SELECT)**: разрешены исключительно запросы выборки данных. CTE-выражения (`WITH`) обязаны оканчиваться оператором `SELECT`.
2. **Блокировка опасных ключевых слов и операций**: запрещены любые модифицирующие (DML: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `UPSERT`, `REPLACE`), структурные (DDL: `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `RENAME`), административные (`PRAGMA`, `ATTACH`, `DETACH`, `VACUUM`, `EXEC`, `GRANT`, `COPY` и др.), а также создание таблиц через `SELECT ... INTO`.
3. **Защита от множественных инструкций**: запрещено выполнение составных запросов через точку с запятой `;` (разрешена только одна завершающая точка с запятой).
4. **Запрет SQL-комментариев**: однострочные (`--`) и многострочные (`/* */`) комментарии полностью блокируются для предотвращения маскирования инъекций.
5. **READ ONLY на уровне транзакции СУБД**: перед выполнением запроса сессия переводится в режим только для чтения (`SET TRANSACTION READ ONLY` в PostgreSQL, `PRAGMA query_only = ON` в SQLite), что делает модификацию физически невозможной на уровне движка БД.
6. **Информативные ошибки**: при нарушениях безопасности или синтаксических ошибках возвращается `HTTP 400 Bad Request` с подробным описанием причины.

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
