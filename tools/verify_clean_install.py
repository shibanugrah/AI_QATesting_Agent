"""Build the working source, install its wheel in a fresh venv, run control tests outside the checkout."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts/clean-install" / str(uuid4())
    output.mkdir(parents=True)
    commands = []
    log = []

    def run(argv, cwd, timeout=300):
        commands.append(argv)
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        log.append(result.stdout + result.stderr)
        (output / "commands.log").write_text("\n".join(log), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"clean install command exited {result.returncode}")

    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(output / "wheels")], root)
    run([sys.executable, "-m", "venv", str(output / "venv")], output)
    python = output / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheel = next((output / "wheels").glob("*.whl"))
    run([str(python), "-m", "pip", "install", str(wheel) + "[dev]"], output)
    outside = output / "outside-checkout"
    (outside / "tests").mkdir(parents=True)
    for name in ["__init__.py", "engine_fixtures.py", "test_engine_controls.py"]:
        shutil.copyfile(root / "tests" / name, outside / "tests" / name)
    run(
        [
            str(python),
            "-m",
            "pytest",
            "tests/test_engine_controls.py",
            "-q",
            "--junitxml=" + str(output / "junit.xml"),
            "--basetemp=" + str(output / "fixtures"),
        ],
        outside,
    )
    result = {
        "status": "PASS",
        "wheel": str(wheel),
        "commands": commands,
        "evidence": str(output / "junit.xml"),
        "note": "Fresh venv, wheel installation, tests executed outside source checkout; browser live verification is separate.",
    }
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
