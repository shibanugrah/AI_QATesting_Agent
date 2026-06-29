from __future__ import annotations

import json

from qa_agent.cli import main


def test_plan_command_prints_included_and_excluded_cases(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = {
        "name": "Demo",
        "base_url": "https://example.com",
        "authorized": True,
        "test_cases": [
            {"id": "smoke-home", "name": "Home", "suite": "smoke", "kind": "ui", "target": "/"},
            {"id": "api-home", "name": "API", "suite": "api", "kind": "api", "target": "/"},
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = main(["plan", "--config", str(path), "--suite", "smoke"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Selected suites: smoke" in output
    assert "smoke-home" in output
    assert "api-home: suite not selected: api" in output
