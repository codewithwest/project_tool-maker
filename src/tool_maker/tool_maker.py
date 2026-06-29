"""
Main ToolMaker class - Orchestrates all components.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tool_maker.analyzer.project_scanner import ProjectScanner
from tool_maker.config import ToolMakerConfigFile
from tool_maker.dotenv import load_dotenv
from tool_maker.llm.provider import LLMProvider, get_provider
from tool_maker.planner import (
    PlanExecutor,
    Planner,
    PlanValidator,
    ResultReviewer,
    WriterToFile,
)
from tool_maker.tool.executor import ToolExecutor
from tool_maker.tool.generator import ToolGenerator
from tool_maker.tool_fixer import ToolFixer

logger = logging.getLogger(__name__)

# Load .env once at import time
load_dotenv()


@dataclass
class ToolMakerConfig:
    """Configuration for ToolMaker."""
    llm_provider: str = "ollama"
    api_key: Optional[str] = None
    model: str = "gemma4:31b-cloud"
    default_project_path: str = "."
    output_dir: str = "./generated_tools"
    ollama_base_url: str = "http://localhost:11434"


class ToolMaker:
    """
    Main ToolMaker class that orchestrates all components.

    Provides both sync and async APIs for project analysis,
    tool generation, and tool execution.
    """

    def __init__(self, config: Optional[ToolMakerConfig] = None, **kwargs):
        self._explicit_config = set(kwargs.keys())
        self.config = config or ToolMakerConfig(**kwargs)
        if config is not None:
            # Mark all non-default fields as explicit when a full config is passed
            from dataclasses import fields
            for f in fields(ToolMakerConfig):
                if getattr(config, f.name) != f.default:
                    self._explicit_config.add(f.name)
        self.file_config = ToolMakerConfigFile()
        self._merge_db_config()
        self.llm_provider: Optional[LLMProvider] = None
        self.project_scanner: Optional[ProjectScanner] = None
        self.tool_generator: Optional[ToolGenerator] = None
        self.tool_executor: Optional[ToolExecutor] = None
        self.planner: Optional[Planner] = None
        self.plan_validator: Optional[PlanValidator] = None
        self.plan_executor: Optional[PlanExecutor] = None
        self.reviewer: Optional[ResultReviewer] = None
        self.writer: Optional[WriterToFile] = None
        self.tool_fixer: Optional[ToolFixer] = None
        self._initialize_components()

    def _initialize_components(self) -> None:
        kwargs = {
            "api_key": self.config.api_key,
            "model": self.config.model,
        }
        if self.config.llm_provider == "ollama" and self.config.ollama_base_url:
            kwargs["base_url"] = self.config.ollama_base_url
        self.llm_provider = get_provider(
            self.config.llm_provider,
            **kwargs,
        )
        self.project_scanner = ProjectScanner(self.config.default_project_path)
        self.tool_generator = ToolGenerator(self.project_scanner)
        self.tool_executor = ToolExecutor(
            extra_whitelist=self.file_config.extra_whitelist,
            approved_deps=self.file_config.approved_deps,
            auto_approve_deps=self.file_config.auto_approve_deps,
        )
        self.planner = Planner(llm_provider=self.llm_provider)
        self.plan_validator = PlanValidator(llm_provider=self.llm_provider)
        self.plan_executor = PlanExecutor(
            tool_generator=self.tool_generator,
            llm_provider=self.llm_provider,
        )
        self.reviewer = ResultReviewer(llm_provider=self.llm_provider)
        self.writer = WriterToFile(output_dir=self.config.output_dir)
        self.tool_fixer = ToolFixer(
            llm_provider=self.llm_provider,
            executor=self.tool_executor,
        )

    # ── Project Analysis ──────────────────────────────────────────────

    def analyze_project(self, project_path: Optional[str] = None) -> Dict[str, Any]:
        path = project_path or self.config.default_project_path
        logger.info("Analyzing project: %s", path)
        scanner = (
            ProjectScanner(path)
            if path != self.config.default_project_path
            else self.project_scanner
        )
        if scanner is not self.project_scanner:
            self.project_scanner = scanner
        return self.project_scanner.scan()

    # ── Tool Creation ──────────────────────────────────────────────────

    def create_tool(
        self, query: str, project_path: Optional[str] = None
    ) -> Optional[Any]:
        logger.info("Creating tool: query=%s", query[:80])
        project_info = self._get_project_info(project_path)
        tool = self.tool_generator.generate_tool(
            query, project_info, llm_provider=self.llm_provider
        )
        if tool and self.config.output_dir:
            self.tool_generator.save_tool(tool, self.config.output_dir)
        return tool

    # ── Tool Execution ─────────────────────────────────────────────────

    def execute_tool(self, tool: Any, **kwargs) -> Any:
        logger.info("Executing tool: %s", tool.name)
        return self.tool_executor.execute_tool(tool.code, tool.name, **kwargs)

    # ── Combined ───────────────────────────────────────────────────────

    def create_and_execute_tool(
        self,
        query: str,
        project_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        tool = self.create_tool(query, project_path)
        if not tool:
            return {"success": False, "error": "Failed to generate tool"}
        result = self.execute_tool(tool, **kwargs)
        return {
            "success": result.success,
            "tool_name": tool.name,
            "tool_description": tool.description,
            "result": result.output,
            "error": result.error,
        }

    # ── Planner Pipeline ─────────────────────────────────────────────────

    def plan_and_execute(
        self,
        goal: str,
        output_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full plan → validate → execute → review → write pipeline.

        Returns a dict with plan, results, review, and output path.
        """
        logger.info("Planning pipeline: goal=%s", goal[:80])

        plan = self.planner.plan(goal)
        is_valid, issues = self.plan_validator.validate_with_llm(plan, goal)
        if not is_valid:
            return {
                "success": False,
                "plan": plan,
                "validation_issues": issues,
                "error": "Plan validation failed",
            }

        result = self.plan_executor.execute(plan)
        review = self.reviewer.review(result, goal)

        output_path = None
        if output_file:
            content = self._format_output(result, review)
            output_path = self.writer.write(content, output_file)

        return {
            "success": len(result.errors) == 0,
            "plan": plan,
            "result": result,
            "review": review,
            "output_path": output_path,
        }

    def _format_output(self, result, review) -> str:
        lines = ["# Execution Results", ""]
        for sid, output in result.outputs.items():
            step = next(
                (s for s in result.plan.steps if s.id == sid), None
            )
            lines.append(f"## Step {sid}: {step.action if step else '?'}")
            lines.append(str(output))
            lines.append("")
        if result.errors:
            lines.append("## Errors")
            for sid, err in result.errors.items():
                lines.append(f"Step {sid}: {err}")
        if review:
            lines.append("## Review")
            lines.append(f"Passed: {review.passed}")
            lines.append(f"Score: {review.score}")
            lines.append(f"Feedback: {review.feedback}")
        return "\n".join(lines)

    # ── Tool Fixer ───────────────────────────────────────────────────────

    def fix_tool(
        self, file_path: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Read, test, and fix a saved tool file using the LLM."""
        logger.info("Fixing tool: %s", file_path)
        return self.tool_fixer.fix_tool_file(file_path, **kwargs)

    # ── Async API ──────────────────────────────────────────────────────

    async def async_create_tool(
        self, query: str, project_path: Optional[str] = None
    ) -> Optional[Any]:
        logger.info("Async creating tool: query=%s", query[:80])
        project_info = self._get_project_info(project_path)
        tool = self.tool_generator.generate_tool(query, project_info)
        if tool and self.config.output_dir:
            self.tool_generator.save_tool(tool, self.config.output_dir)
        return tool

    async def async_execute_tool(self, tool: Any, **kwargs) -> Any:
        logger.info("Async executing tool: %s", tool.name)
        return self.tool_executor.execute_tool(tool.code, tool.name, **kwargs)

    async def async_create_and_execute_tool(
        self,
        query: str,
        project_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        tool = await self.async_create_tool(query, project_path)
        if not tool:
            return {"success": False, "error": "Failed to generate tool"}
        result = await self.async_execute_tool(tool, **kwargs)
        return {
            "success": result.success,
            "tool_name": tool.name,
            "tool_description": tool.description,
            "result": result.output,
            "error": result.error,
        }

    # ─── LLM Analysis ──────────────────────────────────────────────────

    def analyze_with_llm(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        return self.llm_provider.analyze_project(project_info)

    async def async_analyze_with_llm(
        self, project_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.llm_provider.async_analyze_project(project_info)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_project_info(self, project_path: Optional[str] = None) -> Dict[str, Any]:
        path = project_path or self.config.default_project_path
        if path != self.config.default_project_path:
            scanner = ProjectScanner(path)
            return scanner.scan()
        return self.project_scanner.scan()

    def list_available_tools(self, project_path: Optional[str] = None) -> List[str]:
        project_info = self._get_project_info(project_path)
        tools = self.tool_generator.generate_from_project(project_info)
        return [tool.name for tool in tools]

    def set_project_path(self, project_path: str) -> None:
        self.config.default_project_path = project_path
        self.project_scanner = ProjectScanner(project_path)
        self.tool_generator.project_scanner = self.project_scanner

    def set_output_dir(self, output_dir: str) -> None:
        self.config.output_dir = output_dir
        self.file_config.output_dir = output_dir
        # Persist to DB (primary config store)
        try:
            from tool_maker.db.models import set_config
            set_config("output_dir", output_dir)
        except Exception:
            pass

    def add_whitelist(self, *modules: str) -> bool:
        """Add modules to the sandbox whitelist (persisted to config file)."""
        added = self.file_config.add_whitelist(*modules)
        if added:
            self.tool_executor.extra_whitelist = list(self.file_config.extra_whitelist)
        return added

    def clear_cache(self) -> None:
        self.tool_executor.clear_history()
        self.llm_provider.clear_history()

    def _merge_db_config(self) -> None:
        """Merge DB-saved config into in-memory config.

        Precedence: constructor args > DB config > code defaults.
        DB values only apply when the user didn't explicitly pass them
        to the constructor.
        """
        try:
            from tool_maker.db.models import all_config
            db = all_config()
            # Apply DB values to config (but only if not explicitly passed
            # to the constructor)
            if db.get("output_dir") and "output_dir" not in self._explicit_config:
                self.config.output_dir = db["output_dir"]
            # Also keep file_config in sync for backward compat
            if db.get("output_dir"):
                self.file_config.output_dir = db["output_dir"]
            if db.get("extra_whitelist"):
                extra = [
                    m.strip()
                    for m in db["extra_whitelist"].split(",")
                    if m.strip()
                ]
                for m in extra:
                    if m not in self.file_config.extra_whitelist:
                        self.file_config.extra_whitelist.append(m)
            if db.get("approved_deps"):
                extra = [
                    m.strip()
                    for m in db["approved_deps"].split(",")
                    if m.strip()
                ]
                for m in extra:
                    if m not in self.file_config.approved_deps:
                        self.file_config.approved_deps.append(m)
            if db.get("auto_approve_deps") == "true":
                self.file_config.auto_approve_deps = True
            if db.get("model") and "model" not in self._explicit_config:
                self.config.model = db["model"]
            if db.get("llm_base_url") and "ollama_base_url" not in \
                    self._explicit_config:
                self.config.ollama_base_url = db["llm_base_url"]
            if db.get("db_dsn"):
                os.environ.setdefault("TOOLMAKER_DB_DSN", db["db_dsn"])
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Could not load DB config: %s", e)


# ── Factory Functions ────────────────────────────────────────────────────


def create_tool_maker(
    llm_provider: str = "ollama",
    api_key: Optional[str] = None,
    model: str = "gemma4:31b-cloud",
    default_project_path: str = ".",
    output_dir: str = "./generated_tools",
    ollama_base_url: str = "http://localhost:11434",
) -> ToolMaker:
    config = ToolMakerConfig(
        llm_provider=llm_provider,
        api_key=api_key,
        model=model,
        default_project_path=default_project_path,
        output_dir=output_dir,
        ollama_base_url=ollama_base_url,
    )
    return ToolMaker(config)


def create_tool_maker_from_env() -> ToolMaker:
    llm_provider = os.environ.get("TOOL_MAKER_LLM_PROVIDER", "ollama")
    api_key = os.environ.get("TOOL_MAKER_API_KEY")
    model = os.environ.get("TOOL_MAKER_MODEL", "gemma4:31b-cloud")
    project_path = os.environ.get("TOOL_MAKER_PROJECT_PATH", ".")
    output_dir = os.environ.get("TOOL_MAKER_OUTPUT_DIR", "./generated_tools")
    ollama_base_url = os.environ.get(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    )
    return create_tool_maker(
        llm_provider=llm_provider,
        api_key=api_key,
        model=model,
        default_project_path=project_path,
        output_dir=output_dir,
        ollama_base_url=ollama_base_url,
    )
