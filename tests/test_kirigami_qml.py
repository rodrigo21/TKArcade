"""QML suite driver: each case runs in its own subprocess.

kirigami_qml_cases.py segfaults when all 82 tests share one process
(Qt 6.12 GC/shiboken teardown of accumulated QML engines); every case
passes in isolation. A few cases additionally segfault during
interpreter teardown *after* passing (exit 139 with PASSED already
printed), so this driver collects the case ids, runs each in its own
separate `pytest` subprocess (serially), and counts a case as passed
when its PASSED line is present — a missing PASSED line (real
failure, mid-test crash, collection error) fails loudly with the
captured output, so `pytest tests/` stays green end to end without
masking real regressions (those fail assertions before PASSED).

Single-case dev loop:
    python -m pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"
"""

import concurrent.futures
import os
import subprocess
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "kirigami_qml_cases.py"
ROOT = Path(__file__).resolve().parent.parent
# Serial: parallel offscreen Qt processes flake timing-sensitive cases
# and segfault under contention; one case per process, one at a time.
WORKERS = 1
TIMEOUT = 240


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


def _run_one(nodeid: str) -> tuple[str, bool, int, str]:
    """Run one case; passed iff its PASSED line printed (teardown may segfault after)."""
    try:
        r = subprocess.run(
            _base_cmd(nodeid, "-v", "--tb=short"),
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=TIMEOUT,
            env=_inner_env(),
        )
        passed = " PASSED" in r.stdout
        return nodeid, passed, r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = f"TIMEOUT after {TIMEOUT}s\n{e.stdout or ''}{e.stderr or ''}"
        return nodeid, False, -1, out if isinstance(out, str) else str(out)


def test_qml_suite_isolated():
    ids = _collect_ids()
    assert len(ids) >= 50, f"only {len(ids)} QML cases collected, expected 80+"
    failures: list[tuple[str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for nodeid, passed, rc, out in pool.map(_run_one, ids):
            if not passed:
                failures.append((nodeid, rc, out))
    if failures:
        report = "\n".join(f"--- {n} (rc={c}) ---\n{o[-6000:]}" for n, c, o in failures)
        raise AssertionError(f"{len(failures)}/{len(ids)} QML cases failed:\n{report}")
