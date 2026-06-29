from __future__ import annotations

from qa_agent.models import TargetSite, TestCase, TestSuite


class TestGenerator:
    """Build deterministic API/UI cases. It deliberately does not claim LLM generation."""

    def generate(self, target: TargetSite) -> list[TestCase]:
        if target.test_cases:
            return list(target.test_cases)

        tests: list[TestCase] = []
        for index, endpoint in enumerate(target.api_endpoints, start=1):
            tests.append(
                TestCase(
                    id=f"api-{index}",
                    name=f"GET {endpoint} returns 200",
                    suite=TestSuite.API,
                    kind="api",
                    target=endpoint,
                    method="GET",
                    expected_status=200,
                )
            )
        for index, path in enumerate(target.ui_paths, start=1):
            tests.append(
                TestCase(
                    id=f"smoke-ui-{index}",
                    name=f"Page {path} loads",
                    suite=TestSuite.SMOKE,
                    kind="ui",
                    target=path,
                    expected_status=200,
                )
            )
        return tests
