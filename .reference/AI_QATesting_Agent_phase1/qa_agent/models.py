from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4


class TestSuite(StrEnum):
    SMOKE = "smoke"
    API = "api"
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    REGRESSION = "regression"
    ACCESSIBILITY = "accessibility"
    VISUAL = "visual"
    SECURITY_BASELINE = "security_baseline"


class TargetMode(StrEnum):
    URL = "url"
    REPOSITORY = "repository"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


TestKind = Literal["api", "ui"]
TestStatus = Literal["passed", "failed", "skipped", "error"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TestCase:
    id: str
    name: str
    suite: TestSuite
    kind: TestKind
    target: str
    method: str = "GET"
    expected_status: int = 200
    expected_text: str | None = None
    priority: Priority = Priority.MEDIUM
    tags: list[str] = field(default_factory=list)
    execution_adapter: str = ""

    def __post_init__(self) -> None:
        self.suite = TestSuite(self.suite)
        self.priority = Priority(self.priority)
        self.method = self.method.upper()
        if self.method not in {"GET", "HEAD"}:
            raise ValueError("Only safe GET and HEAD test methods are supported in Phase 1.")
        if self.kind not in {"api", "ui"}:
            raise ValueError("Test kind must be 'api' or 'ui'.")
        if not self.id.strip():
            raise ValueError("Test case id cannot be empty.")
        if not self.target.startswith("/"):
            raise ValueError("Test case target must be a relative path beginning with '/'.")
        if not self.execution_adapter:
            self.execution_adapter = "api" if self.kind == "api" else "ui"


@dataclass(slots=True)
class TargetSite:
    name: str
    base_url: str
    api_endpoints: list[str] = field(default_factory=list)
    ui_paths: list[str] = field(default_factory=lambda: ["/"])
    test_cases: list[TestCase] = field(default_factory=list)
    authorized: bool = False
    environment: str = "demo"


@dataclass(slots=True)
class RunRequest:
    target_mode: TargetMode
    selected_suites: list[TestSuite]
    environment: str = "demo"
    browser: str = "chromium"
    fail_fast: bool = False
    dry_run: bool = False

    def __post_init__(self) -> None:
        self.target_mode = TargetMode(self.target_mode)
        self.selected_suites = [TestSuite(suite) for suite in self.selected_suites]
        if not self.selected_suites:
            raise ValueError("Select at least one test suite.")
        if len(set(self.selected_suites)) != len(self.selected_suites):
            raise ValueError("Selected test suites must not contain duplicates.")
        if self.environment not in {"local", "demo", "staging"}:
            raise ValueError("Environment must be one of: local, demo, staging.")


@dataclass(slots=True)
class ExcludedTest:
    test_case: TestCase
    reason: str


@dataclass(slots=True)
class TestPlan:
    target_name: str
    target_mode: TargetMode
    environment: str
    selected_suites: list[TestSuite]
    included_tests: list[TestCase]
    excluded_tests: list[ExcludedTest]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TestResult:
    test_case: TestCase
    status: TestStatus
    duration_ms: int
    logs: list[str]
    error: str | None = None
    response_status: int | None = None


@dataclass(slots=True)
class Report:
    id: str
    site_name: str
    created_at: str
    selected_suites: list[TestSuite]
    plan: TestPlan
    results: list[TestResult]
    html_path: str | None = None

    @classmethod
    def create(cls, site_name: str, plan: TestPlan, results: list[TestResult]) -> "Report":
        return cls(
            id=str(uuid4()),
            site_name=site_name,
            created_at=utc_now(),
            selected_suites=list(plan.selected_suites),
            plan=plan,
            results=results,
        )


@dataclass(slots=True)
class RunOutcome:
    plan: TestPlan
    report: Report | None


def to_dict(value: Any) -> dict[str, Any]:
    """Convert a project model into a JSON-compatible dictionary."""
    return asdict(value)
