from __future__ import annotations

import unittest

from qa_agent.report_service import ai_insights, result_counts, summary_text


class ReportServiceTests(unittest.TestCase):
    def test_counts_summary_and_insights_from_review_record(self) -> None:
        record = {
            "approval_status": "pending",
            "report": {
                "site_name": "Demo",
                "results": [
                    {"status": "passed"},
                    {"status": "failed"},
                    {"status": "error"},
                ],
                "analyses": [
                    {
                        "test_id": "api-1",
                        "likely_cause": "Server-side failure.",
                        "recommendation": "Check backend logs.",
                    }
                ],
            },
        }

        self.assertEqual(
            result_counts(record),
            {"total": 3, "passed": 1, "failed": 1, "errors": 1, "skipped": 0},
        )
        self.assertEqual(summary_text(record), "Demo: 1/3 passed, 2 need attention.")
        self.assertIn("api-1", ai_insights(record)[0])


if __name__ == "__main__":
    unittest.main()
