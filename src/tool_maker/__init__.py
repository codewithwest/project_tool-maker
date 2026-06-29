"""
Tool Maker - An intelligent tool-making package that leverages LLMs.
"""

__version__ = "0.3.0"
__author__ = "Codewithwest"

from tool_maker.analyzer.project_scanner import ProjectScanner
from tool_maker.client import ToolMakerClient
from tool_maker.config import ToolMakerConfigFile
from tool_maker.db.backends import SqliteBackend, PostgresBackend, get_backend
from tool_maker.llm.provider import (
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    get_provider,
)
from tool_maker.tool.generator import ToolGenerator
from tool_maker.tool.executor import ToolExecutor
from tool_maker.tool_fixer import ToolFixer
from tool_maker.tool_maker import (
    ToolMaker,
    create_tool_maker,
    create_tool_maker_from_env,
)

__all__ = [
    "ProjectScanner",
    "ToolMakerClient",
    "ToolMakerConfigFile",
    "SqliteBackend",
    "PostgresBackend",
    "get_backend",
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "get_provider",
    "ToolGenerator",
    "ToolExecutor",
    "ToolFixer",
    "ToolMaker",
    "create_tool_maker",
    "create_tool_maker_from_env",
]
