"""Модуль криптографии, токенов и защиты от брутфорса.

Содержит:
- Хэширование и сверку паролей алгоритмом scrypt (RFC 7914 / NIST) с криптографической солью.
- Создание и верификацию JWT-токенов с настраиваемым сроком жизни.
- Механизм защиты от подбора паролей (Rate Limiter / Account Lockout) со скользящим окном.
"""

import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from taskmanager.core.config import settings


def hash_password(password: str) -> str:
    """Хэширует пароль с использованием алгоритма scrypt и случайной соли.

    Args:
        password: Исходный открытый пароль.

    Returns:
        Строка вида 'salt_hex:hash_hex'.
    """
    salt = secrets.token_bytes(16)
    # n=16384, r=8, p=1 - рекомендованные OWASP параметры памяти и CPU
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        maxmem=0,
        dklen=64,
    )
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие открытого пароля сохраненному хэшу за константное время.

    Args:
        plain_password: Введенный открытый пароль.
        hashed_password: Хэш из базы данных ('salt_hex:hash_hex').

    Returns:
        True, если пароль совпадает, иначе False.
    """
    try:
        salt_hex, hash_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        derived = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=0,
            dklen=64,
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Создает подписанный JWT-токен сессии.

    Args:
        data: Полезная нагрузка (claims), например {'sub': str(user_id)}.
        expires_delta: Индивидуальный срок жизни токена. Если не задан,
                       используется settings.access_token_expire_minutes.

    Returns:
        Подписанная JWT-строка.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Верифицирует и декодирует JWT-токен.

    Args:
        token: JWT-строка.

    Returns:
        Словарь claims при валидной подписи и непротухшем сроке, иначе None.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None


class BruteForceProtector:
    """Механизм защиты от подбора паролей со скользящим окном и временной блокировкой.

    Отслеживает количество неудачных попыток входа по ключу (IP или IP + логин).
    При превышении порога блокирует запросы на установленное время.
    """

    def __init__(self) -> None:
        # key -> list of failure timestamps
        self._failures: dict[str, list[float]] = {}
        # key -> timestamp until which the key is blocked
        self._lockouts: dict[str, float] = {}

    def is_blocked(self, key: str) -> tuple[bool, int]:
        """Проверяет, заблокирован ли ключ.

        Args:
            key: Идентификатор (например, IP адрес или IP:username).

        Returns:
            Кортеж (is_blocked: bool, remaining_seconds: int).
        """
        now = time.monotonic()
        locked_until = self._lockouts.get(key)
        if locked_until is not None:
            if now < locked_until:
                return True, int(locked_until - now)
            # Срок блокировки истек — очищаем
            del self._lockouts[key]
            self._failures.pop(key, None)
        return False, 0

    def register_failure(self, key: str) -> tuple[bool, int]:
        """Регистрирует неудачную попытку входа.

        Args:
            key: Идентификатор попытки.

        Returns:
            Кортеж (became_blocked: bool, remaining_seconds: int).
        """
        now = time.monotonic()
        # Очищаем устаревшие попытки вне скользящего окна
        window = settings.brute_force_window_seconds
        attempts = [t for t in self._failures.get(key, []) if now - t < window]
        attempts.append(now)
        self._failures[key] = attempts

        if len(attempts) >= settings.brute_force_max_attempts:
            lockout_time = settings.brute_force_lockout_seconds
            self._lockouts[key] = now + lockout_time
            self._failures.pop(key, None)
            return True, int(lockout_time)

        return False, 0

    def register_success(self, key: str) -> None:
        """Сбрасывает историю попыток при успешной аутентификации.

        Args:
            key: Идентификатор попытки.
        """
        self._failures.pop(key, None)
        self._lockouts.pop(key, None)

    def clear(self) -> None:
        """Сбрасывает все блокировки (используется для тестов)."""
        self._failures.clear()
        self._lockouts.clear()


# Глобальный синглтон защиты от подбора
login_protector = BruteForceProtector()
