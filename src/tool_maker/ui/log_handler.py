"""
Log capture handler - captures log records for live streaming to the UI.
"""

import logging
import threading
from datetime import datetime
from typing import Dict, List


class LogCaptureHandler(logging.Handler):
    """Captures log records into a thread-safe buffer for SSE streaming."""

    def __init__(self, max_records: int = 500):
        super().__init__()
        self._buffer: List[Dict] = []
        self._max = max_records
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "time": datetime.fromtimestamp(record.created)
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
        }
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) > self._max:
                self._buffer.pop(0)

    def get_since(self, since: int) -> List[Dict]:
        with self._lock:
            return list(self._buffer[since:])

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._buffer)


_LOG_HANDLER: LogCaptureHandler = None
_LOG_HANDLER_LOCK = threading.Lock()


def get_log_handler() -> LogCaptureHandler:
    global _LOG_HANDLER
    if _LOG_HANDLER is None:
        with _LOG_HANDLER_LOCK:
            if _LOG_HANDLER is None:
                _LOG_HANDLER = LogCaptureHandler()
                _LOG_HANDLER.setFormatter(
                    logging.Formatter(
                        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                    )
                )
                root = logging.getLogger()
                root.setLevel(logging.DEBUG)
                root.addHandler(_LOG_HANDLER)
    return _LOG_HANDLER
