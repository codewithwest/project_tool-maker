"""
Shared data models for the planning system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanStep:
    id: int
    action: str
    input_description: str
    expected_output: str
    dependencies: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    plan: Plan
    outputs: Dict[int, Any] = field(default_factory=dict)
    errors: Dict[int, str] = field(default_factory=dict)
    review: Optional[str] = None
    review_passed: Optional[bool] = None


@dataclass
class Review:
    passed: bool
    feedback: str
    score: float = 0.0
