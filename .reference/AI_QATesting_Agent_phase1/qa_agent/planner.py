from __future__ import annotations

from qa_agent.models import ExcludedTest, RunRequest, TargetMode, TargetSite, TestCase, TestPlan, TestSuite


class PlanError(ValueError):
    """Raised when a requested test plan cannot safely be executed."""


SUPPORTED_PHASE_ONE_SUITES = frozenset({TestSuite.SMOKE, TestSuite.API})


def create_plan(target: TargetSite, request: RunRequest, test_cases: list[TestCase]) -> TestPlan:
    _validate_request(request)

    included: list[TestCase] = []
    excluded: list[ExcludedTest] = []
    for test_case in test_cases:
        if test_case.suite in request.selected_suites:
            included.append(test_case)
        else:
            excluded.append(
                ExcludedTest(
                    test_case=test_case,
                    reason=f"suite not selected: {test_case.suite.value}",
                )
            )

    if not included:
        raise PlanError(
            "No test cases match the selected suite(s). Add matching tests or choose another supported suite."
        )

    return TestPlan(
        target_name=target.name,
        target_mode=request.target_mode,
        environment=request.environment,
        selected_suites=list(request.selected_suites),
        included_tests=included,
        excluded_tests=excluded,
    )


def _validate_request(request: RunRequest) -> None:
    selected = set(request.selected_suites)
    if TestSuite.UNIT in selected and request.target_mode is TargetMode.URL:
        raise PlanError(
            "Unit testing requires target_mode='repository'; a website URL cannot execute unit tests."
        )

    unsupported = selected - SUPPORTED_PHASE_ONE_SUITES
    if unsupported:
        names = ", ".join(sorted(suite.value for suite in unsupported))
        raise PlanError(
            f"The requested suite(s) are modeled but not implemented in Phase 1: {names}. "
            "Currently executable suites: smoke, api."
        )

    if request.target_mode is not TargetMode.URL:
        raise PlanError("Repository mode is modeled but is not executable in Phase 1.")
