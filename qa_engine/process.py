"""Trusted native process execution. Fixed argv, minimal environment, bounded output/time."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass


@dataclass
class ProcessResult:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False


def environment(extra=None):
    keep = {
        "PATH",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in {s.upper() for s in keep}}
    env.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1", "CI": "1", "GIT_TERMINAL_PROMPT": "0"})
    env.update(extra or {})
    return env


def stop_tree(proc):
    if os.name == "nt":
        job = getattr(proc, "_qa_job", None)
        if job:
            job.close()
            return
        subprocess.run(
            [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            shell=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()


def execute(argv, cwd, timeout=30, cap=1_000_000, extra_env=None):
    started = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment(extra_env),
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if os.name == "nt":
        from qa_engine.windows_job import WindowsJob

        try:
            proc._qa_job = WindowsJob(proc)
        except OSError:
            stop_tree(proc)
            proc.wait(timeout=10)
            raise
    buffers = [bytearray(), bytearray()]
    overflow = [False]

    def drain(stream, buffer):
        while chunk := stream.read(8192):
            remaining = cap - len(buffer)
            buffer.extend(chunk[: max(0, remaining)])
            if len(chunk) > remaining:
                overflow[0] = True
        stream.close()

    threads = [
        threading.Thread(target=drain, args=(stream, buffers[index]), daemon=True)
        for index, stream in enumerate((proc.stdout, proc.stderr))
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
        for thread in threads:
            thread.join(timeout=max(0.01, timeout - (time.monotonic() - started)))
        if any(t.is_alive() for t in threads):
            timed_out = True
            stop_tree(proc)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        timed_out = True
        stop_tree(proc)
        proc.wait(timeout=10)
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        if os.name == "nt":
            proc._qa_job.close()
        for thread in threads:
            thread.join(timeout=2)
    return ProcessResult(
        list(argv),
        proc.returncode,
        *(bytes(b).decode("utf-8", "replace") for b in buffers),
        int((time.monotonic() - started) * 1000),
        timed_out,
        overflow[0],
    )
