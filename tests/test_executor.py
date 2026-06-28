from tool_maker.tool.executor import ToolExecutor
from tool_maker.tool.generator import Tool


SAMPLE_TOOL_CODE = """
def sample_tool(x, y):
    return x * y
"""


def test_execute_tool_success():
    executor = ToolExecutor()
    tool = Tool(
        name="sample_tool", description="test", parameters={}, code=SAMPLE_TOOL_CODE
    )
    result = executor.execute_tool(tool.code, tool.name, x=3, y=4)
    assert result.success
    assert result.output == 12
    assert result.tool_name == "sample_tool"


def test_execute_tool_not_found():
    executor = ToolExecutor()
    result = executor.execute_tool(SAMPLE_TOOL_CODE, "nonexistent")
    assert not result.success
    assert "not found" in (result.error or "")


def test_execute_tool_syntax_error():
    executor = ToolExecutor()
    result = executor.execute_tool("def broken(: pass", "broken")
    assert not result.success


def test_execute_tool_runtime_error():
    code = """
def bad():
    raise ValueError("oops")
"""
    executor = ToolExecutor()
    result = executor.execute_tool(code, "bad")
    assert not result.success
    assert "oops" in (result.error or "")


def test_execution_history():
    executor = ToolExecutor()
    executor.execute_tool(SAMPLE_TOOL_CODE, "sample_tool", x=1, y=2)
    executor.execute_tool(SAMPLE_TOOL_CODE, "sample_tool", x=3, y=4)
    history = executor.get_execution_history()
    assert len(history) == 2
    assert history[0]["tool_name"] == "sample_tool"
    assert history[1]["result"] == 12


def test_clear_history():
    executor = ToolExecutor()
    executor.execute_tool(SAMPLE_TOOL_CODE, "sample_tool", x=1, y=2)
    executor.clear_history()
    assert len(executor.get_execution_history()) == 0


def test_execute_cached_tool():
    executor = ToolExecutor()

    def cached_func(a, b):
        return a + b

    executor.cache_tool("adder", cached_func)
    result = executor.execute_cached_tool("adder", a=5, b=7)
    assert result.success
    assert result.output == 12


def test_execute_cached_tool_not_found():
    executor = ToolExecutor()
    result = executor.execute_cached_tool("missing")
    assert not result.success
    assert "not found" in (result.error or "")


def test_sandbox_timeout():
    code = """
def infinite():
    while True:
        pass
"""
    executor = ToolExecutor(sandbox_timeout=1)
    result = executor.execute_tool(code, "infinite")
    assert not result.success
    assert "timed out" in (result.error or "").lower()
