from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


TestKind = Literal["api", "ui"]
TestStatus = Literal["passed", "failed", "skipped", "error"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TargetSite:
    name: str
    base_url: str
    api_endpoints: list[str] = field(default_factory=list)
    ui_paths: list[str] = field(default_factory=lambda: ["/"])


@dataclass(slots=True)
class TestCase:
    id: str
    name: str
    kind: TestKind
    target: str
    method: str = "GET"
    expected_status: int = 200
    expected_text: str | None = None


@dataclass(slots=True)
class TestResult:
    test_case: TestCase
    status: TestStatus
    duration_ms: int
    logs: list[str]
    error: str | None = None
    response_status: int | None = None


@dataclass(slots=True)
class FailureAnalysis:
    test_id: str
    summary: str
    likely_cause: str
    recommendation: str
    similar_failures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Report:
    id: str
    site_name: str
    created_at: str
    results: list[TestResult]
    analyses: list[FailureAnalysis]
    html_path: str | None = None

    @classmethod
    def create(
        cls,
        site_name: str,
        results: list[TestResult],
        analyses: list[FailureAnalysis],
    ) -> "Report":
        return cls(
            id=str(uuid4()),
            site_name=site_name,
            created_at=utc_now(),
            results=results,
            analyses=analyses,
        )


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)

