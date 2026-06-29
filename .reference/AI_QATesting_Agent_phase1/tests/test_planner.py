from __future__ import annotations

import pytest

from qa_agent.models import RunRequest, TargetMode, TargetSite, TestCase, TestSuite
from qa_agent.planner import PlanError, create_plan


def _target() -> TargetSite:
    return TargetSite(
        name="Demo",
        base_url="https://example.com",
        authorized=True,
        test_cases=[
            TestCase("smoke-home", "Home loads", TestSuite.SMOKE, "ui", "/"),
            TestCase("api-health", "Health API", TestSuite.API, "api", "/api/health"),
        ],
    )


def test_smoke_plan_includes_only_smoke_cases() -> None:
    target = _target()
    request = RunRequest(TargetMode.URL, [TestSuite.SMOKE])

    plan = create_plan(target, request, target.test_cases)

    assert [case.id for case in plan.included_tests] == ["smoke-home"]
    assert [(item.test_case.id, item.reason) for item in plan.excluded_tests] == [
        ("api-health", "suite not selected: api")
    ]


def test_unit_suite_is_rejected_for_url_targets() -> None:
    with pytest.raises(PlanError, match="requires target_mode='repository'"):
        create_plan(_target(), RunRequest(TargetMode.URL, [TestSuite.UNIT]), _target().test_cases)


def test_modeled_suite_is_rejected_until_adapter_exists() -> None:
    with pytest.raises(PlanError, match="not implemented in Phase 1"):
        create_plan(_target(), RunRequest(TargetMode.URL, [TestSuite.E2E]), _target().test_cases)
