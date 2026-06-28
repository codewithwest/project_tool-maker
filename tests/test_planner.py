"""Tests for the planner module components."""

import json

from tool_maker.planner import (
    Plan,
    PlanExecutor,
    Planner,
    PlanResult,
    PlanStep,
    PlanValidator,
    ResultReviewer,
    WriterToFile,
)
from tool_maker.planner.models import PlanStatus, StepStatus


# ── Planner ────────────────────────────────────────────────────────────────


def test_planner_without_provider_returns_fallback():
    p = Planner()
    plan = p.plan("do something")
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "implement"


def test_planner_parses_json_response():
    class FakeProvider:
        @staticmethod
        def generate(prompt, **kw):
            return json.dumps({
                "steps": [
                    {"id": 1, "action": "fetch", "input_description": "get data",
                     "expected_output": "raw data", "dependencies": []},
                    {"id": 2, "action": "process", "input_description": "clean data",
                     "expected_output": "clean data", "dependencies": [1]},
                ]
            })

    p = Planner(llm_provider=FakeProvider())
    plan = p.plan("fetch and process data")
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "fetch"
    assert plan.steps[1].dependencies == [1]


def test_planner_handles_invalid_json():
    class FakeProvider:
        @staticmethod
        def generate(prompt, **kw):
            return "not json"

    p = Planner(llm_provider=FakeProvider())
    plan = p.plan("do something")
    assert len(plan.steps) == 1  # falls back


# ── PlanValidator ──────────────────────────────────────────────────────────


def test_validator_empty_plan():
    v = PlanValidator()
    plan = Plan(goal="test", steps=[])
    valid, errors = v.validate(plan)
    assert valid
    assert errors == []


def test_validator_valid_plan():
    v = PlanValidator()
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="fetch", input_description="get data",
                 expected_output="data"),
        PlanStep(id=2, action="process", input_description="clean",
                 expected_output="done", dependencies=[1]),
    ])
    valid, errors = v.validate(plan)
    assert valid


def test_validator_missing_action():
    v = PlanValidator()
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="", input_description="x", expected_output="y"),
    ])
    valid, errors = v.validate(plan)
    assert not valid
    assert any("missing action" in e for e in errors)


def test_validator_bad_dependency():
    v = PlanValidator()
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="a", input_description="x", expected_output="y",
                 dependencies=[99]),
    ])
    valid, errors = v.validate(plan)
    assert not valid
    assert any("non-existent" in e for e in errors)


def test_validator_cycle():
    v = PlanValidator()
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="a", input_description="x",
                 expected_output="y", dependencies=[2]),
        PlanStep(id=2, action="b", input_description="x",
                 expected_output="y", dependencies=[1]),
    ])
    valid, errors = v.validate(plan)
    assert not valid
    assert any("Circular" in e for e in errors)


# ── PlanExecutor ───────────────────────────────────────────────────────────


def test_executor_topological_order():
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="first", input_description="s1",
                 expected_output="o1"),
        PlanStep(id=2, action="second", input_description="s2",
                 expected_output="o2", dependencies=[1]),
        PlanStep(id=3, action="third", input_description="s3",
                 expected_output="o3", dependencies=[1, 2]),
    ])
    ex = PlanExecutor()
    ex.execute(plan)
    ordered = ex._resolve_order(plan)
    assert ordered == [1, 2, 3]
    assert plan.status == PlanStatus.COMPLETED


def test_executor_without_provider_returns_placeholder():
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="do_stuff", input_description="in",
                 expected_output="out"),
    ])
    ex = PlanExecutor()
    result = ex.execute(plan)
    assert 1 in result.outputs
    assert "do_stuff" in result.outputs[1]


# ── ResultReviewer ─────────────────────────────────────────────────────────


def test_reviewer_without_provider():
    r = ResultReviewer()
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="do", input_description="x",
                 expected_output="y", status=StepStatus.SUCCESS),
    ])
    result = PlanResult(plan=plan, outputs={1: "ok"})
    review = r.review(result, "test")
    assert review.passed is True


def test_reviewer_with_provider():
    class FakeProvider:
        @staticmethod
        def generate(prompt, **kw):
            return json.dumps({"passed": True, "score": 0.9,
                               "feedback": "good job"})

    r = ResultReviewer(llm_provider=FakeProvider())
    plan = Plan(goal="test", steps=[
        PlanStep(id=1, action="do", input_description="x",
                 expected_output="y", status=StepStatus.SUCCESS),
    ])
    result = PlanResult(plan=plan, outputs={1: "ok"})
    review = r.review(result, "test")
    assert review.passed is True
    assert review.score == 0.9


# ── WriterToFile ───────────────────────────────────────────────────────────


def test_writer_writes_file(tmp_path):
    w = WriterToFile(output_dir=str(tmp_path))
    path = w.write("hello world", "test.txt")
    assert (tmp_path / "test.txt").read_text() == "hello world"
    assert path.endswith("test.txt")


def test_writer_creates_directory(tmp_path):
    sub = tmp_path / "nested" / "dir"
    w = WriterToFile(output_dir=str(sub))
    w.write("content", "out.txt")
    assert sub.exists()
    assert (sub / "out.txt").read_text() == "content"
