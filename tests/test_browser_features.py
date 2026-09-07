import pytest

from qa_engine import Engine, RunRequest
from qa_engine.domain import Step
from tests.engine_fixtures import web_fixture, web_project

pytestmark = [pytest.mark.browser, pytest.mark.integration]


@pytest.mark.parametrize("broken", [False, True])
def test_live_axe_rules(tmp_path, monkeypatch, broken):
    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "fixture-private-value")
    with web_fixture() as (url, _):
        project = web_project(url, browser=True)
        project.policy.required = ["accessibility"]
        project.policy.timeout_seconds = 20
        project.journeys[0].profiles = project.journeys[0].profiles[:1]
        project.journeys[0].steps = [
            Step(action="goto", value=url + "/a11y" if broken else url),
            Step(action="expect_visible", selector="h1"),
        ]
        engine = Engine(tmp_path)
        engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=["accessibility"]))
        assert result.gate.decision == ("FAIL" if broken else "PASS"), result.gate
        findings = result.checks[0].attempts[0].details["tests"][0]["accessibility"]
        assert bool(findings) == broken
        if broken:
            assert any(v["id"] == "label" for v in findings)


def test_browser_redirect_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_FIXTURE_PASSWORD", "fixture-private-value")
    with web_fixture() as (url, state):
        project = web_project(url, browser=True)
        project.journeys[0].profiles = project.journeys[0].profiles[:1]
        project.journeys[0].steps = [Step(action="goto", value=url + "/redirect"), Step(action="expect_visible", selector="h1")]
        engine = Engine(tmp_path)
        engine.enroll(project)
        result = engine.run(RunRequest(project_id=project.id, profiles=["browser_e2e"]))
        assert result.gate.decision == "REVIEW_REQUIRED", result.gate
        assert state["requests"] == 1
        assert result.checks[0].classification == "POLICY_BLOCKED"
