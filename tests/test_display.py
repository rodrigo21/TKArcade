"""Display mode backend: parsing, apply/restore, provider detection."""

import os
import shutil
import stat

from tkarcade.backends import display as D


def _bindir(tmp_path, monkeypatch):
    bindir = tmp_path / "dispbin"
    bindir.mkdir(exist_ok=True)

    def _make(name, body):
        path = bindir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    _make(
        "kscreen-doctor",
        '#!/bin/sh\nif [ "$1" = "-o" ]; then\n'
        "printf 'Output: 1 DP-3 04cbfa0a-uuid\\n\\tenabled\\n\\tconnected\\n\\tpriority 1\\n"
        "\\tModes:  1:2560x1440@120.00!  2:\\033[32m2560x1440@164.96*\\033[0m"
        "  3:1920x1080@60.00\\n"
        "Output: 2 HDMI-1 other-uuid\\n\\tdisabled\\n\\tdisconnected\\n"
        "\\tModes:  1:1920x1080@60.00\\n'\n"
        'exit 0\nfi\necho "$@" >> "$KSCREEN_LOG"\nexit 0\n',
    )
    _make(
        "xrandr",
        '#!/bin/sh\nif [ "$1" = "--query" ]; then\n'
        "printf 'DP-3 connected primary 2560x1440+0+0\\n"
        "   2560x1440    164.96*+  60.00\\n   1920x1080    60.00\\n"
        "HDMI-1 disconnected\\n'\n"
        'exit 0\nfi\necho "$@" >> "$XRANDR_LOG"\nexit 0\n',
    )
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    (tmp_path / "kscreen.log").write_text("")
    (tmp_path / "xrandr.log").write_text("")
    monkeypatch.setenv("KSCREEN_LOG", str(tmp_path / "kscreen.log"))
    monkeypatch.setenv("XRANDR_LOG", str(tmp_path / "xrandr.log"))
    return bindir


def _logs(tmp_path):
    k = (tmp_path / "kscreen.log").read_text().strip().splitlines()
    x = (tmp_path / "xrandr.log").read_text().strip().splitlines()
    return [ln for ln in k if ln], [ln for ln in x if ln]


def test_parse_mode():
    assert D.parse_mode("1920x1080") == (1920, 1080, None)
    assert D.parse_mode("1920x1080@60") == (1920, 1080, 60.0)
    assert D.parse_mode("2560x1440@164.96") == (2560, 1440, 164.96)
    for bad in ("", "1920", "1920x", "x1080", "abc", "1920x1080@", "0x1080", "-1x5"):
        assert D.parse_mode(bad) is None


def test_detect_provider(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    for var in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    assert D.detect_provider("plasma") == "plasma"
    assert D.detect_provider("off") == "off"
    assert D.detect_provider("bogus") == "off"
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert D.detect_provider("auto") == "plasma"
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert D.detect_provider("auto") == "gnome"
    monkeypatch.delenv("XDG_CURRENT_DESKTOP")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/xrandr" if name == "xrandr" else None)
    assert D.detect_provider("auto") == "x11"


def test_plasma_apply_and_restore(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    s = D.DisplaySession(provider="plasma", mode="1920x1080@60")
    assert s.start() == []
    s.stop()
    k, _x = _logs(tmp_path)
    assert k == ["output.DP-3.mode.3", "output.DP-3.mode.2"]


def test_plasma_explicit_output_and_idempotent(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    s = D.DisplaySession(provider="plasma", output="DP-3", mode="1920x1080")
    assert s.start() == []
    assert s.start() == []  # second start is a no-op
    k, _x = _logs(tmp_path)
    assert k == ["output.DP-3.mode.3"]
    s.stop()


def test_plasma_unknown_output_and_unoffered_mode(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    assert "not found" in D.DisplaySession("plasma", "NOPE", "1920x1080").start()[0]
    assert "not offered" in D.DisplaySession("plasma", "DP-3", "640x480").start()[0]
    k, _x = _logs(tmp_path)
    assert k == []


def test_empty_and_invalid_mode_do_nothing(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    assert D.DisplaySession("plasma", "", "").start() == []
    warns = D.DisplaySession("plasma", "", "bogus").start()
    assert warns and "invalid display mode" in warns[0]
    k, _x = _logs(tmp_path)
    assert k == []


def test_unsupported_and_missing_binary(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    assert "not supported yet" in D.DisplaySession("gnome", "", "1920x1080").start()[0]
    monkeypatch.setenv("PATH", str(tmp_path))  # no helpers on PATH
    assert "not found" in D.DisplaySession("plasma", "", "1920x1080").start()[0]


def test_x11_apply_and_restore(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    s = D.DisplaySession(provider="x11", mode="1920x1080@60")
    assert s.start() == []
    s.stop()
    _k, x = _logs(tmp_path)
    assert x[0] == "--output DP-3 --mode 1920x1080 --rate 60"
    assert x[1] == "--output DP-3 --mode 2560x1440 --rate 164.96"


def test_x11_context_manager_restores(tmp_path, monkeypatch):
    _bindir(tmp_path, monkeypatch)
    with D.DisplaySession(provider="x11", output="DP-3", mode="1920x1080"):
        pass
    _k, x = _logs(tmp_path)
    assert len(x) == 2 and "1920x1080" in x[0] and "2560x1440" in x[1]


def test_display_fields_collect_and_populate(qt_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.game_dialog import GameDialog

    cfg = C.GameConfig()
    cfg.general.appid = "161"
    cfg.display.provider = "plasma"
    cfg.display.output = "DP-3"
    cfg.display.mode = "1920x1080@60"
    C.save(cfg)
    d = GameDialog(None, "161", "T")
    assert d.e_dout.text() == "DP-3"
    assert d.e_dmode.currentText() == "1920x1080@60"
    assert d.cb_dprov.currentData() == "plasma"
    d.e_dmode.setCurrentText("1280x720")
    d._collect()
    assert d.cfg.display.mode == "1280x720"
    d.accept()
    assert C.load("161").display.mode == "1280x720"
    d.close()


def test_offered_modes_lists_backend_modes(tmp_path, monkeypatch):
    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    modes = D.offered_modes("plasma", "")
    assert modes == [
        (2, "2560x1440@164.96", True),
        (1, "2560x1440@120", False),
        (3, "1920x1080@60", False),
    ]
    assert D.offered_modes("plasma", "NOPE") == modes  # unknown output falls back
    assert D.offered_modes("gnome", "") == []
    assert D.offered_modes("x11", "") != []


def test_mode_picker_lists_offered_and_keeps_manual(qt_app, xdg_env, monkeypatch):
    from tkarcade import config as C
    from tkarcade.backends import display as dispmod
    from tkarcade.gui.game_dialog import GameDialog

    monkeypatch.setattr(dispmod, "offered_modes", lambda *a: [(None, "1920x1080@60", False)])
    cfg = C.GameConfig()
    cfg.general.appid = "163"
    cfg.display.mode = "1280x720@60"
    C.save(cfg)
    d = GameDialog(None, "163", "T")
    assert d.e_dmode.currentText() == "1280x720@60"  # manual value survives refill
    d.close()


def test_restore_rc_failure_warns(tmp_path, monkeypatch, caplog):
    import logging
    import subprocess

    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    s = D.DisplaySession(provider="plasma", mode="1920x1080@60")
    assert s.start() == []
    assert s._prev is not None

    def boom(*a, **k):
        return subprocess.CompletedProcess(a[0], 1, "", "nope")

    monkeypatch.setattr(D.subprocess, "run", boom)
    with caplog.at_level(logging.WARNING, logger="tkarcade.display"):
        s.stop()
    assert any("restore" in r.message and "failed" in r.message for r in caplog.records)


def test_no_current_mode_warns_without_restore(tmp_path, monkeypatch, caplog):
    import logging
    import subprocess

    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    real_run = D.subprocess.run

    def no_star(cmd, **k):
        if cmd[:2] == ["kscreen-doctor", "-o"]:
            out = real_run(cmd, **k)
            text = out.stdout.replace("*", "")
            return subprocess.CompletedProcess(cmd, 0, text, "")
        return real_run(cmd, **k)

    unhealthy = D.DisplaySession(provider="plasma", mode="1920x1080@60")
    monkeypatch.setattr(D.subprocess, "run", no_star)
    with caplog.at_level(logging.WARNING, logger="tkarcade.display"):
        assert unhealthy.start() == []
    assert any("without restore" in r.message for r in caplog.records)
    assert unhealthy._prev is None


def test_dip_candidate_prefers_same_res_lower_rate():
    from tkarcade.backends.display import _dip_candidate, _Mode

    modes = [
        _Mode(1, 2560, 1440, 120.0, False),
        _Mode(2, 2560, 1440, 164.96, True),
        _Mode(3, 1920, 1080, 60.0, False),
    ]
    assert _dip_candidate(modes, modes[1]) == modes[0]
    assert _dip_candidate([modes[1]], modes[1]) is None


def test_same_mode_dips_down_and_back(tmp_path, monkeypatch):

    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    slept = []
    monkeypatch.setattr(D.time, "sleep", lambda s: slept.append(s))
    s = D.DisplaySession(provider="plasma", mode="2560x1440@164.96")
    assert s.start() == []
    k, _x = _logs(tmp_path)
    assert k == ["output.DP-3.mode.1", "output.DP-3.mode.2"]
    assert slept == [D.DIP_SECONDS]
    s.stop()
    k, _x = _logs(tmp_path)
    assert k[-1] == "output.DP-3.mode.2"


def test_same_mode_x11_dips_down_and_back(tmp_path, monkeypatch):

    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    slept = []
    monkeypatch.setattr(D.time, "sleep", lambda s: slept.append(s))
    s = D.DisplaySession(provider="x11", mode="2560x1440")
    assert s.start() == []
    _k, x = _logs(tmp_path)
    # Same resolution, lower refresh: no resolution flicker on the dip.
    assert x[0] == "--output DP-3 --mode 2560x1440 --rate 60"
    assert slept == [D.DIP_SECONDS]


def test_display_dip_seconds_roundtrip_and_clamp(xdg_env):
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "168"
    cfg.display.mode = "1920x1080@60"
    cfg.display.dip_seconds = 7
    C.save(cfg)
    assert C.load("168").display.dip_seconds == 7
    C.game_file("169").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("169").write_text(
        '[general]\nappid = "169"\n[display]\nmode = "1920x1080@60"\ndip_seconds = 99\n',
        encoding="utf-8",
    )
    assert C.load("169").display.dip_seconds == 15
    C.game_file("170").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("170").write_text(
        '[general]\nappid = "170"\n[display]\nmode = "x"\ndip_seconds = "lots"\n',
        encoding="utf-8",
    )
    assert C.load("170").display.dip_seconds == 8


def _flaky_second_apply(monkeypatch, tmp_path):
    """Real binaries, but the 2nd mode-set (the dip target) fails."""
    from types import SimpleNamespace

    from tkarcade.backends import display as D

    real_run = D.subprocess.run
    sets = []

    def flaky(cmd, **kw):
        if isinstance(cmd, list) and any(a.startswith("output.") or a == "--mode" for a in cmd):
            sets.append(" ".join(cmd))
            if len(sets) == 2:
                return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        return real_run(cmd, **kw)

    monkeypatch.setattr(D.subprocess, "run", flaky)
    return sets


def test_partial_dip_restores_plasma(tmp_path, monkeypatch):
    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    _flaky_second_apply(monkeypatch, tmp_path)
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    s = D.DisplaySession(provider="plasma", mode="2560x1440@164.96")
    warnings = s.start()
    assert warnings and "boom" in warnings[0]
    k, _x = _logs(tmp_path)
    # dip applied, target failed, restore re-applied the original (mode 2)
    assert k == ["output.DP-3.mode.1", "output.DP-3.mode.2"]
    assert s._prev is None  # restore consumed it; stop() is a safe no-op
    s.stop()


def test_partial_dip_restores_x11(tmp_path, monkeypatch):
    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    _flaky_second_apply(monkeypatch, tmp_path)
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    s = D.DisplaySession(provider="x11", mode="2560x1440")
    warnings = s.start()
    assert warnings and "boom" in warnings[0]
    _k, x = _logs(tmp_path)
    assert x[0] == "--output DP-3 --mode 2560x1440 --rate 60"
    assert x[-1] == "--output DP-3 --mode 2560x1440 --rate 164.96"
    assert s._prev is None
    s.stop()


def test_sleep_interrupted_restores_plasma(tmp_path, monkeypatch):
    import pytest

    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)

    def boom(s):
        raise KeyboardInterrupt()

    monkeypatch.setattr(D.time, "sleep", boom)
    s = D.DisplaySession(provider="plasma", mode="2560x1440@164.96")
    with pytest.raises(KeyboardInterrupt):
        s.start()
    k, _x = _logs(tmp_path)
    assert k == ["output.DP-3.mode.1", "output.DP-3.mode.2"]
    assert s._prev is None


def test_xrandr_keeps_every_rate_on_one_line(tmp_path, monkeypatch):
    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    modes = D.current_x11()["DP-3"]
    same = sorted(m.rate for m in modes if (m.w, m.h) == (2560, 1440))
    assert same == [60.0, 164.96]
    assert sum(1 for m in modes if m.current) == 1


def test_dip_seconds_plumbing(tmp_path, monkeypatch):
    from tkarcade.backends import display as D

    _bindir(tmp_path, monkeypatch)
    slept = []
    monkeypatch.setattr(D.time, "sleep", lambda s: slept.append(s))
    s = D.DisplaySession(provider="plasma", mode="2560x1440@164.96", dip_seconds=5)
    assert s.start() == []
    assert slept == [5]
    s.stop()
