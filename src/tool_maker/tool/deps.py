"""
Sandbox dependency manager — auto-install third-party packages.
"""

import ast
import importlib
import importlib.util
import logging
import subprocess
import sys
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

STDLIB_MODULES: Set[str] = {
    "_thread", "abc", "argparse", "array", "ast", "atexit",
    "base64", "bdb", "binascii", "bisect", "builtins", "bz2",
    "calendar", "cmath", "cmd", "code", "codecs", "codeop",
    "collections", "colorsys", "compileall", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile",
    "csv", "ctypes",
    "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "doctest",
    "email", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib",
    "grp", "gzip",
    "hashlib", "heapq", "hmac", "html", "http",
    "imaplib", "importlib", "inspect", "io", "ipaddress",
    "itertools",
    "json",
    "keyword",
    "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing",
    "netrc", "nis", "nntplib", "numbers",
    "opcode", "operator", "optparse", "os",
    "pathlib", "pdb", "pickle", "pickletools", "pipes",
    "pkgutil", "platform", "plistlib", "poplib", "posix",
    "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "pyexpat",
    "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource",
    "rlcompleter", "runpy",
    "sched", "secrets", "select", "selectors", "shelve",
    "shlex", "shutil", "signal", "site", "smtplib", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics",
    "string", "stringprep", "struct", "subprocess", "symtable",
    "sys", "sysconfig", "syslog",
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "types", "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid",
    "venv",
    "warnings", "wave", "weakref", "webbrowser",
    "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
}

_MODULE_TO_PACKAGE: Dict[str, str] = {
    "bs4": "beautifulsoup4",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "lxml": "lxml",
    "crypto": "pycryptodome",
    "nacl": "PyNaCl",
    "zmq": "pyzmq",
    "dateutil": "python-dateutil",
    "markdown": "Markdown",
    "mistune": "mistune",
    "pymongo": "pymongo",
    "redis": "redis",
    "psutil": "psutil",
    "sentry_sdk": "sentry-sdk",
    "flask": "Flask",
    "django": "Django",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "gunicorn": "gunicorn",
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "tensorflow": "tensorflow",
    "torch": "torch",
    "transformers": "transformers",
    "selenium": "selenium",
    "playwright": "playwright",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "pydantic": "pydantic",
    "rich": "rich",
    "click": "click",
    "typer": "typer",
    "pytest": "pytest",
    "mypy": "mypy",
    "ruff": "ruff",
    "black": "black",
    "isort": "isort",
    "flake8": "flake8",
}

WHITELISTED = {
    "base64", "binascii", "bisect", "calendar", "collections",
    "copy", "csv", "dataclasses", "datetime", "decimal", "difflib",
    "enum", "filecmp", "fnmatch", "functools", "glob", "gzip",
    "hashlib", "heapq", "html", "io", "itertools", "json", "locale",
    "math", "mimetypes", "numbers", "operator", "pathlib", "pickle",
    "platform", "pprint", "queue", "random", "re", "reprlib",
    "secrets", "shelve", "shutil", "sqlite3", "stat", "statistics",
    "string", "struct", "tarfile", "tempfile", "textwrap",
    "threading", "time", "timeit", "traceback", "types", "typing",
    "unicodedata", "urllib", "uuid", "warnings", "weakref", "zipfile",
    "zlib",
}


def scan_imports(code: str) -> List[str]:
    """Extract top-level module names from Python source."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                modules.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                modules.add(top)
    return sorted(modules)


def is_third_party(module_name: str) -> bool:
    """Return True if *module_name* is neither stdlib nor already whitelisted."""
    if module_name in STDLIB_MODULES:
        return False
    if module_name in WHITELISTED:
        return False
    return True


def resolve_package(module_name: str) -> str:
    """Map a Python module name to its pip package name."""
    return _MODULE_TO_PACKAGE.get(module_name, module_name)


def is_installed(module_name: str) -> bool:
    """Check if a module is already importable."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError, ImportError):
        return False


def missing_deps(code: str) -> List[str]:
    """Return third-party modules used in *code* that are not installed."""
    all_imports = scan_imports(code)
    return [m for m in all_imports if is_third_party(m) and not is_installed(m)]


def _pip_cmd() -> List[str]:
    """Return the pip command for this environment (uv pip or pip)."""
    import shutil
    if shutil.which("uv"):
        return ["uv", "pip", "install"]
    return [sys.executable, "-m", "pip", "install"]


def install(module_name: str) -> bool:
    """Install a pip package for *module_name*.

    Returns True if installation succeeded.
    """
    package = resolve_package(module_name)
    logger.info("Installing package '%s' (for module '%s') ...", package, module_name)
    cmd = _pip_cmd() + [package]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Successfully installed '%s'", package)
            return True
        logger.warning(
            "%s failed:\n%s\n%s",
            " ".join(cmd), result.stdout.strip(), result.stderr.strip(),
        )
        return False
    except subprocess.TimeoutExpired:
        logger.warning("pip install '%s' timed out", package)
        return False
    except Exception as e:
        logger.warning("pip install '%s' raised: %s", package, e)
        return False


def ensure(
    module_name: str,
    approved: Optional[List[str]] = None,
    auto_approve: bool = False,
    prompt_fn=None,
) -> bool:
    """Ensure *module_name* is installed.

    Args:
        module_name: The module to check/install.
        approved: List of previously approved module names.
        auto_approve: If True, install without prompting.
        prompt_fn: Callable(module_name) -> bool for interactive approval.

    Returns:
        True if the module is (or became) available.
    """
    if is_installed(module_name):
        return True

    if module_name in (approved or []):
        return install(module_name)

    if auto_approve:
        return install(module_name)

    if prompt_fn is not None:
        if prompt_fn(module_name):
            return install(module_name)
        return False

    return install(module_name)


def install_deps_for_code(
    code: str,
    approved: Optional[List[str]] = None,
    auto_approve: bool = False,
    prompt_fn=None,
) -> List[str]:
    """Install all missing third-party dependencies for *code*.

    Returns the list of modules that were installed.
    """
    installed = []
    for mod in missing_deps(code):
        if ensure(mod, approved=approved, auto_approve=auto_approve,
                   prompt_fn=prompt_fn):
            installed.append(mod)
    return installed
