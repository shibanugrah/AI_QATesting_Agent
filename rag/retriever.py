from __future__ import annotations

from rag.embedder import Embedder
from rag.vector_store import VectorStore

from qa_agent.logging_utils import get_logger
from qa_agent.models import TestResult

logger = get_logger(__name__)


class Retriever:
    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedder = embedder or Embedder()
        self.vector_store = vector_store or VectorStore()

    def remember_failure(self, result: TestResult) -> None:
        text = "\n".join(result.logs + ([result.error] if result.error else []))
        metadata = {
            "test_id": result.test_case.id,
            "test_name": result.test_case.name,
            "status": result.status,
            "response_status": result.response_status,
        }
        self.vector_store.add(text, self.embedder.embed(text), metadata)
        logger.info("Remembered failure for %s", result.test_case.id)

    def retrieve(self, text: str, limit: int = 3) -> list[dict]:
        if not text.strip():
            return []
        results = self.vector_store.search(self.embedder.embed(text), limit)
        logger.info("Retrieved %d similar failure memories", len(results))
        return results
