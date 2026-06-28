from tool_maker.tool.generator import ToolGenerator, Tool


def test_fallback_name():
    gen = ToolGenerator()
    assert gen._fallback_name("read json file") == "read_json_file_tool"
    assert gen._fallback_name("parse CSV data!") == "parse_csv_data_tool"


def test_fallback_name_empty():
    gen = ToolGenerator()
    name = gen._fallback_name("a")
    assert name == "generated_tool"


def test_extract_code_with_python_marker():
    gen = ToolGenerator()
    response = "```python\ndef hello():\n    return 1\n```"
    code = gen._extract_code(response)
    assert code == "def hello():\n    return 1"


def test_extract_code_without_language():
    gen = ToolGenerator()
    response = "```\ndef hello():\n    return 1\n```"
    code = gen._extract_code(response)
    assert code == "def hello():\n    return 1"


def test_extract_code_no_block():
    gen = ToolGenerator()
    assert gen._extract_code("just text") is None


def test_extract_function_name():
    gen = ToolGenerator()
    name = gen._extract_function_name("def add(a, b):\n    return a + b")
    assert name == "add"


def test_extract_function_name_no_match():
    gen = ToolGenerator()
    assert gen._extract_function_name("x = 1") is None


def test_extract_parameters():
    gen = ToolGenerator()
    code = "def add(a: int, b: float, c=1):\n    return a + b"
    params = gen._extract_parameters(code)
    assert params == {"a": "any", "b": "any"}


def test_extract_parameters_no_match():
    gen = ToolGenerator()
    assert gen._extract_parameters("x = 1") == {}


def test_extract_dependencies():
    gen = ToolGenerator()
    code = """
import os
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup
"""
    deps = gen._extract_dependencies(code)
    assert "requests" in deps
    assert "bs4" in deps
    assert "os" not in deps
    assert "json" not in deps
    assert "pathlib" not in deps


def test_parse_response_valid():
    gen = ToolGenerator()
    response = "```python\ndef add(a: int, b: int):\n    return a + b\n```"
    tool = gen._parse_response(response, "add two numbers")
    assert tool is not None
    assert tool.name == "add"
    assert "return a + b" in tool.code
    assert tool.parameters == {"a": "any", "b": "any"}


def test_parse_response_no_code():
    gen = ToolGenerator()
    tool = gen._parse_response("just text", "do something")
    assert tool is not None
    assert "LLM provider" in tool.code


def test_generate_tool_without_provider_returns_stub():
    gen = ToolGenerator()
    tool = gen.generate_tool("do something", project_info={})
    assert isinstance(tool, Tool)
    assert "LLM provider" in tool.code


def test_generate_tool_with_provider():
    gen = ToolGenerator()

    class FakeProvider:
        @staticmethod
        def generate(prompt, **kw):
            return "```python\ndef hello(name: str):\n    return f'Hello {name}'\n```"

    tool = gen.generate_tool("say hello", project_info={}, llm_provider=FakeProvider())
    assert tool is not None
    assert tool.name == "hello"
    assert "Hello" in tool.code


def test_generate_from_project():
    gen = ToolGenerator()
    project_info = {
        "modules": [
            {
                "name": "mymod",
                "functions": [
                    {"name": "func1", "docstring": "does something"},
                    {"name": "func2", "docstring": None},
                ],
            }
        ]
    }
    tools = gen.generate_from_project(project_info)
    assert len(tools) == 2
    assert tools[0].name == "func1"
    assert tools[0].description == "does something"


def test_save_tool(tmp_path):
    gen = ToolGenerator()
    tool = Tool(name="test_tool", description="test", parameters={}, code="x = 1")
    gen.save_tool(tool, str(tmp_path))
    saved = tmp_path / "test_tool.py"
    assert saved.exists()
    assert saved.read_text() == "x = 1"
