"""
Database layer — auto-selects SQLite (stdlib) or PostgreSQL backend based on DSN.
"""

from .backends import (
    Backend, SqliteBackend, PostgresBackend,
    get_backend, set_backend, close_backend,
)
from .config import DBConfig
from .connection import close_pool, get_connection, init_schema
from .migrator import migrate, rollback, status

__all__ = [
    "Backend",
    "SqliteBackend",
    "PostgresBackend",
    "DBConfig",
    "close_pool",
    "close_backend",
    "get_backend",
    "get_connection",
    "init_schema",
    "migrate",
    "rollback",
    "set_backend",
    "status",
]
