"""Running-game records: who is playing, and how Terminate reaches them."""

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from tkarcade import running, xdg

SLEEPER = "import time; time.sleep(60)"


def _spawn(code=SLEEPER):
    """A stand-in launcher that is its own session (like the GUI spawn)."""
    return subprocess.Popen([sys.executable, "-c", code], start_new_session=True)


def _wait_dead(pid, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if running.process_start_time(pid) is None:
            return True
        time.sleep(0.02)
    return running.process_start_time(pid) is None


def _write_record(appid, pid):
    """The launcher's file format, written for a foreign process."""
    path = running.record_path(appid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "appid": appid,
                "pid": pid,
                "start": running.process_start_time(pid),
                "started": time.time(),
            }
        )
    )
    return path


@pytest.fixture
def launcher(xdg_env):
    procs = []

    def spawn(code=SLEEPER):
        proc = _spawn(code)
        procs.append(proc)
        return proc

    yield spawn
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


def test_record_marks_this_process(xdg_env):
    with running.Record("local-doom") as rec:
        assert rec.pid == os.getpid()
        data = running.read("local-doom")
        assert data["appid"] == "local-doom"
        assert data["pid"] == os.getpid()
        assert data["start"] == running.process_start_time(os.getpid())
        assert "local-doom" in running.list_running()
    assert running.read("local-doom") is None
    assert not running.record_path("local-doom").exists()


def test_record_path_is_safe(xdg_env):
    path = running.record_path("../../evil")
    assert path.parent == xdg.app_state_dir() / "running"
    assert "/" not in path.name


def test_read_drops_stale_record(xdg_env, launcher):
    proc = launcher()
    pid = proc.pid
    _write_record("11", pid)
    proc.kill()
    proc.wait(timeout=10)
    assert running.read("11") is None
    assert not running.record_path("11").exists()


def test_read_rejects_a_reused_pid(xdg_env):
    path = _write_record("12", os.getpid())
    path.write_text(json.dumps({**json.loads(path.read_text()), "start": -1}))
    assert running.read("12") is None
    assert not path.exists()


def test_sweep_keeps_live_records(xdg_env, launcher):
    proc = launcher()
    _write_record("13", proc.pid)
    running.record_path("14").write_text("{not json")
    running.sweep()
    assert running.read("13") is not None
    assert sorted(running.list_running()) == ["13"]
    assert not running.record_path("14").exists()


def test_terminate_signals_the_launcher(xdg_env, launcher):
    proc = launcher()
    _write_record("15", proc.pid)
    record = running.terminate("15")
    assert record is not None and record["pid"] == proc.pid
    assert proc.wait(timeout=10) == -signal.SIGTERM


def test_terminate_nothing_running(xdg_env):
    assert running.terminate("16") is None


def test_kill_takes_the_whole_process_group(xdg_env, launcher, tmp_path):
    # A launcher that ignores SIGTERM and already spawned the game
    # (the standalone game here, with a plain shell shim in between):
    # both live in the launcher's session, so the SIGKILL reaches both.
    marker = tmp_path / "game.pid"
    code = (
        "import signal, subprocess, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"child = subprocess.Popen([sys.executable, '-c', {SLEEPER!r}])\n"
        f"open({str(marker)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    proc = launcher(code)
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    game_pid = int(marker.read_text())
    _write_record("17", proc.pid)
    record = running.terminate("17")
    assert record is not None
    time.sleep(0.2)
    assert proc.poll() is None  # SIGTERM ignored, as designed
    assert running.kill(record) is True
    assert proc.wait(timeout=10) == -signal.SIGKILL
    assert _wait_dead(game_pid)


def test_kill_refuses_a_stale_record(xdg_env, launcher):
    proc = launcher()
    _write_record("18", proc.pid)
    proc.kill()
    proc.wait(timeout=10)
    record = json.loads(running.record_path("18").read_text())
    assert running.kill(record) is False
