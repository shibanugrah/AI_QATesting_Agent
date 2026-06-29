from __future__ import annotations

import pytest

from qa_agent.models import TargetSite
from qa_agent.security import TargetSafetyError, validate_authorized_external_target


def test_execution_requires_authorization() -> None:
    with pytest.raises(TargetSafetyError, match="authorized=true"):
        validate_authorized_external_target(TargetSite(name="Demo", base_url="https://example.com"))


def test_private_ip_target_is_blocked() -> None:
    with pytest.raises(TargetSafetyError, match="Private"):
        validate_authorized_external_target(
            TargetSite(name="Demo", base_url="http://127.0.0.1", authorized=True)
        )
