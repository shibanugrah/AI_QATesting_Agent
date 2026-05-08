from __future__ import annotations

import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from qa_agent.logging_utils import get_logger
from qa_agent.models import TargetSite, TestCase, TestResult

logger = get_logger(__name__)


class SeleniumRunner:
    """Runs basic UI checks.

    Selenium is optional for this scaffold. If it is installed, this class can be
    extended to drive a real browser. The MVP performs a page-load check so the
    full flow remains runnable on a fresh machine.
    """

    def run(self, target: TargetSite, test_case: TestCase) -> TestResult:
        if os.getenv("QA_AGENT_REAL_SELENIUM") == "1":
            return self._run_with_selenium(target, test_case)
        return self._run_page_load_check(target, test_case)

    def _run_with_selenium(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        logs = [f"Selenium browser check: {test_case.target}"]
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)
            try:
                driver.get(url)
                title = driver.title
                html = driver.page_source
                passed = bool(html.strip())
                logs.append(f"Page title: {title}")
                logs.append(f"HTML bytes: {len(html)}")
                return TestResult(
                    test_case=test_case,
                    status="passed" if passed else "failed",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    logs=logs,
                    error=None if passed else "Browser loaded an empty page",
                )
            finally:
                driver.quit()
        except Exception as exc:
            logger.exception("Selenium test errored for %s", url)
            logs.append(f"Selenium error: {exc}")
            return TestResult(
                test_case=test_case,
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                error=str(exc),
            )

    def _run_page_load_check(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        logs = [f"UI page-load check: {test_case.target}"]
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")

        try:
            with urlopen(url, timeout=15) as response:
                status = response.status
                html = response.read().decode("utf-8", errors="replace")
            passed = status == test_case.expected_status and bool(html.strip())
            logs.append(f"Page status: {status}")
            logs.append(f"HTML bytes: {len(html)}")
            return TestResult(
                test_case=test_case,
                status="passed" if passed else "failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                response_status=status,
                error=None if passed else "Page did not load as expected",
            )
        except HTTPError as exc:
            logs.append(f"HTTP error: {exc.code}")
            return TestResult(
                test_case=test_case,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                response_status=exc.code,
                error=str(exc),
            )
        except URLError as exc:
            logger.exception("UI test errored for %s", url)
            logs.append(f"Network error: {exc.reason}")
            return TestResult(
                test_case=test_case,
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                error=str(exc.reason),
            )
