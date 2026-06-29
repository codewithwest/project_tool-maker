"""
Database connection — delegates to the active backend (SQLite or PostgreSQL).
"""

import logging
from contextlib import contextmanager

from .backends import get_backend, close_backend

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    with get_backend().connection() as conn:
        yield conn


def close_pool():
    close_backend()


def init_schema():
    """Ensure migrations tracking table exists."""
    b = get_backend()
    with b.connection() as conn:
        cur = conn.cursor()
        try:
            cur.executescript(
                "CREATE TABLE IF NOT EXISTS _migrations ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL UNIQUE, "
                "applied_at TEXT DEFAULT (datetime('now'))"
                ")"
            )
        except AttributeError:
            b.init_migrations_table(cur)
        conn.commit()
