"""
Database configuration for PostgreSQL connection.
Reads from .env files and environment variables.
"""

import os
from dataclasses import dataclass

from tool_maker.dotenv import load_dotenv

DEFAULT_DSN = "postgresql://localhost:5432/toolmaker"

# Load .env once at import time
load_dotenv()


@dataclass
class DBConfig:
    dsn: str = ""
    min_conn: int = 1
    max_conn: int = 5

    @classmethod
    def from_env(cls) -> "DBConfig":
        return cls(
            dsn=os.environ.get("TOOLMAKER_DB_DSN", DEFAULT_DSN),
        )

    @property
    def effective_dsn(self) -> str:
        return self.dsn or os.environ.get("TOOLMAKER_DB_DSN") or DEFAULT_DSN
