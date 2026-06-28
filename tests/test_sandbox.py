import pytest
from tool_maker.tool.sandbox import execute_safe, SandboxError, SandboxTimeout


SIMPLE_TOOL = """
def add(a, b):
    return a + b
"""


def test_execute_simple_function():
    result = execute_safe(SIMPLE_TOOL, "add", a=1, b=2)
    assert result == 3


def test_execute_with_string():
    code = """
def greet(name):
    return f"Hello, {name}!"
"""
    result = execute_safe(code, "greet", name="World")
    assert result == "Hello, World!"


def test_execute_with_list():
    code = """
def double(items):
    return [x * 2 for x in items]
"""
    result = execute_safe(code, "double", items=[1, 2, 3])
    assert result == [2, 4, 6]


def test_function_not_found():
    with pytest.raises(SandboxError, match="not found"):
        execute_safe("x = 1", "nonexistent")


def test_syntax_error():
    with pytest.raises(SandboxError):
        execute_safe("def broken(:", "f")


def test_runtime_error():
    code = """
def crash():
    raise ValueError("boom")
"""
    with pytest.raises(SandboxError, match="boom"):
        execute_safe(code, "crash")


def test_timeout():
    code = """
def slow():
    import time
    time.sleep(100)
"""
    with pytest.raises(SandboxTimeout):
        execute_safe(code, "slow", timeout=1)


def test_blocked_module():
    code = """
def hack():
    import socket
    return socket.gethostname()
"""
    with pytest.raises(SandboxError):
        execute_safe(code, "hack")


def test_allowed_module():
    code = """
def use_math(x):
    import math
    return math.sqrt(x)
"""
    result = execute_safe(code, "use_math", x=9)
    assert result == 3.0


def test_json_serializable_result():
    code = """
def get_dict():
    return {"a": 1, "b": [2, 3], "c": None}
"""
    result = execute_safe(code, "get_dict")
    assert result == {"a": 1, "b": [2, 3], "c": None}
