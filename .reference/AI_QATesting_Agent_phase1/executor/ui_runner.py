from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from qa_agent.models import TargetSite, TestCase, TestResult


class UiRunner:
    """Phase-1 page availability check; browser workflows belong to a later Playwright adapter."""

    def run(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")
        logs = [f"UI availability check: {url}"]
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=15) as response:  # nosec B310: target is validated before execution
                status = response.status
                body = response.read().decode("utf-8", errors="replace")
            passed = status == test_case.expected_status
            if test_case.expected_text:
                passed = passed and test_case.expected_text in body
            logs.append(f"Response status: {status}")
            return TestResult(
                test_case=test_case,
                status="passed" if passed else "failed",
                duration_ms=_elapsed_ms(started),
                logs=logs,
                response_status=status,
                error=None if passed else "Page did not match expectation.",
            )
        except HTTPError as exc:
            logs.append(f"HTTP error: {exc.code}")
            return TestResult(
                test_case=test_case,
                status="failed",
                duration_ms=_elapsed_ms(started),
                logs=logs,
                response_status=exc.code,
                error=str(exc),
            )
        except URLError as exc:
            logs.append(f"Network error: {exc.reason}")
            return TestResult(
                test_case=test_case,
                status="error",
                duration_ms=_elapsed_ms(started),
                logs=logs,
                error=str(exc.reason),
            )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
