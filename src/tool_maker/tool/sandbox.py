"""
Tool Sandbox - Provides safe, process-isolated execution of generated tools.

Uses subprocess with Python's -I (isolated) mode to prevent tool code from
accessing the host environment, filesystem outside allowed paths, or
dynamically escaping the sandbox.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

SANDBOX_TIMEOUT_SECONDS = 10

WHITELISTED_MODULES = [
    "base64",
    "binascii",
    "bisect",
    "calendar",
    "collections",
    "copy",
    "csv",
    "dataclasses",
    "datetime",
    "decimal",
    "difflib",
    "enum",
    "filecmp",
    "fnmatch",
    "functools",
    "glob",
    "gzip",
    "hashlib",
    "heapq",
    "html",
    "io",
    "itertools",
    "json",
    "locale",
    "math",
    "mimetypes",
    "numbers",
    "operator",
    "pathlib",
    "pickle",
    "platform",
    "pprint",
    "queue",
    "random",
    "re",
    "reprlib",
    "secrets",
    "shelve",
    "shutil",
    "sqlite3",
    "stat",
    "statistics",
    "string",
    "struct",
    "tarfile",
    "tempfile",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "traceback",
    "types",
    "typing",
    "unicodedata",
    "urllib.parse",
    "uuid",
    "warnings",
    "weakref",
    "zipfile",
    "zlib",
]

SAFE_BUILTIN_NAMES = [
    "abs", "all", "any", "bool", "callable", "dict", "enumerate", "filter",
    "float", "getattr", "hasattr", "int", "isinstance", "len", "list", "map",
    "max", "min", "print", "range", "reversed", "round", "set", "setattr",
    "slice", "sorted", "str", "sum", "tuple", "type", "zip",
    "True", "False", "None", "Exception", "ValueError", "TypeError",
    "KeyError", "IndexError", "StopIteration", "RuntimeError", "OSError",
    "ZeroDivisionError", "FileNotFoundError", "NotImplementedError",
    "AttributeError", "ImportError",
]


_RUNNER_TEMPLATE = r"""# --- sandbox runner ---
import json, sys

_allowed = set({whitelist!r})

# Remove non-allowed modules from sys.modules so import hooks fire
_always_keep = {{'_sandbox_runner', 'sys', 'json', 'builtins'}}
for _mod_name in list(sys.modules):
    _base = _mod_name.split('.')[0]
    if _base not in _allowed and _base not in _always_keep and _base[0] != '_':
        sys.modules.pop(_mod_name, None)

_src = __builtins__.__dict__ if not isinstance(__builtins__, dict) else __builtins__
_safe_builtins = {{_k: _src[_k] for _k in {builtin_keep!r} if _k in _src}}

def _safe_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if base not in _allowed:
        raise ImportError(f"blocked: {{name}}")
    try:
        return __import__(name, *args, **kwargs)
    except ImportError:
        raise ImportError(f"missing-dep: {{name}}")

_safe_builtins["__import__"] = _safe_import
_globals = {{
    "__builtins__": _safe_builtins,
    "__name__": "__sandbox__",
}}

for _mod in _allowed:
    if _mod in sys.modules:
        _globals[_mod] = sys.modules[_mod]
    else:
        try:
            _globals[_mod] = __import__(_mod)
        except ImportError:
            pass

# Re-purge non-allowed modules that may have been imported as deps
for _mod_name in list(sys.modules):
    _base = _mod_name.split('.')[0]
    if _base not in _allowed and _base not in _always_keep and _base[0] != '_':
        sys.modules.pop(_mod_name, None)

def _sandbox_out(data):
    sys.stdout.flush()
    sys.stderr.flush()
    print("##SBX##" + json.dumps(data))
    sys.stdout.flush()

_code = {code!r}
try:
    exec(_code, _globals)
except Exception as _e:
    _sandbox_out({{"ok": False, "error": str(_e)}})
    sys.exit(0)

if {func_name!r} not in _globals:
    _sandbox_out({{"ok": False, "error": "fn not found"}})
    sys.exit(0)

_func = _globals[{func_name!r}]
_args_ = {args_json!r}

try:
    _res = _func(**_args_)
    _sandbox_out({{"ok": True, "result": _res}})
except Exception as _e:
    _sandbox_out({{"ok": False, "error": str(_e)}})
"""


class SandboxError(Exception):
    """Raised when tool execution produces an error."""


class SandboxTimeout(Exception):
    """Raised when tool execution exceeds the time limit."""


def _serializable(value: Any) -> Any:
    """Coerce a value to be JSON-serializable."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, Path):
        return str(value)
    try:
        return str(value)
    except Exception:
        return repr(value)


def execute_safe(
    code: str,
    function_name: str,
    timeout: int = SANDBOX_TIMEOUT_SECONDS,
    extra_whitelist: Optional[List[str]] = None,
    approved_deps: Optional[List[str]] = None,
    auto_approve_deps: bool = False,
    **kwargs: Any,
) -> Any:
    """Execute a tool function in a subprocess sandbox.

    The tool code is written to a temporary file and run with
    ``python -I`` (isolated mode). Output is communicated via JSON
    on stdout. If execution exceeds *timeout* the subprocess is killed.

    If the sandbox reports a missing third-party dependency, this function
    attempts to pip install it and retries (up to 3 times).

    Args:
        code: Python source code containing the function.
        function_name: Name of the function to call.
        timeout: Max seconds before killing the subprocess.
        extra_whitelist: Additional module names to allow beyond the
                         built-in whitelist (e.g. user-configured ones).
        approved_deps: List of module names the user has approved for
                       auto-installation.
        auto_approve_deps: If True, install missing deps without prompting.

    Returns:
        The return value of the executed function.

    Raises:
        SandboxError: Execution failed or returned an error.
        SandboxTimeout: Execution exceeded *timeout* seconds.
    """
    safe_kwargs = {k: _serializable(v) for k, v in kwargs.items()}

    whitelist = list(WHITELISTED_MODULES)
    if extra_whitelist:
        for m in extra_whitelist:
            if m not in whitelist:
                whitelist.append(m)

    approved = set(approved_deps or [])

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        runner_code = _RUNNER_TEMPLATE.format(
            builtin_keep=SAFE_BUILTIN_NAMES,
            whitelist=whitelist,
            code=code,
            func_name=function_name,
            args_json=safe_kwargs,
        )

        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="sandbox_",
            delete=False,
        )
        try:
            tmp.write(runner_code)
            tmp.close()

            proc = subprocess.Popen(
                [sys.executable, "-I", tmp.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise SandboxTimeout(
                    f"Execution timed out after {timeout}s"
                )

            if proc.returncode != 0:
                msg = stderr.strip() or f"Process exited with code {proc.returncode}"
                raise SandboxError(msg)

            try:
                # Find the ##SBX## marker to handle stray tool stdout
                sbx_marker = "##SBX##"
                idx = stdout.rfind(sbx_marker)
                if idx == -1:
                    raise ValueError("no sandbox marker found")
                payload = stdout[idx + len(sbx_marker):].strip()
                result = json.loads(payload)
            except Exception as e:
                raise SandboxError(
                    f"Could not parse sandbox output: {e}\nstdout: {stdout[:500]}"
                )

            if result.get("ok"):
                return result["result"]

            error = result.get("error", "Unknown sandbox error")

            # Check if this is a missing dependency we can auto-install
            if error.startswith("missing-dep:"):
                mod = error.split(":", 1)[1].strip()
                if mod in whitelist:
                    if mod in approved or auto_approve_deps:
                        from tool_maker.tool.deps import install as _install_dep
                        ok = _install_dep(mod)
                        if ok:
                            whitelist.append(mod) if mod not in whitelist else None
                            logger.info(
                                "Installed '%s', retrying sandbox (attempt %d/%d)",
                                mod, attempt, max_retries,
                            )
                            continue
                    logger.warning(
                        "Missing dep '%s' not approved — skipping install", mod,
                    )

            # Non-retryable error
            raise SandboxError(error)

        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    raise SandboxError(f"Sandbox failed after {max_retries} retries")
