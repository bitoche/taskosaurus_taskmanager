"""Базовый декларативный класс для всех ORM-моделей SQLAlchemy.

Настраивает явные соглашения об именовании ограничений базы данных (naming conventions),
что обеспечивает предсказуемые и воспроизводимые миграции в Alembic и PostgreSQL.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Стандартное соглашение об именовании ограничений в PostgreSQL
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Абстрактный базовый класс для всех моделей приложения.

    Содержит стандартизированные соглашения об именовании индексов,
    уникальных ограничений, проверок, внешних и первичных ключей.
    """

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
