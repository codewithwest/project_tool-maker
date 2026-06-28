"""
ToolFixer - Reads a saved tool, tries to execute it, and uses an LLM to fix it.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from tool_maker.tool.executor import ToolExecutor

logger = logging.getLogger(__name__)

_FIX_PROMPT = (
    "You are a Python code fixer. A user tried to run the following tool "
    "function but it failed with an error.\n\n"
    "Fix the code so the function works correctly. Return ONLY the fixed "
    "Python code inside ```python ... ``` markers.\n"
    "Keep the same function name and signature unless the error requires "
    "changing them.\n"
    "Make minimal changes — only fix what's broken.\n"
    "Ensure ALL parameters and the return value have strict type annotations.\n"
)


class ToolFixer:
    """Reads a tool file, executes it, and uses an LLM to fix failures."""

    def __init__(self, llm_provider=None,
                 executor: Optional[ToolExecutor] = None,
                 max_fix_attempts: int = 3):
        self.llm_provider = llm_provider
        self.executor = executor or ToolExecutor()
        self.max_fix_attempts = max_fix_attempts

    def fix_tool_file(
        self, file_path: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Read, test, and fix a tool file.

        Args:
            file_path: Path to the Python tool file.
            **kwargs: Keyword arguments to pass when executing the tool.

        Returns:
            Dict with keys: fixed (bool), attempts (int), code (str), error (str).
        """
        path = Path(file_path)
        if not path.exists():
            return {"fixed": False, "error": f"File not found: {file_path}"}

        code = path.read_text()
        name = path.stem

        return self.fix_tool_code(code, name, file_path, **kwargs)

    def fix_tool_code(
        self, code: str, function_name: str,
        file_path: Optional[str] = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Test and iteratively fix tool code.

        Args:
            code: Python source code.
            function_name: Name of the function to call.
            file_path: If provided, the fixed code is written back to this file.
            **kwargs: Arguments to pass when executing the function.

        Returns:
            Dict with keys: fixed (bool), attempts (int), code (str), error (str).
        """
        current_code = code
        last_error = ""

        for attempt in range(1, self.max_fix_attempts + 1):
            logger.info(
                "Fix attempt %d/%d for %s",
                attempt, self.max_fix_attempts, function_name,
            )

            result = self.executor.execute_tool(
                current_code, function_name, **kwargs
            )

            if result.success:
                if file_path:
                    Path(file_path).write_text(current_code)
                return {
                    "fixed": True,
                    "attempts": attempt,
                    "code": current_code,
                    "error": None,
                }

            last_error = result.error or "Unknown error"
            logger.warning("Attempt %d failed: %s", attempt, last_error)

            if self.llm_provider is None:
                break

            current_code = self._request_fix(current_code, last_error, function_name)
            if current_code is None:
                break

        return {
            "fixed": False,
            "attempts": self.max_fix_attempts,
            "code": current_code,
            "error": last_error,
        }

    def _request_fix(
        self, code: str, error: str, function_name: str
    ) -> Optional[str]:
        prompt = (
            f"{_FIX_PROMPT}\n"
            f"Function name: {function_name}\n\n"
            f"Current code:\n```\n{code}\n```\n\n"
            f"Error:\n{error}\n\n"
            f"Return the fixed code in ```python ... ``` markers."
        )
        try:
            response = self.llm_provider.generate(prompt)
            return self._extract_code(response) or code
        except Exception as e:
            logger.error("LLM fix request failed: %s", e)
            return None

    def _extract_code(self, response: str) -> Optional[str]:
        import re
        m = re.search(r"```python\s*\n(.*?)\n```", response, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        return m.group(1).strip() if m else None
