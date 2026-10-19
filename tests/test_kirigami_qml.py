"""QML suite driver: cases run in short-lived, isolated subprocesses.

kirigami_qml_cases.py aborts when its cases share one process (Qt 6.12
GC/shiboken teardown of accumulated QML engines; measured: Fatal error:
Aborted after ~20 cases). Every case passes in isolation. A few cases
additionally segfault during interpreter teardown *after* passing (exit
139 with PASSED already printed).

So the driver collects the case ids and runs them in **batches** of
`BATCH` cases per `pytest` subprocess, serially. A case counts as passed
when its PASSED line printed, which pytest flushes per write, so the
lines before an abort survive. A batch whose abort swallowed cases (its
PASSED lines are incomplete) is not trusted: the missing cases are
re-run individually, and only those still lacking a PASSED line fail —
real regressions fail assertions before PASSED, so nothing is masked.

Tuning knobs, all optional (the defaults keep the suite as it was):

    TKARCADE_QML_BATCH      cases per subprocess (default 8)
    TKARCADE_QML_WORKERS    parallel subprocesses (default 1; >1 can
                            flake timing-sensitive cases under load)

Single-case dev loop:
    python -m pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"

Fast loop without the QML suite (the rest is ~15s):
    python -m pytest tests/ -q -m "not qml"
"""

import concurrent.futures
import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parent / "kirigami_qml_cases.py"
ROOT = Path(__file__).resolve().parent.parent
# Cases per subprocess: sized well under the ~20-case abort threshold so a
# batch normally finishes; anything it does lose is re-run individually.
BATCH = int(os.environ.get("TKARCADE_QML_BATCH") or 8)
# Serial by default: parallel offscreen Qt processes flake timing-sensitive
# cases and abort under contention; one subprocess at a time.
WORKERS = max(1, int(os.environ.get("TKARCADE_QML_WORKERS") or 1))
CASE_TIMEOUT = 240  # seconds a single case may take before we call it hung
BATCH_SECONDS_PER_CASE = 30  # headroom per case before a batch gives up


def _base_cmd(*args: str) -> list[str]:
    """Hermetic inner pytest invocation (no cache writes, no outer addopts)."""
    return [
        sys.executable,
        "-m",
        "pytest",
        *args,
        "-p",
        "no:cacheprovider",
        "-o",
        "python_files=*.py",
    ]


def _inner_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    return env


def _collect_ids() -> list[str]:
    r = subprocess.run(
        _base_cmd(str(CASES), "--collect-only", "-q"),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
        env=_inner_env(),
    )
    ids = [
        line.strip()
        for line in r.stdout.splitlines()
        if line.strip().startswith("tests/kirigami_qml_cases.py::")
    ]
    assert r.returncode == 0 and ids, f"QML case collection failed:\n{r.stdout}\n{r.stderr}"
    return ids


def _passed_ids(nodeids: list[str], stdout: str) -> set[str]:
    """The cases whose PASSED line made it out of the subprocess."""
    return {n for n in nodeids if f"{n} PASSED" in stdout}


def _run_batch(nodeids: list[str]) -> tuple[set[str], int, str]:
    """Run one batch; return (passed ids, returncode, combined output)."""
    budget = max(CASE_TIMEOUT, BATCH_SECONDS_PER_CASE * len(nodeids))
    try:
        r = subprocess.run(
            _base_cmd(*nodeids, "-v", "--tb=short"),
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=budget,
            env=_inner_env(),
        )
        out = r.stdout + r.stderr
        return _passed_ids(nodeids, out), r.returncode, out
    except subprocess.TimeoutExpired as e:
        out = f"TIMEOUT after {budget}s\n{e.stdout or ''}{e.stderr or ''}"
        return _passed_ids(nodeids, out if isinstance(out, str) else str(out)), -1, out


def _run_one(nodeid: str) -> tuple[str, bool, int, str]:
    """Run one case; passed iff its PASSED line printed (teardown may abort after)."""
    try:
        r = subprocess.run(
            _base_cmd(nodeid, "-v", "--tb=short"),
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=CASE_TIMEOUT,
            env=_inner_env(),
        )
        passed = " PASSED" in r.stdout
        return nodeid, passed, r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = f"TIMEOUT after {CASE_TIMEOUT}s\n{e.stdout or ''}{e.stderr or ''}"
        return nodeid, False, -1, out if isinstance(out, str) else str(out)


def _run_unit(nodeids: list[str]) -> tuple[str, bool, int, str]:
    """One unit of work: a batch, with lost cases re-run one by one.

    Returns the same tuple shape as `_run_one` (a failed unit reports only
    the cases that failed, and their output).
    """
    passed, rc, out = _run_batch(nodeids)
    lost = [n for n in nodeids if n not in passed]
    if not lost:
        return "+".join(nodeids), True, rc, out

    warnings.warn(
        f"QML batch aborted (rc={rc}), re-ran {len(lost)} of {len(nodeids)} "
        f"case(s) in isolation: {', '.join(n.split('::')[-1] for n in lost)}",
        stacklevel=1,
    )
    failures: list[tuple[str, int, str]] = []
    for nodeid in lost:
        nodeid, ok, rc, case_out = _run_one(nodeid)
        if not ok:
            failures.append((nodeid, rc, case_out))
    if failures:
        nodeid, rc, case_out = failures[0]
        report = case_out
        if len(failures) > 1:
            report += "\n".join(f"--- {n} (rc={c}) ---\n{o[-6000:]}" for n, c, o in failures[1:])
        return nodeid, False, rc, report
    return "+".join(nodeids), True, rc, out


@pytest.mark.qml
def test_qml_suite_isolated():
    ids = _collect_ids()
    assert len(ids) >= 50, f"only {len(ids)} QML cases collected, expected 80+"
    batches = [ids[i : i + BATCH] for i in range(0, len(ids), BATCH)]
    failures: list[tuple[str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for nodeid, passed, rc, out in pool.map(_run_unit, batches):
            if not passed:
                failures.append((nodeid, rc, out))
    if failures:
        report = "\n".join(f"--- {n} (rc={c}) ---\n{o[-6000:]}" for n, c, o in failures)
        raise AssertionError(f"{len(failures)}/{len(ids)} QML cases failed:\n{report}")
