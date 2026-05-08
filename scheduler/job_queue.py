from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from uuid import uuid4

from qa_agent.logging_utils import get_logger
from qa_agent.models import TargetSite

logger = get_logger(__name__)


@dataclass(slots=True)
class Job:
    target: TargetSite
    id: str = field(default_factory=lambda: str(uuid4()))
    attempts: int = 0
    max_retries: int = 1


class JobQueue:
    def __init__(self) -> None:
        self._jobs: deque[Job] = deque()

    def enqueue(self, target: TargetSite, max_retries: int = 1) -> Job:
        job = Job(target=target, max_retries=max_retries)
        self._jobs.append(job)
        logger.info("Queued job %s for %s", job.id, target.name)
        return job

    def dequeue(self) -> Job | None:
        if not self._jobs:
            return None
        job = self._jobs.popleft()
        logger.info("Dequeued job %s", job.id)
        return job

    def retry(self, job: Job) -> bool:
        job.attempts += 1
        if job.attempts > job.max_retries:
            logger.warning("Job %s exhausted retries", job.id)
            return False
        self._jobs.append(job)
        logger.info("Requeued job %s attempt %d", job.id, job.attempts)
        return True

    def __len__(self) -> int:
        return len(self._jobs)

