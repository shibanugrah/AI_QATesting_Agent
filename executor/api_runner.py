from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from qa_agent.logging_utils import get_logger
from qa_agent.models import TargetSite, TestCase, TestResult

logger = get_logger(__name__)


class ApiRunner:
    def run(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        logs = [f"API request: {test_case.method} {test_case.target}"]
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")

        try:
            request = Request(url, method=test_case.method)
            with urlopen(request, timeout=15) as response:
                status = response.status
                body = response.read().decode("utf-8", errors="replace")

            passed = status == test_case.expected_status
            if test_case.expected_text:
                passed = passed and test_case.expected_text in body
            logs.append(f"Response status: {status}")
            return TestResult(
                test_case=test_case,
                status="passed" if passed else "failed",
                duration_ms=self._elapsed_ms(started),
                logs=logs,
                response_status=status,
                error=None if passed else "Response did not match expectation",
            )
        except HTTPError as exc:
            logs.append(f"HTTP error: {exc.code}")
            return TestResult(
                test_case=test_case,
                status="failed",
                duration_ms=self._elapsed_ms(started),
                logs=logs,
                response_status=exc.code,
                error=str(exc),
            )
        except URLError as exc:
            logger.exception("API test errored for %s", url)
            logs.append(f"Network error: {exc.reason}")
            return TestResult(
                test_case=test_case,
                status="error",
                duration_ms=self._elapsed_ms(started),
                logs=logs,
                error=str(exc.reason),
            )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

