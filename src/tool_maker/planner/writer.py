"""
WriterToFile - Writes content to a file on disk.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class WriterToFile:
    """Writes string content to a file."""

    def __init__(self, output_dir: str = "."):
        self.output_dir = output_dir

    def write(self, content: str, filename: str) -> str:
        """Write content to a file. Returns the absolute path."""
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        abs_path = os.path.abspath(path)
        logger.info("Wrote %d bytes to %s", len(content), abs_path)
        return abs_path

    def write_with_plan_result(
        self, content: str, filename: Optional[str] = None
    ) -> str:
        """Write content, auto-naming the file if not specified."""
        if filename is None:
            filename = "output.txt"
        return self.write(content, filename)
