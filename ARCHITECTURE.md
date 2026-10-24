# Архитектура, стандарты разработки и руководство по ведению проекта `taskmanager`

Этот документ служит **основным регламентом и контекстом** при доработке, рефакторинге и расширении микросервиса. Агенты и разработчики обязаны сверяться с ним перед внесением изменений.

---

## 1. 📌 Управление версиями (Single Source of Truth)

* **Единственный источник правды**: файл [`pyproject.toml`](./pyproject.toml) (секция `[project]`, поле `version`).
* **Категорически запрещено**:
  * Хардкодить версию строкой в коде (`__version__ = "X.Y.Z"`).
  * Дублировать версию в `.env`, `.env.example` или `docker-compose.yml`.
* **Как считывается версия**:
  * В [`src/taskmanager/__init__.py`](./src/taskmanager/__init__.py) через стандартную библиотеку:
    ```python
    import importlib.metadata
    __version__ = importlib.metadata.version("taskmanager")
    ```
  * В [`src/taskmanager/core/config.py`](./src/taskmanager/core/config.py) поле `app_version` автоматически берется из `__version__`.
* **Алгоритм релиза новой версии**:
  1. Изменить строку `version = "X.Y.Z"` в `pyproject.toml` по SemVer:
     * `PATCH` (2.0.1) — багфиксы;
     * `MINOR` (2.1.0) — новая функциональность без ломающих изменений;
     * `MAJOR` (3.0.0) — обратно несовместимые изменения API или БД.
  2. Запустить `uv sync` для обновления lock-файла `uv.lock`.
  3. Поставить git-тег: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`.

---

## 2. 🏛️ Архитектурные слои и ответственность

Микросервис построен по принципам **Clean Architecture** с разделением ответственности:

```
src/taskmanager/
├── api/          # Слой HTTP-интерфейса (Маршрутизаторы / Контроллеры)
├── services/     # Слой бизнес-логики (Сервисы)
├── models/       # Слой данных (ORM-модели SQLAlchemy)
├── schemas/      # Слой контрактов (Pydantic DTO)
└── core/         # Конфигурация, сессии БД, доменные исключения
```

### 2.1. Маршрутизаторы (`src/taskmanager/api/routes/`)
* **Ответственность**: приём HTTP-запросов, проверка прав, валидация DTO, вызов соответствующего сервиса, возврат HTTP-статуса и сериализация ответа.
* **Правила**:
  * **Тонкие контроллеры**: в маршрутизаторах **запрещено** писать сырые SQL-запросы или сложную логику обработки данных.
  * Все эндпоинты должны использовать константы `fastapi.status` (например, `status.HTTP_201_CREATED`, а не `201`).
  * Обязательно указывать `response_model`, `status_code`, `summary`, `description` и русскоязычные OpenAPI-теги.
  * Сервисы внедряются через `Depends(...)`.

### 2.2. Сервисный слой (`src/taskmanager/services/`)
* **Ответственность**: чистая бизнес-логика, транзакции, вычисления, правила перехода статусов и запросы к базе данных.
* **Правила**:
  * Сервисы принимают `AsyncSession` в конструкторе (`__init__`).
  * Для изменения сущностей используются методы `session.flush()` и `session.refresh()`.
  * При отсутствии сущности выбрасываются кастомные доменные исключения из `taskmanager.core.exceptions` (например, `TaskNotFoundError`), а не `HTTPException`.

### 2.3. Слой моделей данных (`src/taskmanager/models/`)
* **Ответственность**: декларативное описание структуры таблиц в PostgreSQL через SQLAlchemy 2.0 (`Mapped`, `mapped_column`).
* **Правила**:
  * Все модели наследуются от `Base` из [`src/taskmanager/models/base.py`](./src/taskmanager/models/base.py) с настроенным `POSTGRES_NAMING_CONVENTION` (`ix_`, `fk_`, `uq_`, `pk_`).
  * Все внешние ключи (`ForeignKey`) и колонки, участвующие в частых выборках/сортировках (`due_date`, `task_status`), **обязаны иметь индекс (`index=True`)**.
  * Статусы и категории определяются через перечисления в [`src/taskmanager/models/enums.py`](./src/taskmanager/models/enums.py). Запрещено использовать магические числа в коде.

### 2.4. Схемы валидации (`src/taskmanager/schemas/`)
* **Ответственность**: строгая типизация входных (`Create`, `Update`, `Assign`) и выходных (`Read`) данных через Pydantic v2.
* **Правила**:
  * Выходные схемы `Read` содержат `model_config = ConfigDict(from_attributes=True)`.
  * Поля снабжаются описаниями `Field(description=..., examples=...)`.

### 2.5. Ядро системы (`src/taskmanager/core/`)
* [`config.py`](./src/taskmanager/core/config.py): Pydantic Settings с префиксом `APP_`.
* [`database.py`](./src/taskmanager/core/database.py): `AsyncEngine`, пул соединений (`pool_pre_ping=True`) и генератор сессий `get_session` с автоматическим `commit`/`rollback`.
* [`exceptions.py`](./src/taskmanager/core/exceptions.py): иерархия доменных исключений (`DomainError` -> `EntityNotFoundError`). В [`main.py`](./src/taskmanager/main.py) зарегистрирован глобальный обработчик, транслирующий их в 404.

---

## 3. 💾 База данных и миграции (Alembic)

* **СУБД**: PostgreSQL 17 (драйвер `asyncpg`).
* **Управление схемой**:
  * Автосоздание таблиц при старте (`Base.metadata.create_all`) используется **только в dev/тестовом окружении**.
  * Для продакшена и CI/CD изменения схемы фиксируются миграциями Alembic в папке [`alembic/versions/`](./alembic/versions).
* **Создание новой миграции**:
  ```bash
  uv run alembic revision --autogenerate -m "краткое_описание_миграции"
  ```
* **Применение миграций**:
  ```bash
  uv run alembic upgrade head
  ```

---

## 4. 🧪 Стандарты тестирования

* **Инструменты**: `pytest`, `anyio`, `httpx`, `aiosqlite`.
* **Изоляция**: тесты используют in-memory SQLite и не зависят от запущенного PostgreSQL контейнера.
* **Структура тестов**:
  * [`tests/test_api.py`](./tests/test_api.py): E2E тесты HTTP-эндпоинтов через `AsyncClient`.
  * [`tests/test_services.py`](./tests/test_services.py): модульные тесты сервисов с прямой передачей сессии базы данных.
* **Требование**: при добавлении новой логики обязательно добавлять тесты как на уровне сервиса, так и на уровне API.
* **Запуск тестов**:
  ```bash
  uv run pytest -v
  ```

---

## 5. 🎨 Стиль кода, линтинг и документация

* **Линтер и форматтер**: `ruff`.
  ```bash
  uv run ruff check . --fix
  uv run ruff format .
  ```
* **Язык**:
  * **Все комментарии в коде, докстринги (Google-style docstrings) и документация ведутся строго на русском языке**.
  * Имена переменных, классов, методов и полей БД — на английском языке (snake_case для функций/полей, PascalCase для классов).

---

## 6. 📜 Логирование (Logging)

* **Модуль**: [`src/taskmanager/core/logging.py`](./src/taskmanager/core/logging.py).
* **Потоки вывода**:
  1. `StreamHandler` (консоль `stdout`/`stderr`).
  2. `RotatingFileHandler` (ротируемый файл на диске).
* **Параметры конфигурации (в `Settings` и `.env`)**:
  * `APP_LOG_DIR` — путь к каталогу логов (по умолчанию `logs/` в корне проекта).
  * `APP_LOG_FILE_NAME` — имя файла (по умолчанию `taskmanager.log`).
  * `APP_LOG_LEVEL` — уровень логирования (`INFO`, `DEBUG`, `WARNING`, `ERROR`).
  * `APP_LOG_MAX_BYTES` — лимит размера файла перед ротацией (по умолчанию `10 MB`).
  * `APP_LOG_BACKUP_COUNT` — количество сохраняемых ротированных архивов (по умолчанию `5`).
* **Правило git**:
  * Папка `logs/` сохраняется в репозитории через `.gitkeep`, но все файлы внутри (`logs/*`) добавлены в `.gitignore` и не коммитятся.
