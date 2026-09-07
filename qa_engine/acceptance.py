"""Repeatable 30-scenario harness; retains machine evidence and honest external status."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from qa_engine.domain import now, uid
from qa_engine.process import execute


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/acceptance")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    session = output / uid()
    session.mkdir()
    junit = session / "junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(root / "tests/test_engine_acceptance.py"),
        "-q",
        f"--junitxml={junit}",
        f"--basetemp={session / 'fixtures'}",
    ]
    result = execute(command, root, timeout=900, cap=2_000_000)
    (session / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    records = {}
    if junit.is_file():
        for test in ET.parse(junit).iter("testcase"):
            name = test.attrib["name"]
            number = int(name.split("_")[1])
            status = (
                "FAIL"
                if test.find("failure") is not None or test.find("error") is not None
                else "NOT REVERIFIED"
                if test.find("skipped") is not None
                else "PASS"
            )
            records[number] = {
                "scenario": number,
                "name": name,
                "status": status,
                "seconds": float(test.attrib.get("time", 0)),
                "evidence": str(junit),
            }
    for number in range(1, 31):
        records.setdefault(number, {"scenario": number, "status": "NOT REVERIFIED", "evidence": str(session / "pytest.log")})
    records[20]["status"] = "NOT APPLICABLE" if records[20]["status"] == "PASS" else records[20]["status"]
    records[20]["note"] = "No visual baseline namespace exists in V1; absence assertion executed."
    records[25]["note"] = "Deterministic pip-audit protocol fixture; live integration evidence is recorded separately."
    proofs = {}
    for name in ("clean-install", "live-scanner"):
        candidates = sorted((root / "artifacts" / name).glob("*/result.json"), key=lambda p: p.stat().st_mtime)
        if candidates:
            proof = json.loads(candidates[-1].read_text(encoding="utf-8"))
            proofs[name] = {"status": proof.get("status", "NOT REVERIFIED"), "evidence": str(candidates[-1])}
        else:
            proofs[name] = {"status": "NOT REVERIFIED"}
    records[1]["note"] = "Fresh-venv wheel installation and outside-checkout control tests are required in addition to package smoke."
    records[1]["clean_install"] = proofs["clean-install"]
    if records[1]["status"] == "PASS" and proofs["clean-install"]["status"] != "PASS":
        records[1]["status"] = "NOT REVERIFIED"
    records[25]["live_scanner"] = proofs["live-scanner"]
    manifest = {
        "schema_version": 1,
        "at": now(),
        "command": command,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "scenarios": [records[i] for i in range(1, 31)],
        "external_three_project_proof": "NOT YET EXECUTED",
        "fixture_root": str(session / "fixtures"),
    }
    (output / "results.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        "# QA Engine acceptance",
        "",
        f"Command exit code: {result.exit_code}",
        "",
        "| Scenario | Result | Evidence |",
        "|---|---|---|",
    ]
    for number, record in sorted(records.items()):
        lines.append(f"| {number} | {record['status']} | `{record['evidence']}` |")
    lines += [
        "",
        "Controlled fixture evidence only. External three-project proof: **NOT YET EXECUTED**.",
        "Live dependency scanner: **" + proofs["live-scanner"]["status"] + "** (separate integration evidence).",
        "Clean environment installation evidence: see docs/VERIFICATION.md.",
    ]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"results": str(output / "results.json"), "summary": str(output / "summary.md"), "exit_code": result.exit_code}))
    return (
        0
        if result.exit_code == 0 and not result.timed_out and all(r["status"] in {"PASS", "NOT APPLICABLE"} for r in records.values())
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
