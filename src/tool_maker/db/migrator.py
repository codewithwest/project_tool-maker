"""
Migration runner — applies SQL migration files in order and tracks state.
"""

import logging
from pathlib import Path
from typing import List

from .connection import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

SQL_INIT_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def _applied_names() -> List[str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM _migrations ORDER BY id")
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.warning("Could not read migrations table: %s", e)
        return []


def _mark_applied(name: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO _migrations (name) VALUES (%s) ON CONFLICT DO NOTHING",
                (name,),
            )
        conn.commit()


def _unmark_applied(name: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM _migrations WHERE name = %s", (name,))
        conn.commit()


def _migration_files() -> List[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.info("No migration files found in %s", MIGRATIONS_DIR)
    return files


def migrate(target: str = "head") -> List[str]:
    """Apply pending migrations up to *target* (name or 'head')."""
    applied = _applied_names()
    files = _migration_files()
    pending = [f for f in files if f.stem not in applied]

    if target != "head":
        pending = [f for f in pending if f.stem <= target]

    if not pending:
        logger.info("No pending migrations")
        return []

    applied_names = []
    with get_connection() as conn:
        for f in pending:
            sql = f.read_text()
            logger.info("Applying migration: %s", f.stem)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            _mark_applied(f.stem)
            applied_names.append(f.stem)

    return applied_names


def rollback(target: str) -> List[str]:
    """Rollback migrations down to *target*."""
    applied = _applied_names()
    files = _migration_files()
    to_rollback = [f for f in files if f.stem in applied and f.stem > target]

    if not to_rollback:
        logger.info("Nothing to rollback")
        return []

    rolled = []
    for f in reversed(to_rollback):
        sql = f.read_text()
        if "---- DOWN ----" in sql:
            _, down_part = sql.split("---- DOWN ----", 1)
            logger.info("Rolling back: %s", f.stem)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(down_part)
                conn.commit()
            _unmark_applied(f.stem)
            rolled.append(f.stem)
        else:
            logger.warning("No DOWN section in %s, skipping rollback", f.stem)

    return rolled


def status() -> List[dict]:
    """Show migration status."""
    applied = _applied_names()
    files = _migration_files()
    return [
        {"name": f.stem, "applied": f.stem in applied}
        for f in files
    ]
