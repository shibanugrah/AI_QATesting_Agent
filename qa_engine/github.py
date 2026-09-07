"""Read-only GitHub metadata mapping. CI status is never an input to the gate."""

import re

from qa_engine.security import PolicyBlocked


def bind_pull_request(repository, event):
    pr = event.get("pull_request")
    if not pr:
        return repository
    base, head = pr["base"]["sha"], pr["head"]["sha"]
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (base, head)):
        raise PolicyBlocked("INVALID_GITHUB_SHA")
    name = event.get("repository", {}).get("full_name")
    if (
        repository.head_sha != head
        or repository.base_sha != base
        or (repository.github_repository and name != repository.github_repository)
    ):
        raise PolicyBlocked("GITHUB_CHECKOUT_MISMATCH")
    return repository.model_copy(update={"github_repository": name, "pr_number": int(pr["number"])})
