"""
Tool Generator - Creates tools using LLM-powered code generation.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GENERATION_PROMPT = (
    "You are a Python code generator. Given a user's request, generate a "
    "single Python function that fulfills it.\n\n"
    "Rules:\n"
    "1. Output ONLY the Python code block, nothing else.\n"
    "2. The function must be self-contained (include all imports inside "
    "the function or at the top).\n"
    "3. Use type annotations for all parameters and return type.\n"
    "4. Function name must be a valid Python identifier derived from "
    "the request.\n"
    "5. Add a docstring describing what the function does.\n"
    "6. Use only standard library modules unless the request explicitly "
    "requires an external one.\n"
    "7. Handle edge cases and errors gracefully.\n"
    "8. The function should be practical and actually implement the "
    "requested behavior.\n\n"
    "Wrap your code in ```python ... ``` markers."
)


@dataclass
class Tool:
    """Represents a generated tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    code: str
    module: str = "generated_tools"
    function_name: str = ""
    dependencies: List[str] = field(default_factory=list)


class ToolGenerator:
    """Generates tools by prompting an LLM."""

    def __init__(self, project_scanner=None):
        self.project_scanner = project_scanner
        self.generated_tools: List[Tool] = []

    def generate_tool(
        self,
        request: str,
        project_info: Optional[Dict[str, Any]] = None,
        llm_provider=None,
    ) -> Optional[Tool]:
        if llm_provider is None:
            logger.warning("No LLM provider available for tool generation")
            return self._make_stub(request)

        logger.info("Generating tool via LLM: request=%s", request[:80])
        prompt = self._build_prompt(request, project_info)

        try:
            response = llm_provider.generate(prompt)
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return self._make_stub(request)

        return self._parse_response(response, request)

    def _build_prompt(
        self, request: str, project_info: Optional[Dict[str, Any]] = None
    ) -> str:
        parts = [_GENERATION_PROMPT]
        parts.append(f"\nUser request: {request}")
        if project_info:
            parts.append(
                "\nProject context (available modules/functions to "
                f"consider):\n{project_info}"
            )
        return "\n".join(parts)

    def _parse_response(self, response: str, request: str) -> Optional[Tool]:
        code = self._extract_code(response)
        if not code:
            logger.warning("No code block found in LLM response")
            return self._make_stub(request, response)

        name = self._extract_function_name(code) or self._fallback_name(request)
        params = self._extract_parameters(code)
        deps = self._extract_dependencies(code)

        return Tool(
            name=name,
            description=request,
            parameters=params,
            code=code,
            dependencies=deps,
        )

    def _extract_code(self, response: str) -> Optional[str]:
        m = re.search(r"```python\s*\n(.*?)\n```", response, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        if m:
            return m.group(1).strip()
        return None

    def _extract_function_name(self, code: str) -> Optional[str]:
        m = re.search(r"def\s+(\w+)\s*\(", code)
        return m.group(1) if m else None

    def _extract_parameters(self, code: str) -> Dict[str, Any]:
        m = re.search(r"def\s+\w+\s*\((.*?)\):", code, re.DOTALL)
        if not m:
            return {}
        sig = m.group(1)
        params = {}
        for part in sig.split(","):
            part = part.strip()
            if not part or part == "self" or "=" in part and not part.startswith("*"):
                continue
            if ":" in part:
                name_type = part.split(":")[0].strip()
                params[name_type] = "any"
            elif part and not part.startswith("*"):
                params[part] = "any"
        return params

    def _extract_dependencies(self, code: str) -> List[str]:
        deps = set()
        for m in re.finditer(r"^\s*import\s+(\S+)", code, re.MULTILINE):
            deps.add(m.group(1).split(".")[0])
        for m in re.finditer(
            r"^\s*from\s+(\S+)\s+import", code, re.MULTILINE
        ):
            deps.add(m.group(1).split(".")[0])
        stdlib = {
            "os", "sys", "json", "csv", "re", "math", "pathlib",
            "collections", "itertools", "functools", "typing",
            "datetime", "statistics", "decimal", "random", "time",
            "io", "textwrap", "hashlib", "uuid", "copy", "pprint",
            "argparse", "logging", "warnings", "abc", "enum",
        }
        return sorted(deps - stdlib)

    def _fallback_name(self, request: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", "", request.lower())
        words = [w for w in cleaned.split() if w and not w.startswith("a")]
        if not words:
            return "generated_tool"
        name = "_".join(words[:4])
        if not name.endswith("_tool"):
            name += "_tool"
        return name

    def _make_stub(self, request: str, llm_raw: str = "") -> Tool:
        code = f"""
def {self._fallback_name(request)}(**kwargs):
    \"\"\"{request}\"\"\"
    return "Tool generation requires an LLM provider"
"""
        return Tool(
            name=self._fallback_name(request),
            description=request,
            parameters={},
            code=code,
            dependencies=[],
        )

    def generate_from_project(self, project_info: Dict[str, Any]) -> List[Tool]:
        tools = []
        for module in project_info.get("modules", []):
            for func in module.get("functions", []):
                tool = Tool(
                    name=func["name"],
                    description=func.get("docstring", "No description"),
                    parameters={},
                    code=f"def {func['name']}(): pass",
                    module=module["name"],
                )
                tools.append(tool)
        return tools

    def save_tool(self, tool: Tool, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{tool.name}.py")
        with open(output_path, "w") as f:
            f.write(tool.code)
        logger.info("Tool saved to %s", output_path)

    def save_all_tools(self, tools: List[Tool], output_dir: str) -> None:
        for tool in tools:
            self.save_tool(tool, output_dir)
