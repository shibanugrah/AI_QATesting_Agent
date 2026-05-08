from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from qa_agent.logging_utils import get_logger
from qa_agent.models import Report
from qa_agent.pipeline import QAPipeline
from scheduler.job_queue import Job, JobQueue

logger = get_logger(__name__)


class Worker:
    def __init__(self, pipeline: QAPipeline | None = None) -> None:
        self.pipeline = pipeline or QAPipeline()

    def run_job(self, job: Job) -> Report:
        logger.info("Running job %s for %s", job.id, job.target.name)
        return self.pipeline.run(job.target)

    def run_batch(self, queue: JobQueue, parallelism: int = 2) -> list[Report]:
        jobs: list[Job] = []
        while True:
            job = queue.dequeue()
            if not job:
                break
            jobs.append(job)

        reports: list[Report] = []
        with ThreadPoolExecutor(max_workers=parallelism) as executor:
            futures = {executor.submit(self.run_job, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    reports.append(future.result())
                except Exception:
                    logger.exception("Job %s failed", job.id)
                    queue.retry(job)
        return reports

