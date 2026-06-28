"""
PlanExecutor - Executes a plan step by step, handling dependencies and passing outputs.
"""

import logging
from typing import Any, Dict, Optional

from .models import Plan, PlanResult, PlanStatus, StepStatus

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Executes each step of a plan, resolving dependency order."""

    def __init__(self, tool_generator=None, llm_provider=None):
        self.tool_generator = tool_generator
        self.llm_provider = llm_provider

    def execute(
        self, plan: Plan, context: Optional[Dict[str, Any]] = None
    ) -> PlanResult:
        plan.status = PlanStatus.RUNNING
        ordered = self._resolve_order(plan)
        outputs: Dict[int, Any] = {}
        errors: Dict[int, str] = {}

        for sid in ordered:
            step = next(s for s in plan.steps if s.id == sid)
            step.status = StepStatus.RUNNING
            logger.info("Executing step %d: %s", sid, step.action)

            deps_output = {d: outputs[d] for d in step.dependencies if d in outputs}

            try:
                result = self._execute_step(step, deps_output, context)
                step.status = StepStatus.SUCCESS
                step.result = result
                outputs[sid] = result
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                errors[sid] = str(e)
                logger.error("Step %d failed: %s", sid, e)

        final_status = (
            PlanStatus.COMPLETED if not errors else PlanStatus.FAILED
        )
        plan.status = final_status
        return PlanResult(plan=plan, outputs=outputs, errors=errors)

    def _resolve_order(self, plan: Plan) -> list:
        """Topological sort of step IDs."""
        visited = set()
        ordered = []

        def dfs(sid):
            if sid in visited:
                return
            visited.add(sid)
            step = next((s for s in plan.steps if s.id == sid), None)
            if step:
                for dep in step.dependencies:
                    dfs(dep)
                ordered.append(sid)

        for s in plan.steps:
            dfs(s.id)
        return ordered

    def _execute_step(self, step, deps_outputs: dict, context: dict = None) -> Any:
        if self.tool_generator and self.llm_provider:
            prompt = (
                f"Implement the following step:\n"
                f"Action: {step.action}\n"
                f"Input: {step.input_description}\n"
                f"Expected output: {step.expected_output}\n"
            )
            if deps_outputs:
                prompt += f"Available dependency outputs:\n{deps_outputs}\n"
            if context:
                prompt += f"Context:\n{context}\n"
            prompt += "\nReturn the implementation result or generated code."

            return self.llm_provider.generate(prompt)

        return f"Step {step.id} ({step.action}) executed with inputs: {deps_outputs}"
