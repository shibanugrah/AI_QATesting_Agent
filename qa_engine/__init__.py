"""Independent, deterministic verification for owner-enrolled projects."""

__version__ = "1.0.0.dev1"

from qa_engine.domain import Project, RunRequest, RunResult

__all__ = ["Project", "RunRequest", "RunResult", "Engine"]


def __getattr__(name):
    if name == "Engine":
        from qa_engine.engine import Engine

        return Engine
    raise AttributeError(name)
