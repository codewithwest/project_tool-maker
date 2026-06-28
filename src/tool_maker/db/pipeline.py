"""Full pipeline: analyse → plan → implement (+test) → test → review → finalize.

All results persisted to PostgreSQL. Every step logged in detail for the UI log stream.

The implement stage generates both the implementation function and a test function
named ``test_{{name}}()``. The test stage executes the test function against the
implementation so failures propagate as proper assertion errors.
"""

import json
import logging
from typing import Any, Dict, Optional

from tool_maker.analyzer.project_scanner import ProjectScanner
from tool_maker.planner import PlanExecutor, Planner, PlanValidator, ResultReviewer
from tool_maker.planner.writer import WriterToFile
from tool_maker.tool.executor import ToolExecutor
from tool_maker.tool.generator import ToolGenerator

from . import models as db

logger = logging.getLogger(__name__)
log = logger  # convenience alias


class DBPipeline:
    """Orchestrates the full tool-making pipeline with DB persistence.

    Flow: analyse → plan → validate plan → implement → test → review → finalize
    """

    def __init__(
        self,
        llm_provider=None,
        project_scanner: Optional[ProjectScanner] = None,
        output_dir: str = "./generated_tools",
    ):
        self.llm_provider = llm_provider
        self.scanner = project_scanner or ProjectScanner(".")
        self.tool_generator = ToolGenerator(self.scanner)
        self.tool_executor = ToolExecutor()
        self.planner = Planner(llm_provider=llm_provider)
        self.plan_validator = PlanValidator(llm_provider=llm_provider)
        self.plan_executor = PlanExecutor(
            tool_generator=self.tool_generator,
            llm_provider=llm_provider,
        )
        self.reviewer = ResultReviewer(llm_provider=llm_provider)
        self.writer = WriterToFile(output_dir=output_dir)
        self.output_dir = output_dir

    def run(self, goal: str, project_path: str = ".") -> Dict[str, Any]:
        """Execute the full pipeline.

        Returns a dict with every stage's output plus the final tool_id.
        """
        stages = {}

        # ── 1. Analyse ──────────────────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 1/6: ANALYSE PROJECT                            ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("Scanning project at: %s", project_path)
        scanner = ProjectScanner(project_path)
        project_info = scanner.scan()
        name = project_info.get("name", project_path)
        files = project_info.get("files", [])
        deps = project_info.get("dependencies", [])
        log.info("Project name: %s", name)
        log.info("Files found:  %d", len(files))
        log.info("Dependencies: %d", len(deps))
        for f in files:
            log.info("  File: %s", f)
        if deps:
            log.info("  Deps: %s", ", ".join(deps))
        stages["analysis"] = name

        # ── 2. Plan ────────────────────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 2/6: PLAN                                       ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("Goal: %s", goal)
        log.info("Sending to LLM for plan generation...")
        plan = self.planner.plan(goal, context=project_info)
        log.info("Plan received with %d step(s)", len(plan.steps))
        plan_id = db.create_plan(goal)
        db.update_plan_status(plan_id, "running")
        for i, step in enumerate(plan.steps):
            log.info("  Step %d: %s", step.id, step.action)
            log.info("    Input:  %s", step.input_description)
            log.info("    Output: %s", step.expected_output)
            log.info("    Deps:   %s", step.dependencies)
            db.save_plan_step(
                plan_id, i + 1, step.action,
                input_desc=step.input_description,
                expected_output=step.expected_output,
                dep_ids=step.dependencies,
            )
        stages["plan_id"] = plan_id
        stages["plan"] = {"goal": goal, "steps": [s.action for s in plan.steps]}

        # ── 3. Validate ─────────────────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 3/6: VALIDATE PLAN                              ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("Validating plan structure and completeness...")
        is_valid, issues = self.plan_validator.validate_with_llm(plan, goal)
        log.info("Valid: %s", is_valid)
        if issues:
            log.info("Issues:")
            for iss in issues:
                log.info("  - %s", iss)
        if not is_valid:
            db.update_plan_status(plan_id, "failed")
            log.error("Plan validation FAILED — aborting pipeline")
            return {**stages, "success": False, "error": f"Plan invalid: {issues}"}
        db.update_plan_status(plan_id, "validated")
        stages["validation"] = {"valid": is_valid, "issues": issues}

        # ── 4. Implement ────────────────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 4/6: IMPLEMENT (+ TEST)                         ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("Generating tool code via LLM...")
        tool_code = ""
        tool_name = ""
        for step in plan.steps:
            log.info("Implementing step %d: %s", step.id, step.action)
            prompt = (
                f"Generate Python code for this step.\n"
                f"Action: {step.action}\n"
                f"Input: {step.input_description}\n"
                f"Expected output: {step.expected_output}\n"
                f"Project context: {json.dumps(project_info, indent=2)[:500]}\n"
                f"\n"
                f"The code MUST contain:\n"
                f"1. An implementation function with strict Python type annotations\n"
                f"   for ALL parameters and the return value.\n"
                f"2. A test function named ``test_IMPLEMENTATION_NAME()``\n"
                f"   where IMPLEMENTATION_NAME is the exact name of the\n"
                f"   implementation function from (1). The test function\n"
                f"   must call the implementation with sample inputs and\n"
                f"   assert the result matches the expected output.\n"
                f"\n"
                f"Return ONLY the code in a single ```python ... ``` block."
            )
            log.info("Prompt for step %d (%d chars)", step.id, len(prompt))
            response = self.llm_provider.generate(prompt)
            code = self._extract_code(response)
            if code:
                tool_code = code
                tool_name = self._extract_name(code) or "generated_tool"
                test_func_name = f"test_{tool_name}"
                log.info("Code extracted: function '%s' (%d chars)",
                         tool_name, len(code))
                log.info("── GENERATED CODE ────────────────────────────────")
                for line in code.splitlines():
                    log.info("  %s", line)
                log.info("──────────────────────────────────────────────────")
                # Log whether a test function was detected
                if test_func_name in code:
                    log.info("Test function '%s' found in generated code",
                             test_func_name)
                else:
                    log.warning("No test function '%s' found — test stage will fail",
                                test_func_name)
                break
            else:
                log.warning("No code found in LLM response for step %d", step.id)

        if not tool_code:
            log.error("IMPLEMENTATION FAILED — no code produced")
            return {**stages, "success": False,
                    "error": "Implementation stage produced no code"}

        tool_id = db.save_tool(
            name=tool_name,
            code=tool_code,
            description=goal,
            plan_id=plan_id,
        )
        log.info("Tool saved to DB: id=%d name='%s'", tool_id, tool_name)
        stages["tool_id"] = tool_id
        stages["tool_name"] = tool_name

        # ── 5. Test (+ auto-fix loop) ─────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 5/6: TEST (+ AUTO-FIX)                          ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        test_func_name = f"test_{tool_name}"
        current_code = tool_code
        test_passed = False
        fix_attempts = 0
        last_error = ""

        from tool_maker.tool_fixer import ToolFixer
        fixer = ToolFixer(
            llm_provider=self.llm_provider,
            executor=self.tool_executor,
            max_fix_attempts=3,
        )

        while fix_attempts <= 3 and not test_passed:
            if fix_attempts > 0:
                log.info("── Fix attempt %d/3 ─────────────────────", fix_attempts)
                fix_result = fixer.fix_tool_code(current_code, tool_name)
                if fix_result.get("fixed"):
                    current_code = fix_result["code"]
                    # Update the tool code in DB
                    db.save_tool(
                        name=tool_name, code=current_code,
                        description=goal, plan_id=plan_id,
                    )
                    log.info("Fix %d succeeded, re-running tests...", fix_attempts)
                else:
                    last_error = fix_result.get("error", "fix failed")
                    log.warning("Fix attempt %d failed: %s", fix_attempts,
                                last_error)
                    break

            log.info("Running test '%s' in sandbox...", test_func_name)
            try:
                result = self.tool_executor.execute_tool(
                    current_code, test_func_name)

                # Fallback: if test_{name} not found, try alternatives
                err_msg = (result.error or "").lower()
                if not result.success and "fn not found" in err_msg:
                    for alt in ["test_implement",
                                f"test_{tool_name}_test"]:
                        log.info("Trying fallback test: '%s'", alt)
                        result = self.tool_executor.execute_tool(
                            current_code, alt)
                        alt_err = (result.error or "").lower()
                        if result.success or "fn not found" not in alt_err:
                            test_func_name = alt
                            break

                test_passed = result.success
                log.info("Test success: %s", test_passed)
                log.info("── TEST OUTPUT ───────────────────────────────────────")
                out = str(result.output) if test_passed else ""
                err = result.error or ""
                if out:
                    for line in out.splitlines():
                        log.info("  %s", line)
                if err:
                    log.error("  ERROR: %s", err)
                log.info("──────────────────────────────────────────────────────")
                last_error = err

                if not test_passed and fix_attempts == 0:
                    # Try the implementation function directly as a fallback
                    log.info("Test failed — trying implementation directly...")
                    impl_result = self.tool_executor.execute_tool(
                        current_code, tool_name)
                    if impl_result.success:
                        log.info("Implementation runs — test may need fixing")
                    else:
                        log.warning("Implementation also failed: %s",
                                    impl_result.error)
                        last_error = impl_result.error

            except Exception as e:
                log.error("TEST EXCEPTION: %s", e)
                last_error = str(e)
                if fix_attempts >= 3:
                    break

            fix_attempts += 1

        # Record final test result
        tool_code = current_code
        db.save_tool(
            name=tool_name, code=tool_code,
            description=goal, plan_id=plan_id,
        )
        db.record_execution(
            tool_id=tool_id, success=test_passed,
            output=out if test_passed else "",
            error=last_error, plan_id=plan_id,
        )
        stages["test"] = {"success": test_passed,
                          "output": (out[:500] if test_passed else last_error[:500])}
        stages["fix_attempts"] = fix_attempts - 1 if fix_attempts > 0 else 0

        # ── 6. Review ──────────────────────────────────────────────────
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  STAGE 6/6: REVIEW                                     ║")
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("Submitting results for LLM review...")
        review = self.reviewer.review(
            type("PlanResult", (), {"plan": plan, "outputs": {
                i: stages.get("test", {}).get("output", "")
                for i, _ in enumerate(plan.steps, 1)
            }, "errors": {}})(),
            goal,
        )
        log.info("Review: passed=%s  score=%.2f", review.passed, review.score)
        log.info("Feedback: %s", review.feedback[:500])
        db.save_review(
            tool_id=tool_id, passed=review.passed,
            score=review.score, feedback=review.feedback,
        )
        stages["review"] = {"passed": review.passed,
                            "score": review.score,
                            "feedback": review.feedback[:500]}

        # ── Finalize ───────────────────────────────────────────────────
        final_status = "final" if review.passed else "needs_fix"
        db.update_tool_status(tool_id, final_status)

        # Save tool to output directory
        file_path = self.writer.write(tool_code, f"{tool_name}.py")
        log.info("Tool saved to file: %s", file_path)

        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║  PIPELINE COMPLETE                                     ║")
        log.info("║  Output: %s", file_path.ljust(34))
        log.info("║  Tool:   %s (id=%d)", tool_name.ljust(22), tool_id)
        log.info("║  Status: %s", final_status.ljust(25))
        log.info("╚══════════════════════════════════════════════════════════╝")

        stages["success"] = True
        stages["final_status"] = final_status
        stages["file_path"] = file_path
        return stages

    def _extract_code(self, response: str) -> str:
        import re
        m = re.search(r"```python\s*\n(.*?)\n```", response, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_name(self, code: str) -> str:
        import re
        m = re.search(r"def\s+(\w+)\s*\(", code)
        return m.group(1) if m else ""
