"""
Simple .env file loader — no external dependencies.

Looks for `.env` in the current working directory and/or
`~/.config/tool-maker/.env`.  Populates `os.environ` with
`setdefault` so existing env vars take precedence.
"""

import logging
import os
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(
    r"^\s*(?:export\s+)?"
    r"(?P<key>[A-Za-z_]\w*)"
    r"\s*=\s*"
    r"(?P<value>.*)"
    r"\s*$",
)

_SEARCH_PATHS = [
    Path.cwd() / ".env",
    Path.home() / ".config" / "tool-maker" / ".env",
]


def _parse_line(line: str) -> Optional[tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = _ENV_PATTERN.match(line)
    if not m:
        return None
    key = m.group("key")
    raw = m.group("value")
    # Strip surrounding quotes
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1]
    return key, raw


def load_dotenv(paths: Optional[List[Path]] = None) -> int:
    """Load variables from .env files into os.environ via setdefault.

    Args:
        paths:  List of .env file paths.
                Defaults to [cwd/.env, ~/.config/tool-maker/.env].

    Returns:
        Number of variables loaded.
    """
    loaded = 0
    for path in (paths or _SEARCH_PATHS):
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
            continue
        for line in text.splitlines():
            parsed = _parse_line(line)
            if parsed:
                key, value = parsed
                if key not in os.environ:
                    os.environ[key] = value
                    loaded += 1
        logger.debug("Loaded %s from %s", path, loaded)
    if loaded:
        logger.info("Loaded %d env var(s) from .env file(s)", loaded)
    return loaded
