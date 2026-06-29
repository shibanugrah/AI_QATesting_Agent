from __future__ import annotations

import json

import pytest

from qa_agent.config import ConfigError, load_target, target_from_dict


def test_rejects_legacy_api_tests_field() -> None:
    with pytest.raises(ConfigError, match="api_tests.*api_endpoints"):
        target_from_dict(
            {
                "name": "Demo",
                "base_url": "https://example.com",
                "api_tests": ["/health"],
            }
        )


def test_loads_valid_explicit_test_case(tmp_path) -> None:
    config = {
        "name": "Demo",
        "base_url": "https://example.com",
        "authorized": True,
        "test_cases": [
            {
                "id": "smoke-home",
                "name": "Home loads",
                "suite": "smoke",
                "kind": "ui",
                "target": "/",
            }
        ],
    }
    path = tmp_path / "target.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    target = load_target(path)

    assert target.authorized is True
    assert target.test_cases[0].suite.value == "smoke"


def test_rejects_unknown_case_field() -> None:
    with pytest.raises(ConfigError, match="Unknown field"):
        target_from_dict(
            {
                "name": "Demo",
                "base_url": "https://example.com",
                "test_cases": [
                    {
                        "id": "smoke-home",
                        "name": "Home",
                        "suite": "smoke",
                        "kind": "ui",
                        "target": "/",
                        "shell_command": "rm -rf /",
                    }
                ],
            }
        )
