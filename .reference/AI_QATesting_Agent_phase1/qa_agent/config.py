from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from qa_agent.models import Priority, TargetSite, TestCase, TestSuite


class ConfigError(ValueError):
    """Raised when a target configuration is invalid or unsafe to interpret."""


_ALLOWED_TOP_LEVEL = {
    "name",
    "base_url",
    "api_endpoints",
    "ui_paths",
    "test_cases",
    "authorized",
    "environment",
}
_ALLOWED_CASE_FIELDS = {
    "id",
    "name",
    "suite",
    "kind",
    "target",
    "method",
    "expected_status",
    "expected_text",
    "priority",
    "tags",
    "execution_adapter",
}


def load_target(path: str | Path) -> TargetSite:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {source}: {exc.msg} (line {exc.lineno}).") from exc
    return target_from_dict(data)


def target_from_dict(data: Any) -> TargetSite:
    if not isinstance(data, dict):
        raise ConfigError("Target configuration must be a JSON object.")

    unknown = set(data) - _ALLOWED_TOP_LEVEL
    if unknown:
        details = ", ".join(sorted(unknown))
        if "api_tests" in unknown:
            raise ConfigError("Unknown field 'api_tests'. Use 'api_endpoints' instead.")
        raise ConfigError(f"Unknown configuration field(s): {details}.")

    name = _required_str(data, "name")
    base_url = _required_str(data, "base_url")
    _validate_base_url(base_url)
    api_endpoints = _paths(data.get("api_endpoints", []), "api_endpoints")
    default_ui_paths = ["/"] if not api_endpoints else []
    ui_paths = _paths(data.get("ui_paths", default_ui_paths), "ui_paths")
    authorized = data.get("authorized", False)
    environment = data.get("environment", "demo")

    if not isinstance(authorized, bool):
        raise ConfigError("'authorized' must be true or false.")
    if environment not in {"local", "demo", "staging"}:
        raise ConfigError("'environment' must be one of: local, demo, staging.")

    raw_cases = data.get("test_cases", [])
    if not isinstance(raw_cases, list):
        raise ConfigError("'test_cases' must be a list.")
    test_cases = [_case_from_dict(item, index) for index, item in enumerate(raw_cases, start=1)]

    if test_cases and (api_endpoints or ui_paths != ["/"]):
        raise ConfigError(
            "Use either explicit 'test_cases' or legacy 'api_endpoints'/'ui_paths', not both."
        )

    return TargetSite(
        name=name,
        base_url=base_url.rstrip("/"),
        api_endpoints=api_endpoints,
        ui_paths=ui_paths,
        test_cases=test_cases,
        authorized=authorized,
        environment=environment,
    )


def _case_from_dict(data: Any, index: int) -> TestCase:
    if not isinstance(data, dict):
        raise ConfigError(f"test_cases[{index}] must be an object.")
    unknown = set(data) - _ALLOWED_CASE_FIELDS
    if unknown:
        raise ConfigError(
            f"Unknown field(s) in test_cases[{index}]: {', '.join(sorted(unknown))}."
        )
    try:
        tags = data.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ConfigError(f"test_cases[{index}].tags must be a list of strings.")
        return TestCase(
            id=_required_str(data, "id", f"test_cases[{index}]"),
            name=_required_str(data, "name", f"test_cases[{index}]"),
            suite=TestSuite(_required_str(data, "suite", f"test_cases[{index}]")),
            kind=_required_str(data, "kind", f"test_cases[{index}]"),
            target=_required_str(data, "target", f"test_cases[{index}]"),
            method=data.get("method", "GET"),
            expected_status=data.get("expected_status", 200),
            expected_text=data.get("expected_text"),
            priority=Priority(data.get("priority", "medium")),
            tags=tags,
            execution_adapter=data.get("execution_adapter", ""),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid test_cases[{index}]: {exc}") from exc


def _required_str(data: dict[str, Any], key: str, prefix: str = "configuration") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{prefix}.{key} must be a non-empty string.")
    return value.strip()


def _paths(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{field_name}' must be a list of relative path strings.")
    result = [item.strip() for item in value]
    if not all(item.startswith("/") for item in result):
        raise ConfigError(f"Every '{field_name}' item must start with '/'.")
    return result


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigError("base_url must be an absolute http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ConfigError("base_url must not contain embedded credentials.")
