"""
Database backends — SQLite (stdlib) and PostgreSQL (psycopg2).
Auto-selected by DSN scheme.
"""

import json
import logging
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Optional

from tool_maker.dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path.home() / ".config" / "tool-maker" / "data.db"


# ── helpers ──────────────────────────────────────────────────────────────────


def _serialize_param(p: Any) -> Any:
    if isinstance(p, (list, dict)):
        return json.dumps(p)
    return p


def _translate_sql(sql: str) -> str:
    sql = sql.replace("%s", "?")
    sql = sql.replace("NOW()", "datetime('now')")
    sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    sql = sql.replace("SERIAL", "INTEGER")
    sql = sql.replace("JSONB", "TEXT")
    sql = sql.replace("TIMESTAMPTZ", "TEXT")
    sql = sql.replace("INTEGER[]", "TEXT")
    return sql


# ── Connection proxies ───────────────────────────────────────────────────────


class _SqliteCursor:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = _translate_sql(sql)
        if params:
            params = tuple(_serialize_param(p) for p in params)
            return self._cur.execute(sql, params)
        return self._cur.execute(sql)

    def executescript(self, sql):
        sql = _translate_sql(sql)
        return self._cur.executescript(sql)

    def executemany(self, sql, seq):
        sql = _translate_sql(sql)
        seq = [tuple(_serialize_param(p) for p in row) for row in seq]
        return self._cur.executemany(sql, seq)

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _SqliteConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _SqliteCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ── Abstract backend ─────────────────────────────────────────────────────────


class Backend(ABC):
    @abstractmethod
    def connection(self):
        ...

    @abstractmethod
    def close(self):
        ...

    @abstractmethod
    def migrate(self):
        ...

    @abstractmethod
    def init_migrations_table(self, cur) -> None:
        ...

    @abstractmethod
    def mark_applied(self, name: str) -> None:
        ...

    @abstractmethod
    def unmark_applied(self, name: str) -> None:
        ...

    @abstractmethod
    def applied_names(self) -> List[str]:
        ...

    @abstractmethod
    def migration_dirs(self) -> List[Path]:
        ...


# ── SQLite backend ───────────────────────────────────────────────────────────


class SqliteBackend(Backend):
    def __init__(self, path: Optional[str] = None):
        path = path or os.environ.get("TOOLMAKER_DB_PATH") or str(DEFAULT_SQLITE_PATH)
        self._path = path
        self._local = threading.local()
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        logger.info("SQLite backend -> %s", path)

    def _get_raw(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def connection(self):
        conn = _SqliteConnection(self._get_raw())
        yield conn

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def migrate(self):
        applied = self.applied_names()
        for f in self.migration_dirs():
            if f.stem not in applied:
                sql = f.read_text()
                logger.info("Applying migration: %s", f.stem)
                with self.connection() as conn:
                    cur = conn.cursor()
                    cur.execute(sql)
                    conn.commit()
                self.mark_applied(f.stem)

    def init_migrations_table(self, cur) -> None:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL UNIQUE, "
            "applied_at TEXT DEFAULT (datetime('now'))"
            ")"
        )

    def mark_applied(self, name: str) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO _migrations (name) VALUES (?)", (name,)
            )

    def unmark_applied(self, name: str) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM _migrations WHERE name = ?", (name,))

    def applied_names(self) -> List[str]:
        try:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM _migrations ORDER BY id")
                return [row[0] for row in cur.fetchall()]
        except Exception:
            return []

    def migration_dirs(self) -> List[Path]:
        return sorted(
            (Path(__file__).parent / "migrations").glob("*.sqlite.sql")
        )


# ── PostgreSQL backend ────────────────────────────────────────────────────────


class PostgresBackend(Backend):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool = None
        self._lock = threading.Lock()
        logger.info("PostgreSQL backend -> %s", dsn)

    def _ensure_db_exists(self):
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(self._dsn)
        db_name = (
            parsed.path.lstrip("/")
            if parsed.path and len(parsed.path) > 1
            else None
        )
        if not db_name or db_name in ("postgres", "template0", "template1"):
            return
        import psycopg2

        try:
            conn = psycopg2.connect(self._dsn)
            conn.close()
            return
        except psycopg2.OperationalError as e:
            if "does not exist" not in str(e).lower():
                raise
        admin_dsn = parsed._replace(path="/postgres")
        admin_url = urlunparse(admin_dsn)
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(f'CREATE DATABASE "{db_name}"')
            cur.close()
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                raise
        finally:
            conn.close()

    def _ensure_pool(self):
        if self._pool is None:
            import psycopg2.pool

            with self._lock:
                if self._pool is None:
                    self._ensure_db_exists()
                    self._pool = psycopg2.pool.ThreadedConnectionPool(
                        1, 5, self._dsn
                    )
        return self._pool

    @contextmanager
    def connection(self):
        pool = self._ensure_pool()
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)

    def close(self):
        with self._lock:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None

    def migrate(self):
        applied = self.applied_names()
        for f in self.migration_dirs():
            if f.stem not in applied:
                sql = f.read_text()
                logger.info("Applying migration: %s", f.stem)
                with self.connection() as conn:
                    cur = conn.cursor()
                    cur.execute(sql)
                    conn.commit()
                self.mark_applied(f.stem)

    def init_migrations_table(self, cur) -> None:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "id SERIAL PRIMARY KEY, "
            "name TEXT NOT NULL UNIQUE, "
            "applied_at TIMESTAMPTZ DEFAULT NOW()"
            ")"
        )

    def mark_applied(self, name: str) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO _migrations (name) VALUES (%s) ON CONFLICT DO NOTHING",
                (name,),
            )
            conn.commit()

    def unmark_applied(self, name: str) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM _migrations WHERE name = %s", (name,))
            conn.commit()

    def applied_names(self) -> List[str]:
        try:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM _migrations ORDER BY id")
                return [row[0] for row in cur.fetchall()]
        except Exception:
            return []

    def migration_dirs(self) -> List[Path]:
        return sorted(
            (Path(__file__).parent / "migrations").glob("*.postgres.sql")
        )


# ── Factory ───────────────────────────────────────────────────────────────────


_backend: Optional[Backend] = None


def get_backend() -> Backend:
    global _backend
    if _backend is not None:
        return _backend
    dsn = os.environ.get("TOOLMAKER_DB_DSN", "").strip()
    if dsn and dsn.startswith("postgresql://"):
        _backend = PostgresBackend(dsn)
    else:
        _backend = SqliteBackend()
    return _backend


def set_backend(b: Backend) -> None:
    global _backend
    _backend = b


def close_backend() -> None:
    global _backend
    if _backend is not None:
        _backend.close()
        _backend = None
