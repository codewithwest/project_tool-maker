"""Integration tests for the ToolMaker class."""

from unittest.mock import patch

import httpx

from tool_maker import ToolMaker
from tool_maker.tool_maker import (
    ToolMakerConfig,
    create_tool_maker,
    create_tool_maker_from_env,
)
from tool_maker.tool.generator import Tool


def _mock_empty_tags():
    return patch.object(
        httpx.Client, "get",
        return_value=httpx.Response(200, json={"models": []}),
    )


class TestToolMaker:
    def test_default_config(self):
        with _mock_empty_tags():
            tm = ToolMaker()
        assert tm.config.llm_provider == "ollama"
        assert tm.config.default_project_path == "."

    def test_custom_config(self):
        with _mock_empty_tags():
            config = ToolMakerConfig(
                llm_provider="ollama",
                model="llama3.1",
                default_project_path="/tmp",
            )
            tm = ToolMaker(config)
        assert tm.config.llm_provider == "ollama"
        assert tm.config.model == "llama3.1"
        assert tm.config.default_project_path == "/tmp"

    def test_config_via_kwargs(self):
        with _mock_empty_tags():
            tm = ToolMaker(llm_provider="ollama", model="llama3.3")
        assert tm.config.model == "llama3.3"

    def test_set_project_path(self):
        with _mock_empty_tags():
            tm = ToolMaker()
        tm.set_project_path("/tmp")
        assert tm.config.default_project_path == "/tmp"

    def test_set_output_dir(self):
        with _mock_empty_tags():
            tm = ToolMaker()
        tm.set_output_dir("/tmp/tools")
        assert tm.config.output_dir == "/tmp/tools"

    def test_clear_cache(self):
        with _mock_empty_tags():
            tm = ToolMaker()
        tm.clear_cache()  # Should not raise

    def test_create_tool_returns_tool(self):
        tm = ToolMaker(output_dir=None)
        tool = tm.create_tool("read json file", project_path=".")
        assert tool is not None
        assert isinstance(tool, Tool)

    def test_create_tool_without_output_dir(self):
        tm = ToolMaker(output_dir="")
        tool = tm.create_tool("read csv data")
        assert tool is not None

    def test_execute_tool(self):
        tm = ToolMaker()
        code = """
def adder(a, b):
    return a + b
"""
        tool = Tool(name="adder", description="add", parameters={}, code=code)
        result = tm.tool_executor.execute_tool(tool.code, tool.name, a=1, b=2)
        assert result.success
        assert result.output == 3

    def test_create_and_execute_tool_success(self):
        tm = ToolMaker(output_dir=None)
        mock_code = (
            "def add_two_numbers(a: int, b: int) -> int:\n"
            '    """Add two numbers together."""\n'
            "    return a + b\n"
        )
        with patch.object(tm.llm_provider, "generate",
                          return_value=f"```python\n{mock_code}\n```"):
            tool = tm.create_tool("make an adder that adds two numbers")
        assert tool is not None
        assert isinstance(tool, Tool)
        assert "adder" in tool.name or "add" in tool.name

        result = tm.tool_executor.execute_tool(tool.code, tool.name, a=3, b=5)
        assert result.success
        assert result.output == 8

    def test_list_available_tools(self):
        tm = ToolMaker()
        tools = tm.list_available_tools(project_path=".")
        assert isinstance(tools, list)

    def test_components_initialized(self):
        with _mock_empty_tags():
            tm = ToolMaker()
        assert tm.llm_provider is not None
        assert tm.project_scanner is not None
        assert tm.tool_generator is not None
        assert tm.tool_executor is not None


class TestFactories:
    def test_create_tool_maker(self):
        with _mock_empty_tags():
            tm = create_tool_maker()
        assert isinstance(tm, ToolMaker)
        assert tm.config.llm_provider == "ollama"

    def test_create_tool_maker_from_env(self, monkeypatch):
        monkeypatch.setenv("TOOL_MAKER_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("TOOL_MAKER_MODEL", "llama3.3")
        tm = create_tool_maker_from_env()
        assert tm.config.llm_provider == "ollama"
        assert tm.config.model == "llama3.3"


class TestIntegration:
    def test_analyze_then_create_tool(self):
        tm = ToolMaker(output_dir=None)
        project_info = tm.analyze_project(".")
        assert "name" in project_info
        assert "modules_count" in project_info

        tool = tm.create_tool("parse json file", project_path=".")
        assert tool is not None

    def test_set_project_path_reflects_in_scan(self):
        tm = ToolMaker()
        tm.set_project_path("/tmp")
        assert tm.project_scanner.project_path.name == "tmp"
