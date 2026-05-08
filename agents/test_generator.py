from __future__ import annotations

from qa_agent.logging_utils import get_logger
from qa_agent.models import TargetSite, TestCase

logger = get_logger(__name__)


class TestGenerator:
    """Generates deterministic MVP tests with a future AI hook."""

    def generate(self, target: TargetSite) -> list[TestCase]:
        logger.info("Generating tests for %s", target.name)
        tests: list[TestCase] = []

        for index, endpoint in enumerate(target.api_endpoints, start=1):
            tests.append(
                TestCase(
                    id=f"api-{index}",
                    name=f"GET {endpoint} returns 200",
                    kind="api",
                    target=endpoint,
                    method="GET",
                    expected_status=200,
                )
            )

        for index, path in enumerate(target.ui_paths, start=1):
            tests.append(
                TestCase(
                    id=f"ui-{index}",
                    name=f"Page {path} loads",
                    kind="ui",
                    target=path,
                    expected_status=200,
                )
            )

        logger.info("Generated %d tests for %s", len(tests), target.name)
        return tests

