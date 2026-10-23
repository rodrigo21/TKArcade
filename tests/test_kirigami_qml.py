"""QML suite driver: cases run in short-lived, isolated subprocesses.

kirigami_qml_cases.py aborts when its cases share one process (Qt 6.12
GC/shiboken teardown of accumulated QML engines; measured: Fatal error:
Aborted after ~20 cases). Every case passes in isolation. A few cases
additionally segfault during interpreter teardown *after* passing (exit
139 with PASSED already printed).

So the driver collects the case ids and runs them in **batches** of
`BATCH` cases per `pytest` subprocess, one subprocess per CPU by
default. A case counts as passed when its PASSED line printed, which
pytest flushes per write, so the lines before an abort survive. A batch
whose abort swallowed cases (its PASSED lines are incomplete) is not
trusted: the missing cases are re-run individually, and only those still
lacking a PASSED line fail — real regressions fail assertions before
PASSED, so nothing is masked.

Tuning knobs, all optional:

    TKARCADE_QML_BATCH      cases per subprocess (default follows the
                            worker count: 8 serial, 4 up to four, 2
                            above -- smaller batches lose less to an
                            abort and balance better across workers)
    TKARCADE_QML_WORKERS    parallel subprocesses (default: one per CPU,
                            capped at 8; each offscreen Qt process costs
                            ~200MB. Parallel runs can flake the
                            timing-sensitive cases under load: set 1 to
                            run one at a time)

Verbose progress (`-v` prints one line per finished batch):
    python -m pytest tests/test_kirigami_qml.py -v -rP

A failing batch reports a bounded tail; the full output goes to
`/tmp/tkarcade-qml-fail-*.log` (path printed in the assertion).

Single-case dev loop:
    python -m pytest "tests/kirigami_qml_cases.py::<name>" -o python_files="*.py"

Fast loop without the QML suite (~15s):
    python -m pytest tests/ -q -m "not qml"
"""

import concurrent.futures
import os
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parent / "kirigami_qml_cases.py"
ROOT = Path(__file__).resolve().parent.parent
WORKERS_MAX = 8  # each offscreen Qt subprocess holds ~200MB


def _default_workers() -> int:
    """One subprocess per CPU, capped at WORKERS_MAX."""
    return max(1, min(os.cpu_count() or 1, WORKERS_MAX))


WORKERS = max(1, int(os.environ.get("TKARCADE_QML_WORKERS") or _default_workers()))


def _default_batch(workers: int) -> int:
    """Cases per subprocess, scaled down as workers go up.

    Serial, a big batch amortizes the ~0.7s pytest start; with several
    workers the tail latency and the cases lost to an abort dominate, so
    four and then two pay off (measured on 4 cores: 8 -> 70s, 6 -> 59s,
    4 -> 59s, 2 -> 62s with zero aborts).
    """
    if workers <= 2:
        return 8
    if workers <= 4:
        return 4
    return 2


# Sized well under the ~20-case abort threshold so a batch normally
# finishes; anything it does lose is re-run individually.
BATCH = max(1, int(os.environ.get("TKARCADE_QML_BATCH") or _default_batch(WORKERS)))
CASE_TIMEOUT = 240  # seconds a single case may take before we call it hung
BATCH_SECONDS_PER_CASE = 30  # headroom per case before a batch gives up

# A failing suite can lose dozens of batches at once; the assertion keeps a
# tail per failure and points at a log with the rest, so one bad run does not
# flood the caller's context.
REPORT_CHARS = 1000  # tail kept per failure inside a unit report
REPORT_CASES = 2  # failures rendered per unit report
REPORT_UNITS = 3  # failed units rendered in the final assertion


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


def _write_failure_log(entries: list[tuple[str, int, str]]) -> Path:
    """Persist the full failure output so the assertion only carries a tail."""
    fd, name = tempfile.mkstemp(prefix="tkarcade-qml-fail-", suffix=".log")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for nodeid, rc, out in entries:
            fh.write(f"--- {nodeid} (rc={rc}) ---\n{out}\n")
    return Path(name)


def _failure_tail(entries: list[tuple[str, int, str]], limit: int) -> str:
    """Bounded block per failure: the assertion sits at the end of the output."""
    shown = entries[:limit]
    text = "\n".join(
        f"--- {nodeid} (rc={rc}) ---\n{out[-REPORT_CHARS:]}" for nodeid, rc, out in shown
    )
    if len(entries) > limit:
        text += f"\n... and {len(entries) - limit} more case(s), full output in the log."
    return text


def _run_unit(nodeids: list[str]) -> tuple[str, bool, int, str, float]:
    """One unit of work: a batch, with lost cases re-run one by one.

    Returns the same tuple shape as `_run_one` plus the wall time. A failed
    unit reports only its failed cases: a bounded tail in the assertion and a
    `/tmp/tkarcade-qml-fail-*.log` path with the full output.
    """
    started = time.perf_counter()
    passed, rc, out = _run_batch(nodeids)
    lost = [n for n in nodeids if n not in passed]
    if not lost:
        return "+".join(nodeids), True, rc, out, time.perf_counter() - started

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
        nodeid, rc, _ = failures[0]
        log = _write_failure_log(failures)
        report = f"full output: {log}\n{_failure_tail(failures, REPORT_CASES)}"
        return nodeid, False, rc, report, time.perf_counter() - started
    return "+".join(nodeids), True, rc, out, time.perf_counter() - started


@pytest.mark.qml
def test_qml_suite_isolated(request):
    ids = _collect_ids()
    assert len(ids) >= 50, f"only {len(ids)} QML cases collected, expected 80+"
    batches = [ids[i : i + BATCH] for i in range(0, len(ids), BATCH)]
    verbose = request.config.getoption("verbose") > 0
    failures: list[tuple[str, int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = pool.map(_run_unit, batches)
        for index, (nodeid, passed, rc, out, seconds) in enumerate(results, 1):
            if verbose:
                first = nodeid.split("+")[0].split("::")[-1]
                print(
                    f"QML batch {index}/{len(batches)} ({first}...): "
                    f"{'ok' if passed else 'FAIL'} ({seconds:.1f}s)",
                    flush=True,
                )
            if not passed:
                failures.append((nodeid, rc, out))
    if failures:
        report = "\n".join(out for _, _, out in failures[:REPORT_UNITS])
        if len(failures) > REPORT_UNITS:
            report += f"\n... and {len(failures) - REPORT_UNITS} more unit(s) failed."
        raise AssertionError(f"{len(failures)}/{len(batches)} QML batches failed:\n{report}")
