from __future__ import annotations

from pathlib import Path

from qa_agent.json_utils import read_json, write_json
from qa_agent.logging_utils import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Small persistent vector store with a FAISS-ready interface."""

    def __init__(self, path: str = "artifacts/rag/vector_store.json") -> None:
        self.path = Path(path)
        self.records: list[dict] = []
        self.load()

    def add(self, text: str, embedding: list[float], metadata: dict | None = None) -> None:
        self.records.append(
            {
                "text": text,
                "embedding": embedding,
                "metadata": metadata or {},
            }
        )
        self.save()
        logger.info("Stored RAG memory item; total=%d", len(self.records))

    def search(self, embedding: list[float], limit: int = 3) -> list[dict]:
        scored = [
            {**record, "score": self._dot(embedding, record["embedding"])}
            for record in self.records
        ]
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    def save(self) -> None:
        write_json(self.path, {"records": self.records})

    def load(self) -> None:
        if self.path.exists():
            self.records = read_json(self.path).get("records", [])

    @staticmethod
    def _dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

