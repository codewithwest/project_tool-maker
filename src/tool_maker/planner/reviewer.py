"""
ResultReviewer - Reviews plan execution results for quality and correctness.
"""

import json
import logging

from .models import PlanResult, Review

logger = logging.getLogger(__name__)

_REVIEW_PROMPT = (
    "You are a QA reviewer. Given a user's original goal and the "
    "execution results, evaluate whether the output meets the goal.\n\n"
    "Return ONLY a JSON object:\n"
    "{\n"
    '  "passed": true/false,\n'
    '  "score": 0.0-1.0,\n'
    '  "feedback": "detailed feedback explaining the evaluation"\n'
    "}\n\n"
    "Be honest and specific. If the output doesn't fully satisfy "
    "the goal, note what's missing.\n"
)


class ResultReviewer:
    """Reviews execution results against the original goal."""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider

    def review(self, result: PlanResult, goal: str) -> Review:
        if self.llm_provider is None:
            passed = len(result.errors) == 0
            return Review(
                passed=passed,
                feedback="No LLM provider — automated check: "
                         f"{'no errors' if passed else 'errors found'}",
                score=1.0 if passed else 0.0,
            )

        prompt = (
            f"{_REVIEW_PROMPT}\n\n"
            f"Original goal: {goal}\n\n"
            f"Execution results:\n"
        )
        for sid, output in result.outputs.items():
            step = next(
                (s for s in result.plan.steps if s.id == sid), None
            )
            prompt += (
                f"Step {sid} ({step.action if step else '?'}):\n"
                f"  Output: {str(output)[:500]}\n"
            )
        if result.errors:
            prompt += "\nErrors:\n"
            for sid, err in result.errors.items():
                prompt += f"  Step {sid}: {err}\n"

        try:
            response = self.llm_provider.generate(prompt)
            data = json.loads(response)
            return Review(
                passed=data.get("passed", False),
                feedback=data.get("feedback", ""),
                score=data.get("score", 0.0),
            )
        except Exception as e:
            logger.warning("Review failed: %s", e)
            return Review(
                passed=len(result.errors) == 0,
                feedback=f"Review error: {e}",
            )
