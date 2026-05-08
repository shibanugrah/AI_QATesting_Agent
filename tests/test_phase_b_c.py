from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from qa_agent.models import TargetSite, TestCase, TestResult
from rag.embedder import Embedder
from rag.retriever import Retriever
from rag.vector_store import VectorStore
from scheduler.job_queue import JobQueue


class PhaseBCTests(unittest.TestCase):
    def test_rag_retrieves_similar_failure(self) -> None:
        temp_dir = Path("artifacts") / "test_runs" / str(uuid4())
        retriever = Retriever(
            embedder=Embedder(),
            vector_store=VectorStore(str(temp_dir / "store.json")),
        )
        result = TestResult(
            test_case=TestCase(id="api-1", name="server error", kind="api", target="/health"),
            status="failed",
            duration_ms=5,
            logs=["HTTP error: 500", "dependency timeout"],
            response_status=500,
            error="Internal Server Error",
        )

        retriever.remember_failure(result)
        matches = retriever.retrieve("dependency timeout caused HTTP 500", limit=1)

        self.assertEqual(len(matches), 1)
        self.assertGreater(matches[0]["score"], 0)

    def test_job_queue_retries_once(self) -> None:
        queue = JobQueue()
        job = queue.enqueue(TargetSite(name="Local", base_url="http://127.0.0.1"), max_retries=1)

        self.assertIs(queue.dequeue(), job)
        self.assertTrue(queue.retry(job))
        self.assertIs(queue.dequeue(), job)
        self.assertFalse(queue.retry(job))


if __name__ == "__main__":
    unittest.main()
