from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from uuid import uuid4

from executor.selenium_runner import SeleniumRunner
from qa_agent.models import TargetSite, TestCase


class SeleniumRunnerTests(unittest.TestCase):
    def test_page_load_retries_and_writes_structured_logs(self) -> None:
        runner = SeleniumRunner(timeout_seconds=1, retries=1)
        test_case = TestCase(id="ui-1", name="Home", kind="ui", target="/")

        with patch("executor.selenium_runner.urlopen", side_effect=URLError("blocked")):
            with patch.object(runner, "_sleep_before_retry"):
                result = runner.run(TargetSite(name="Local", base_url="http://127.0.0.1"), test_case)

        events = [json.loads(entry)["event"] for entry in result.logs]
        self.assertEqual(result.status, "error")
        self.assertEqual(events.count("page_load_attempt"), 2)
        self.assertIn("page_load_network_error", events)

    def test_capture_screenshot_saves_to_artifacts(self) -> None:
        screenshot_dir = Path("artifacts") / "test_runs" / str(uuid4()) / "screenshots"
        runner = SeleniumRunner(screenshot_dir=str(screenshot_dir))
        driver = FakeDriver()
        logs: list[str] = []

        path = runner._capture_screenshot(
            driver,
            TestCase(id="ui/home", name="Home", kind="ui", target="/"),
            attempt=1,
            logs=logs,
        )

        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertIn("screenshot_captured", logs[0])


class FakeDriver:
    def save_screenshot(self, path: str) -> bool:
        Path(path).write_bytes(b"fake screenshot")
        return True


if __name__ == "__main__":
    unittest.main()
