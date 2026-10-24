"""Модуль валидации и защиты пользовательских SQL-запросов.

Обеспечивает многоуровневую защиту от SQL-инъекций и деструктивных операций:
- Разрешены исключительно запросы на чтение данных (SELECT или WITH ... SELECT).
- Запрещены множественные выражения (разделители ';').
- Запрещены любые модифицирующие (DML), структурные (DDL) и административные операции.
- Запрещены любые SQL-комментарии (-- и /* */), способные маскировать внедрение кода.
"""

import re

from taskmanager.core.exceptions import SqlSecurityError

# Список запрещенных ключевых слов и опасных операций
FORBIDDEN_KEYWORDS: frozenset[str] = frozenset(
    {
        # Модификация структуры данных (DDL)
        "CREATE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "RENAME",
        # Модификация данных (DML)
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "UPSERT",
        "REPLACE",
        # Команды создания таблиц через SELECT INTO
        "INTO",
        # Административные операции и управление БД
        "ATTACH",
        "DETACH",
        "PRAGMA",
        "VACUUM",
        "ANALYZE",
        "REINDEX",
        "CLUSTER",
        "REFRESH",
        "DISCARD",
        "RESET",
        "SET",
        "SHOW",
        "LOCK",
        "EXPLAIN",
        "GRANT",
        "REVOKE",
        "COPY",
        "EXEC",
        "EXECUTE",
        "CALL",
        "DO",
        "PREPARE",
        "DEALLOCATE",
        # Управление транзакциями вручную
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE",
        "TRANSACTION",
        "BEGIN",
        "START",
        "LISTEN",
        "NOTIFY",
        "LOAD",
        "CHECKPOINT",
        # Системные и потенциально опасные функции PostgreSQL / SQLite
        "PG_SLEEP",
        "PG_TERMINATE_BACKEND",
        "PG_CANCEL_BACKEND",
        "PG_READ_FILE",
        "PG_WRITE_FILE",
        "PG_READ_BINARY_FILE",
        "DBLINK",
        "LOAD_EXTENSION",
    }
)


def validate_and_clean_sql(query: str) -> str:
    """Выполняет лексическую проверку SQL-запроса на безопасность.

    Args:
        query: Исходная строка SQL-запроса от клиента.

    Returns:
        Очищенная и проверенная строка SQL-запроса (без завершающей точки с запятой).

    Raises:
        SqlSecurityError: Если запрос пуст, содержит запрещенные конструкции,
            комментарии, множественные инструкции или ключевые слова.
    """
    if not query or not query.strip():
        raise SqlSecurityError("SQL-запрос не может быть пустым.")

    i = 0
    n = len(query)
    in_single_quote = False
    in_double_quote = False
    code_parts: list[str] = []
    current_code: list[str] = []
    semicolon_found = False

    while i < n:
        ch = query[i]
        nxt = query[i + 1] if i + 1 < n else ""

        # Внутри строкового литерала ('...')
        if in_single_quote:
            if ch == "'":
                if nxt == "'":
                    i += 2
                    continue
                in_single_quote = False
            elif ch == "\\":
                i += 2
                continue
            i += 1
            continue

        # Внутри двойных кавычек ("...")
        if in_double_quote:
            if ch == '"':
                if nxt == '"':
                    i += 2
                    continue
                in_double_quote = False
            elif ch == "\\":
                i += 2
                continue
            current_code.append(ch)
            i += 1
            continue

        # Вне строк и идентификаторов
        if ch == "'":
            in_single_quote = True
            if current_code:
                code_parts.append("".join(current_code))
                current_code = []
            i += 1
            continue

        if ch == '"':
            in_double_quote = True
            current_code.append(ch)
            i += 1
            continue

        # Блокировка SQL-комментариев для исключения скрытия инъекций
        if ch == "-" and nxt == "-":
            raise SqlSecurityError("Использование однострочных комментариев (--) запрещено в целях безопасности.")
        if ch == "/" and nxt == "*":
            raise SqlSecurityError("Использование многострочных комментариев (/* */) запрещено в целях безопасности.")
        if ch == "*" and nxt == "/":
            raise SqlSecurityError("Некорректный синтаксис: обнаружено закрытие комментария (*/).")

        # Блокировка множественных выражений
        if ch == ";":
            rest = query[i + 1 :]
            if rest.strip():
                raise SqlSecurityError("Множественные SQL-запросы через точку с запятой запрещены.")
            semicolon_found = True
            break

        current_code.append(ch)
        i += 1

    if in_single_quote:
        raise SqlSecurityError("Некорректный синтаксис: незакрытая строковая кавычка.")
    if in_double_quote:
        raise SqlSecurityError("Некорректный синтаксис: незакрытая двойная кавычка.")

    if current_code:
        code_parts.append("".join(current_code))

    cleaned_code = " ".join(code_parts)
    words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cleaned_code)
    if not words:
        raise SqlSecurityError("Запрос не содержит допустимых SQL-инструкций.")

    # Проверка первого оператора
    first_word = words[0].upper()
    if first_word not in ("SELECT", "WITH"):
        raise SqlSecurityError("Разрешены только запросы на чтение данных (SELECT или WITH ... SELECT).")

    # Для CTE-запросов обязательно наличие основного SELECT
    if first_word == "WITH":
        upper_words = [w.upper() for w in words]
        if "SELECT" not in upper_words:
            raise SqlSecurityError("CTE-запрос (WITH) должен содержать предложение SELECT.")

    # Проверка на наличие запрещенных ключевых слов
    for w in words:
        w_up = w.upper()
        if w_up in FORBIDDEN_KEYWORDS:
            raise SqlSecurityError(f"Операция или ключевое слово '{w_up}' запрещено в целях безопасности.")

    clean_sql = query[:i] if semicolon_found else query
    return clean_sql.strip()
