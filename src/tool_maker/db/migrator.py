"""
Migration runner — applies SQL migration files via the active backend.
"""

import logging
from pathlib import Path
from typing import List

from .backends import get_backend

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migrate(target: str = "head") -> List[str]:
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
    applied = b.applied_names()
    files = b.migration_dirs()
    pending = [f for f in files if f.stem not in applied]
    if target != "head":
        pending = [f for f in pending if f.stem <= target]
    if not pending:
        logger.info("No pending migrations")
        return []
    applied_names = []
    for f in pending:
        sql = f.read_text()
        logger.info("Applying migration: %s", f.stem)
        with b.connection() as conn:
            cur = conn.cursor()
            try:
                cur.executescript(sql)
            except AttributeError:
                cur.execute(sql)
            conn.commit()
        b.mark_applied(f.stem)
        applied_names.append(f.stem)
    return applied_names


def rollback(target: str) -> List[str]:
    b = get_backend()
    applied = b.applied_names()
    files = b.migration_dirs()
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
            with b.connection() as conn:
                cur = conn.cursor()
                try:
                    cur.executescript(down_part)
                except AttributeError:
                    cur.execute(down_part)
                conn.commit()
            b.unmark_applied(f.stem)
            rolled.append(f.stem)
        else:
            logger.warning("No DOWN section in %s, skipping rollback", f.stem)
    return rolled


def status() -> List[dict]:
    b = get_backend()
    applied = b.applied_names()
    files = b.migration_dirs()
    return [
        {"name": f.stem, "applied": f.stem in applied}
        for f in files
    ]
