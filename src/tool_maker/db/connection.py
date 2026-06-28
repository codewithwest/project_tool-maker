"""
Database connection pool for PostgreSQL.
Auto-creates the database if it does not exist.
Auto-runs pending migrations on first connection.
"""

import logging
from contextlib import contextmanager
from typing import Optional
from urllib.parse import urlparse, urlunparse

import psycopg2
import psycopg2.pool
import psycopg2.extras

from .config import DBConfig

logger = logging.getLogger(__name__)

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_migrated: bool = False


def _parse_db_name(dsn: str) -> Optional[str]:
    """Extract the database name from a PostgreSQL DSN."""
    parsed = urlparse(dsn)
    # path is like "/dbname"
    if parsed.path and len(parsed.path) > 1:
        return parsed.path.lstrip("/")
    return None


def _dsn_with_db(dsn: str, dbname: str) -> str:
    """Replace the database name in a DSN."""
    parsed = urlparse(dsn)
    replaced = parsed._replace(path=f"/{dbname}")
    return urlunparse(replaced)


def _ensure_db_exists() -> None:
    """Create the target database if it does not exist.

    Connects to the maintenance database 'postgres' first, then
    issues CREATE DATABASE if the target is missing.
    """
    cfg = DBConfig.from_env()
    dsn = cfg.effective_dsn
    db_name = _parse_db_name(dsn)

    # No db name in DSN, or already targeting 'postgres' — nothing to do
    if not db_name or db_name in ("postgres", "template0", "template1"):
        return

    try:
        conn = psycopg2.connect(dsn)
        conn.close()
        return  # database exists
    except psycopg2.OperationalError as e:
        err_msg = str(e)
        if 'does not exist' not in err_msg and 'database' not in err_msg.lower():
            raise  # different error, propagate

    # Connect to the default 'postgres' database to create the target
    admin_dsn = _dsn_with_db(dsn, "postgres")
    logger.info("Creating database '%s' via %s", db_name, admin_dsn)
    try:
        conn = psycopg2.connect(admin_dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            # Quote the identifier to handle special chars
            safe_name = psycopg2.extensions.quote_ident(db_name, cur)
            cur.execute(f"CREATE DATABASE {safe_name}")
        conn.close()
        logger.info("Database '%s' created", db_name)
    except psycopg2.Error as e:
        if 'already exists' in str(e):
            logger.debug("Database '%s' already exists (race)", db_name)
        else:
            logger.warning("Could not create database '%s': %s", db_name, e)
            raise


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool, _migrated
    if _pool is None:
        cfg = DBConfig.from_env()
        _ensure_db_exists()
        logger.info("Creating connection pool to %s", cfg.effective_dsn)
        _pool = psycopg2.pool.ThreadedConnectionPool(
            cfg.min_conn,
            cfg.max_conn,
            cfg.effective_dsn,
        )
        if not _migrated:
            _auto_migrate()
            _migrated = True
    return _pool


def _auto_migrate() -> None:
    """Run pending migrations automatically on first connection."""
    logger.info("Running auto-migrations")
    conn = _pool.getconn()
    try:
        from .migrator import (
            SQL_INIT_MIGRATIONS,
            _applied_names,
            _mark_applied,
            _migration_files,
        )
        with conn.cursor() as cur:
            cur.execute(SQL_INIT_MIGRATIONS)
        conn.commit()
        applied = _applied_names()
        for f in _migration_files():
            if f.stem not in applied:
                sql = f.read_text()
                logger.info("Applying migration: %s", f.stem)
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                _mark_applied(f.stem)
                logger.info("Migration %s applied", f.stem)
        logger.info("Auto-migrations complete")
    except Exception as e:
        logger.error("Auto-migration failed: %s", e)
        raise  # so _migrated stays False
    finally:
        _pool.putconn(conn)


@contextmanager
def get_connection():
    """Get a connection from the pool (context manager)."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    """Close all connections in the pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def init_schema() -> None:
    """Ensure the migrations tracking table exists (explicit call)."""
    from .migrator import SQL_INIT_MIGRATIONS
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_INIT_MIGRATIONS)
        conn.commit()
