"""
Flask application factory for the Tool Maker UI.
Auto-runs DB migrations on startup when postgres deps are installed.
"""

import logging

from flask import Flask

from tool_maker.dotenv import load_dotenv

from .log_handler import get_log_handler
from .routes import register_routes

logger = logging.getLogger(__name__)

load_dotenv()


def _auto_migrate() -> None:
    try:
        from tool_maker.db.connection import init_schema
        from tool_maker.db.migrator import migrate, status
        init_schema()
        applied = migrate()
        if applied:
            logger.info("DB migrations applied on startup: %s", ", ".join(applied))
        else:
            pending = [s for s in status() if not s["applied"]]
            if pending:
                logger.info("%d migration(s) pending on startup", len(pending))
            else:
                logger.debug("DB migrations up to date")
    except ImportError:
        logger.debug("Postgres deps not installed, skipping auto-migration")
    except Exception as e:
        logger.warning("Auto-migration on startup failed: %s", e)


def create_ui_app(tool_maker_instance=None) -> Flask:
    """Create and configure the Tool Maker UI Flask application.

    Auto-runs pending DB migrations on startup (silently skipped
    if psycopg2 is not installed).

    Args:
        tool_maker_instance: An optional pre-configured ToolMaker instance.
                             If not provided, one is created from env vars.

    Returns:
        A configured Flask application.
    """
    app = Flask(__name__)
    app.secret_key = "tool-maker-ui-dev"  # only used for session flashes

    _auto_migrate()

    get_log_handler()

    register_routes(app, tool_maker_instance)

    return app
