"""
PlanValidator - Validates a plan for correctness, completeness, and consistency.
"""

import logging

from .models import Plan, PlanStatus

logger = logging.getLogger(__name__)


class PlanValidator:
    """Validates a plan's structure and dependencies."""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def validate(self, plan: Plan) -> tuple:
        """Validate plan structure. Returns (is_valid, errors).

        Checks:
        - All step IDs are unique
        - All dependency references point to existing steps
        - No circular dependencies
        - Each step has action and input_description
        """
        errors = []

        ids = {s.id for s in plan.steps}
        if len(ids) != len(plan.steps):
            errors.append("Duplicate step IDs")

        for s in plan.steps:
            if not s.action.strip():
                errors.append(f"Step {s.id}: missing action")
            if not s.input_description.strip():
                errors.append(f"Step {s.id}: missing input_description")
            for dep in s.dependencies:
                if dep not in ids:
                    errors.append(
                        f"Step {s.id}: depends on non-existent step {dep}"
                    )

        if self._has_cycle(plan):
            errors.append("Circular dependency detected")

        is_valid = len(errors) == 0
        if is_valid:
            plan.status = PlanStatus.VALIDATED
        return is_valid, errors

    def _has_cycle(self, plan: Plan) -> bool:
        visited = set()
        rec_stack = set()

        def dfs(sid):
            if sid in rec_stack:
                return True
            if sid in visited:
                return False
            visited.add(sid)
            rec_stack.add(sid)
            step = next((s for s in plan.steps if s.id == sid), None)
            if step:
                for dep in step.dependencies:
                    if dfs(dep):
                        return True
            rec_stack.discard(sid)
            return False

        for s in plan.steps:
            if dfs(s.id):
                return True
        return False

    def validate_with_llm(self, plan: Plan, goal: str) -> tuple:
        """Use LLM to validate the plan against the original goal."""
        if self.llm_provider is None:
            return self.validate(plan)

        prompt = (
            f"Original goal: {goal}\n\n"
            f"Plan:\n"
        )
        for s in plan.steps:
            prompt += (
                f"  Step {s.id}: {s.action}\n"
                f"    Input: {s.input_description}\n"
                f"    Expected: {s.expected_output}\n"
                f"    Depends on: {s.dependencies}\n"
            )
        prompt += (
            "\nIs this plan complete and correct for achieving the goal?\n"
            "Answer with a single JSON object: "
            '{"valid": true/false, "issues": ["issue1", ...]}'
        )

        try:
            response = self.llm_provider.generate(prompt)
            import json
            data = json.loads(response)
            is_valid = data.get("valid", False)
            issues = data.get("issues", [])
            if is_valid:
                plan.status = PlanStatus.VALIDATED
            return is_valid, issues
        except Exception as e:
            logger.warning("LLM validation failed: %s", e)
            return self.validate(plan)
