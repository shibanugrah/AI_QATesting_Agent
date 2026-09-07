from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]
Kind = Literal[
    "lint",
    "type",
    "build",
    "unit",
    "integration",
    "regression",
    "api",
    "smoke",
    "browser_e2e",
    "accessibility",
    "web_diagnostics",
    "security_dependency_scan",
    "security_headers",
]
Status = Literal["PENDING", "READY", "RUNNING", "SUCCEEDED", "FAILED", "ERROR", "BLOCKED", "SKIPPED", "AWAITING_APPROVAL", "CANCELLED"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid4())


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class Condition(Model):
    pattern: str
    required: list[Kind]


class Policy(Model):
    version: Identifier = "v1"
    required: list[Kind] = Field(min_length=1)
    conditional: list[Condition] = []
    allowed_commands: list[Identifier] = []
    allowed_hosts: list[str] = []
    allowed_ports: list[int] = [80, 443]
    allow_loopback: bool = False
    allow_mutation: bool = False
    diagnostic_retries: int = Field(default=1, ge=0, le=2)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_requests: int = Field(default=100, ge=1, le=1000)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_artifact_bytes: int = Field(default=5_000_000, ge=1024, le=50_000_000)
    max_run_artifact_bytes: int = Field(default=50_000_000, ge=1_000_000, le=500_000_000)
    retention_days: int = Field(default=30, ge=1, le=365)
    regression_checks: list[Kind] = ["unit"]


class APIEndpoint(Model):
    id: Identifier
    url: str
    tags: list[Literal["api", "smoke"]] = ["api"]
    method: Literal["GET", "HEAD", "OPTIONS"] = "GET"
    expected_status: int = Field(default=200, ge=100, le=599)
    expected_text: str | None = None
    expected_json: dict[str, Any] = {}
    expected_headers: dict[str, str] = {}
    credential_ref: Identifier | None = None


class Step(Model):
    action: Literal["goto", "fill", "click", "check", "select", "expect_text", "expect_visible", "expect_url"]
    selector: str | None = None
    value: str | None = None
    credential_ref: Identifier | None = None

    @model_validator(mode="after")
    def correct_fields(self):
        if self.action not in {"goto", "expect_url"} and not self.selector:
            raise ValueError("selector required")
        if self.action in {"goto", "expect_url", "expect_text", "select"} and self.value is None:
            raise ValueError("value required")
        if self.action == "fill" and (self.value is None) == (self.credential_ref is None):
            raise ValueError("fill requires exactly one value or credential_ref")
        if self.credential_ref and self.action != "fill":
            raise ValueError("credential_ref is only valid for fill")
        return self


class Viewport(Model):
    name: Identifier = "desktop"
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=720, ge=320, le=2160)


class Journey(Model):
    id: Identifier
    steps: list[Step] = Field(min_length=1, max_length=100)
    profiles: list[Viewport] = Field(default_factory=lambda: [Viewport()], min_length=1, max_length=5)
    fail_on_console_error: bool = True
    fail_on_network_error: bool = True

    @model_validator(mode="after")
    def unique_profiles(self):
        if len({p.name for p in self.profiles}) != len(self.profiles):
            raise ValueError("duplicate viewport names")
        return self


class Project(Model):
    schema_version: Literal[1] = 1
    id: Identifier
    repository: str | None = None
    environment: Literal["local", "staging"] = "local"
    policy: Policy
    api_endpoints: list[APIEndpoint] = Field(default_factory=list, max_length=100)
    journeys: list[Journey] = Field(default_factory=list, max_length=20)
    credentials: dict[Identifier, Identifier] = {}

    @model_validator(mode="after")
    def coherent(self):
        for items in (self.api_endpoints, self.journeys):
            if len({x.id for x in items}) != len(items):
                raise ValueError("duplicate check IDs")
        if self.policy.allow_loopback and self.environment != "local":
            raise ValueError("loopback authorization is local-only")
        refs = [x.credential_ref for x in self.api_endpoints]
        refs += [s.credential_ref for j in self.journeys for s in j.steps]
        if any(ref and ref not in self.credentials for ref in refs):
            raise ValueError("unknown project credential reference")
        return self


class GitHubPR(Model):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    number: int = Field(ge=1)
    base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")


class RunRequest(Model):
    project_id: Identifier
    operation: Literal["VERIFY_CHANGE", "TEST_TARGET", "INVESTIGATE_BUG", "VERIFY_FIX", "RELEASE_GATE"] = "VERIFY_CHANGE"
    profiles: list[Kind] = []
    base_ref: str | None = None
    head_ref: str = "HEAD"
    previous_run_id: Identifier | None = None
    dry_run: bool = False
    advisory_additions: list[Kind] = []
    context: str = Field(default="", max_length=10000)
    github_pr: GitHubPR | None = None


class RepositoryIdentity(Model):
    path: str
    head_sha: str
    base_sha: str | None = None
    branch: str
    remote: str = ""
    dirty: bool
    dirty_diff_hash: str
    changed_files: list[str]
    github_repository: str | None = None
    pr_number: int | None = None


class Capability(Model):
    kind: Kind
    command_id: str | None = None
    available: bool
    source: str
    reason: str = ""


class PlanItem(Model):
    id: Identifier
    kind: Kind
    mandatory: bool
    available: bool
    command_id: str | None = None
    source: str
    reason: str = ""


class TestPlan(Model):
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=uid)
    project_id: Identifier
    policy_version: str
    policy_hash: str
    request: RunRequest
    repository: RepositoryIdentity | None = None
    items: list[PlanItem]
    required: list[Kind]
    risk_level: Literal["LOW", "HIGH", "UNKNOWN"] = "UNKNOWN"
    impact_basis: list[str] = []


class ArtifactRef(Model):
    id: str = Field(default_factory=uid)
    path: str
    sha256: str
    size: int
    kind: str
    redaction_status: Literal["SANITIZED"] = "SANITIZED"
    sensitivity: str = "project-private"
    retention_days: int = 30


class Attempt(Model):
    number: int
    status: Literal["SUCCEEDED", "FAILED", "ERROR", "BLOCKED"]
    started_at: str = Field(default_factory=now)
    duration_ms: int = 0
    exit_code: int | None = None
    failure_code: str | None = None
    evidence: list[ArtifactRef] = []
    details: dict[str, Any] = {}


class Finding(Model):
    check_id: str
    category: str
    message: str
    evidence_refs: list[str] = []


class CheckResult(Model):
    id: str
    kind: Kind
    status: Status
    mandatory: bool
    attempts: list[Attempt] = []
    classification: str = "UNKNOWN"
    reason: str = ""
    fingerprint: str | None = None
    definition_hash: str = ""


class StageResult(Model):
    stage_id: int
    name: str
    stage_version: int = 1
    status: Status = "PENDING"
    started_at: str | None = None
    finished_at: str | None = None
    input_refs: list[str] = []
    output_refs: list[str] = []
    evidence_refs: list[str] = []
    executor: str = "qa-engine"
    executor_version: str = "1.0.0.dev1"
    timeout: int = 30
    attempts: int = 0
    retry_policy: int = 0
    skip_reason: str | None = None
    failure_code: str | None = None
    failure_effect: str | None = None
    approval_required: bool = False
    approval_ref: str | None = None
    policy_version: str


class GateResult(Model):
    decision: Literal["PASS", "FAIL", "REVIEW_REQUIRED", "NOT_EVALUATED"] = "NOT_EVALUATED"
    reason_codes: list[str] = []
    missing: list[str] = []


class RunResult(Model):
    schema_version: Literal[1] = 1
    run_id: str = Field(default_factory=uid)
    project_id: Identifier
    environment_id: str
    operation: str
    plan: TestPlan
    stages: list[StageResult]
    checks: list[CheckResult] = []
    findings: list[Finding] = []
    artifacts: list[ArtifactRef] = []
    memory_matches: list[str] = []
    run_status: Literal["RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "ERROR", "CANCELLED"] = "RUNNING"
    gate: GateResult = Field(default_factory=GateResult)
    approval: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    started_at: str = Field(default_factory=now)
    finished_at: str | None = None
    tool_versions: dict[str, str] = {}
    previous_run_id: str | None = None


class MemoryRecord(Model):
    id: str = Field(default_factory=uid)
    project_id: Identifier
    run_id: str
    check_id: str
    fingerprint: str
    text: str
    state: Literal["OBSERVED", "REPRODUCED", "FIX_VALIDATED", "APPROVED", "REJECTED", "STALE", "EXPIRED"] = "OBSERVED"
    policy_hash: str
    fix_run_id: str | None = None
    expires_at: str
    sanitized: bool = True
