"""
Planner - Breaks a user request into a step-by-step plan using an LLM.
"""

import json
import logging
from typing import Any, Dict, Optional

from .models import Plan, PlanStep

logger = logging.getLogger(__name__)

_PLANNER_PROMPT = (
    "You are a planner. Given a user's goal, break it into a sequence of "
    "concrete, executable steps.\n\n"
    "Return ONLY valid JSON with this structure:\n"
    "{\n"
    '  "steps": [\n'
    "    {\n"
    '      "id": 1,\n'
    '      "action": "brief action name like \'generate_code\' or '
    "\'fetch_data'\",\n"
    '      "input_description": "what input this step needs",\n'
    '      "expected_output": "what this step should produce",\n'
    '      "dependencies": []\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Each step must be self-contained and actionable.\n"
    "- Use dependency IDs to order steps (a step runs after all "
    "its dependencies finish).\n"
    "- First steps should have empty dependencies.\n"
    "- Keep dependencies minimal — only list IDs this step directly "
    "needs output from.\n"
    "- The plan should cover the entire goal from start to finish.\n"
    "- Do NOT include code in the plan — just descriptions of "
    "what each step does.\n"
)


class Planner:
    """Creates a step-by-step plan from a user request using an LLM."""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Plan:
        if self.llm_provider is None:
            logger.warning("No LLM provider — returning single-step fallback plan")
            return Plan(
                goal=goal,
                steps=[
                    PlanStep(
                        id=1,
                        action="implement",
                        input_description=goal,
                        expected_output="Completed implementation",
                    )
                ],
            )

        logger.info("Planning: %s", goal[:80])
        prompt = self._build_prompt(goal, context)
        try:
            response = self.llm_provider.generate(prompt)
            return self._parse_response(response, goal)
        except Exception as e:
            logger.error("Planning failed: %s", e)
            return self._fallback(goal)

    def _build_prompt(
        self, goal: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        parts = [_PLANNER_PROMPT, f"\nUser goal: {goal}"]
        if context:
            parts.append(f"\nContext: {json.dumps(context, indent=2)}")
        return "\n".join(parts)

    def _parse_response(self, response: str, goal: str) -> Plan:
        data = json.loads(response)
        if isinstance(data, dict) and "steps" in data:
            steps_data = data["steps"]
        elif isinstance(data, list):
            steps_data = data
        else:
            return self._fallback(goal)

        steps = [
            PlanStep(
                id=s.get("id", i + 1),
                action=s.get("action", "unknown"),
                input_description=s.get("input_description", ""),
                expected_output=s.get("expected_output", ""),
                dependencies=s.get("dependencies", []),
            )
            for i, s in enumerate(steps_data)
        ]
        return Plan(goal=goal, steps=steps)

    def _fallback(self, goal: str) -> Plan:
        return Plan(
            goal=goal,
            steps=[
                PlanStep(
                    id=1,
                    action="implement",
                    input_description=goal,
                    expected_output="Completed implementation",
                )
            ],
        )
