"""Standalone editor child process: flags, protocol line, availability."""

import json

import pytest


@pytest.fixture(autouse=True)
def _no_style_leak(monkeypatch):
    """`main()` pins QT_QUICK_CONTROLS_STYLE in os.environ, as the product does.

    Left alone it leaks into the rest of the session, and the QML driver's
    child processes then run the desktop style: its menu fade keeps `opened`
    false through a tight settle loop, so the tray case failed inside
    makepkg's check() while standalone runs (default style) stayed green.
    """
    monkeypatch.delenv("QT_QUICK_CONTROLS_STYLE", raising=False)


def test_parse_args_defaults():
    from tkarcade.gui import edit

    args = edit.parse_args([])
    assert args.appid == ""
    assert args.pick is False
    assert args.can_launch is True
    assert args.menu is False


def test_parse_args_flags():
    from tkarcade.gui import edit

    args = edit.parse_args(["--appid", "7", "--pick", "--menu", "--no-can-launch"])
    assert (args.appid, args.pick, args.menu) == ("7", True, True)
    assert args.can_launch is False


def test_main_without_a_display_is_unavailable(monkeypatch, capsys):
    from tkarcade.gui import edit

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert edit.main(["--appid", "7"]) == 2
    assert "needs a display" in capsys.readouterr().err


def test_main_prints_the_protocol_line(monkeypatch, capsys):
    """One JSON line on stdout, exit 0 -- what run_editor_menu parses."""
    from tkarcade.gui import edit

    monkeypatch.setattr(edit, "_ensure_qapp", lambda tool: True)
    seen = {}

    def fake_run_editor(appid, menu=False, can_launch=True, pick=False):
        seen.update(appid=appid, menu=menu, can_launch=can_launch, pick=pick)
        return "launch", "588950"

    monkeypatch.setattr(edit, "run_editor", fake_run_editor)
    assert edit.main(["--appid", "7", "--menu"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out.splitlines()[-1]) == {"outcome": "launch", "appid": "588950"}
    assert seen == {"appid": "7", "menu": True, "can_launch": True, "pick": False}


def test_main_asks_for_the_picker_only_without_an_appid(monkeypatch, capsys):
    from tkarcade.gui import edit

    monkeypatch.setattr(edit, "_ensure_qapp", lambda tool: True)
    seen = {}

    def fake_run_editor(appid, menu=False, can_launch=True, pick=False):
        seen["pick"] = pick
        return "cancelled", appid

    monkeypatch.setattr(edit, "run_editor", fake_run_editor)
    assert edit.main(["--pick"]) == 0
    assert seen["pick"] is True
    assert edit.main(["--appid", "9", "--pick"]) == 0
    assert seen["pick"] is False
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["outcome"] == "cancelled"


def test_main_reports_unavailable_when_the_ui_cannot_load(monkeypatch):
    from tkarcade.gui import edit

    monkeypatch.setattr(edit, "_ensure_qapp", lambda tool: True)
    monkeypatch.setattr(edit, "run_editor", lambda *a, **k: ("unavailable", ""))
    assert edit.main(["--appid", "7"]) == 2


def test_run_editor_actually_starts_the_qml_host(qgui_app, xdg_env, monkeypatch):
    """The real --edit/--menu path must call Editor.qml's start().

    Regression: run_editor set the properties and went straight into
    app.exec(), never calling start(), so the CLI flows opened nothing and
    hung until Ctrl+C. The QML harness (kirigami_qml_cases) calls start()
    itself, which is why the suite stayed green. start() is what fills the
    host's `settings` property.
    """
    from PySide6.QtCore import QTimer

    from tkarcade.gui import edit, kirigami_app

    captured = {}
    real_build = kirigami_app.build_engine

    def build(name="main.qml"):
        engine, model, game_filter = real_build(name)
        roots = engine.rootObjects()
        captured["engine"] = engine  # keeps root (and its windows) alive
        captured["root"] = roots[0] if roots else None
        return engine, model, game_filter

    # run_editor imports build_engine from the module, so patching it here
    # reaches the production call site.
    monkeypatch.setattr(kirigami_app, "build_engine", build)
    # start() builds the window before app.exec(); a watchdog quit lets the
    # test inspect the host without waiting for a user decision.
    QTimer.singleShot(0, qgui_app.quit)
    edit.run_editor("7", menu=False, can_launch=True)
    root = captured["root"]
    assert root is not None, "Editor.qml did not load"
    assert root.property("settings") is not None, "Editor.qml start() never ran"


def test_menu_timeout_comes_from_the_config(xdg_env):
    from tkarcade import config as C
    from tkarcade.gui import edit

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.menu_timeout = 7
    C.save(cfg)
    assert edit.menu_timeout("local-doom") == 7
    assert edit.menu_timeout("nope") == 0


def test_game_name_is_empty_for_unknown_appids(xdg_env):
    from tkarcade.gui import edit

    assert edit.game_name("nope") == ""
