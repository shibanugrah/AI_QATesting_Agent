from __future__ import annotations

import json
import os
import time
from pathlib import Path
from socket import timeout as SocketTimeout
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

    def __init__(
        self,
        timeout_seconds: int | None = None,
        retries: int | None = None,
        screenshot_dir: str = "artifacts/screenshots",
        headless: bool | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds or int(os.getenv("QA_AGENT_UI_TIMEOUT", "15"))
        self.retries = retries if retries is not None else int(os.getenv("QA_AGENT_UI_RETRIES", "1"))
        self.screenshot_dir = Path(screenshot_dir)
        self.headless = headless if headless is not None else os.getenv("QA_AGENT_HEADLESS", "1") != "0"

    def run(self, target: TargetSite, test_case: TestCase) -> TestResult:
        if os.getenv("QA_AGENT_REAL_SELENIUM") == "1":
            return self._run_with_selenium(target, test_case)
        return self._run_page_load_check(target, test_case)

    def _run_with_selenium(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        logs = [
            self._log_event(
                "selenium_start",
                test_id=test_case.id,
                target=test_case.target,
                timeout_seconds=self.timeout_seconds,
                retries=self.retries,
                headless=self.headless,
            )
        ]
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")

        last_error: str | None = None
        last_screenshot: str | None = None
        last_status = "error"
        for attempt in range(1, self.retries + 2):
            driver = None
            try:
                driver = self._create_driver()
                logs.append(self._log_event("selenium_attempt", attempt=attempt, url=url))
                driver.set_page_load_timeout(self.timeout_seconds)
                driver.get(url)
                self._wait_for_page_ready(driver)
                title = driver.title
                html = driver.page_source
                passed = bool(html.strip())
                logs.append(
                    self._log_event(
                        "selenium_page_loaded",
                        attempt=attempt,
                        title=title,
                        html_bytes=len(html),
                    )
                )
                if passed:
                    return self._result(test_case, "passed", started, logs)

                last_error = "Browser loaded an empty page"
                last_status = "failed"
                last_screenshot = self._capture_screenshot(driver, test_case, attempt, logs)
            except Exception as exc:
                last_error = self._format_exception(exc)
                last_status = "error"
                logger.exception("Selenium attempt %d errored for %s", attempt, url)
                logs.append(
                    self._log_event(
                        "selenium_error",
                        attempt=attempt,
                        exception_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                if driver is not None:
                    last_screenshot = self._capture_screenshot(driver, test_case, attempt, logs)
            finally:
                if driver is not None:
                    self._quit_driver(driver, logs)

            if attempt <= self.retries:
                self._sleep_before_retry(attempt, logs)

        error = self._with_screenshot(last_error or "Selenium test failed", last_screenshot)
        return self._result(test_case, last_status, started, logs, error=error)

    def _create_driver(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            return webdriver.Chrome(options=options)
        except ImportError as exc:
            raise RuntimeError("Selenium is not installed. Install selenium to enable browser UI tests.") from exc

    def _wait_for_page_ready(self, driver) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as expected
        from selenium.webdriver.support.ui import WebDriverWait

        wait = WebDriverWait(driver, self.timeout_seconds)
        wait.until(lambda active_driver: active_driver.execute_script("return document.readyState") == "complete")
        wait.until(expected.presence_of_element_located((By.TAG_NAME, "body")))

    def _run_page_load_check(self, target: TargetSite, test_case: TestCase) -> TestResult:
        started = time.perf_counter()
        logs = [
            self._log_event(
                "page_load_start",
                test_id=test_case.id,
                target=test_case.target,
                timeout_seconds=self.timeout_seconds,
                retries=self.retries,
            )
        ]
        url = target.base_url.rstrip("/") + "/" + test_case.target.lstrip("/")

        last_error: str | None = None
        last_status: int | None = None
        for attempt in range(1, self.retries + 2):
            result = self._run_page_load_attempt(url, test_case, started, logs, attempt)
            if result.status == "passed":
                return result
            last_error = result.error
            last_status = result.response_status
            if attempt <= self.retries:
                self._sleep_before_retry(attempt, logs)

        return TestResult(
            test_case=test_case,
            status="failed" if last_status else "error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            logs=logs,
            response_status=last_status,
            error=last_error,
        )

    def _run_page_load_attempt(
        self,
        url: str,
        test_case: TestCase,
        started: float,
        logs: list[str],
        attempt: int,
    ) -> TestResult:
        try:
            logs.append(self._log_event("page_load_attempt", attempt=attempt, url=url))
            with urlopen(url, timeout=self.timeout_seconds) as response:
                status = response.status
                html = response.read().decode("utf-8", errors="replace")
            passed = status == test_case.expected_status and bool(html.strip())
            logs.append(
                self._log_event(
                    "page_load_response",
                    attempt=attempt,
                    status=status,
                    html_bytes=len(html),
                    passed=passed,
                )
            )
            return TestResult(
                test_case=test_case,
                status="passed" if passed else "failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                response_status=status,
                error=None if passed else "Page did not load as expected",
            )
        except HTTPError as exc:
            logs.append(self._log_event("page_load_http_error", attempt=attempt, status=exc.code, message=str(exc)))
            return TestResult(
                test_case=test_case,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                response_status=exc.code,
                error=str(exc),
            )
        except (URLError, SocketTimeout, TimeoutError) as exc:
            logger.warning("UI page-load attempt errored for %s: %s", url, self._format_exception(exc))
            logs.append(
                self._log_event(
                    "page_load_network_error",
                    attempt=attempt,
                    exception_type=type(exc).__name__,
                    message=self._format_exception(exc),
                )
            )
            return TestResult(
                test_case=test_case,
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                logs=logs,
                error=self._format_exception(exc),
            )

    def _capture_screenshot(self, driver, test_case: TestCase, attempt: int, logs: list[str]) -> str | None:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        safe_test_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in test_case.id)
        path = self.screenshot_dir / f"{safe_test_id}_attempt_{attempt}_{int(time.time())}.png"
        try:
            driver.save_screenshot(str(path))
            logs.append(self._log_event("screenshot_captured", attempt=attempt, path=str(path)))
            return str(path)
        except Exception as exc:
            logger.exception("Could not capture screenshot for %s", test_case.id)
            logs.append(
                self._log_event(
                    "screenshot_error",
                    attempt=attempt,
                    exception_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            return None

    def _quit_driver(self, driver, logs: list[str]) -> None:
        try:
            driver.quit()
            logs.append(self._log_event("selenium_driver_closed"))
        except Exception as exc:
            logger.warning("Could not close Selenium driver: %s", exc)
            logs.append(self._log_event("selenium_driver_close_error", message=str(exc)))

    def _sleep_before_retry(self, attempt: int, logs: list[str]) -> None:
        delay_seconds = min(2**attempt, 5)
        logs.append(self._log_event("retry_scheduled", attempt=attempt, delay_seconds=delay_seconds))
        time.sleep(delay_seconds)

    def _result(
        self,
        test_case: TestCase,
        status: str,
        started: float,
        logs: list[str],
        error: str | None = None,
    ) -> TestResult:
        return TestResult(
            test_case=test_case,
            status=status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            logs=logs,
            error=error,
        )

    @staticmethod
    def _format_exception(exc: BaseException) -> str:
        if isinstance(exc, URLError):
            return str(exc.reason)
        return str(exc)

    @staticmethod
    def _with_screenshot(error: str, screenshot_path: str | None) -> str:
        if not screenshot_path:
            return error
        return f"{error} | Screenshot: {screenshot_path}"

    @staticmethod
    def _log_event(event: str, **fields: object) -> str:
        payload = {"event": event, **fields}
        return json.dumps(payload, sort_keys=True)
