"""
Tool Executor - Executes generated tools.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import os

from .sandbox import execute_safe, SandboxError, SandboxTimeout


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    tool_name: str = ""


class ToolExecutor:
    """Executes generated tools and manages tool execution."""

    def __init__(
        self, sandbox_timeout: int = 10,
        extra_whitelist: Optional[List[str]] = None,
    ):
        self.executed_tools: List[Dict[str, Any]] = []
        self.tool_cache: Dict[str, Callable] = {}
        self.sandbox_timeout = sandbox_timeout
        self.extra_whitelist = extra_whitelist or []

    def execute_tool(self, tool_code: str, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool from its code."""
        try:
            result = execute_safe(
                tool_code,
                tool_name,
                timeout=self.sandbox_timeout,
                extra_whitelist=self.extra_whitelist,
                **kwargs,
            )

            self.executed_tools.append({
                "tool_name": tool_name,
                "success": True,
                "result": result,
            })

            return ToolResult(
                success=True,
                output=result,
                tool_name=tool_name,
            )
        except (SandboxError, SandboxTimeout) as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                tool_name=tool_name,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                tool_name=tool_name,
            )

    def execute_tool_from_file(self, file_path: str, **kwargs) -> ToolResult:
        """Execute a tool from a file."""
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"File not found: {file_path}",
            )

        with open(file_path, 'r') as f:
            tool_code = f.read()

        tool_name = os.path.splitext(os.path.basename(file_path))[0]
        return self.execute_tool(tool_code, tool_name, **kwargs)

    def execute_multiple_tools(self, tools: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute multiple tools."""
        results = []
        for tool in tools:
            result = self.execute_tool(
                tool["code"],
                tool["name"],
                **tool.get("kwargs", {}),
            )
            results.append(result)
        return results

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get the history of executed tools."""
        return self.executed_tools

    def clear_history(self) -> None:
        """Clear the execution history."""
        self.executed_tools = []

    def cache_tool(self, tool_name: str, tool_func: Callable) -> None:
        """Cache a tool for later execution."""
        self.tool_cache[tool_name] = tool_func

    def execute_cached_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a cached tool."""
        if tool_name not in self.tool_cache:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found in cache",
            )

        try:
            func = self.tool_cache[tool_name]
            result = func(**kwargs)

            self.executed_tools.append({
                "tool_name": tool_name,
                "success": True,
                "result": result,
            })

            return ToolResult(
                success=True,
                output=result,
                tool_name=tool_name,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                tool_name=tool_name,
            )


class ToolManager:
    """Manages tool generation, storage, and execution."""

    def __init__(self):
        self.generator = None
        self.executor = ToolExecutor()
        self.tools: Dict[str, Dict[str, Any]] = {}

    def add_tool(self, name: str, tool: Dict[str, Any]) -> None:
        """Add a tool to the manager."""
        self.tools[name] = tool

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name."""
        return self.tools.get(name)

    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{name}' not found",
            )

        return self.executor.execute_tool(
            tool["code"],
            name,
            **kwargs,
        )

    def list_tools(self) -> List[str]:
        """List all available tools."""
        return list(self.tools.keys())

    def remove_tool(self, name: str) -> bool:
        """Remove a tool by name."""
        if name in self.tools:
            del self.tools[name]
            return True
        return False
