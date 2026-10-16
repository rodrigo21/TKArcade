"""Standalone settings editor for subprocess use.

The launcher spawns this instead of opening Qt in-process so the dialog
gets a sanitized environment (Steam pollutes LD_LIBRARY_PATH, which
breaks Qt style/theme plugin loading and falls back to Fusion).

Protocol: prints one JSON line {"outcome": ..., "appid": ...} on stdout.
Exit 0 = outcome delivered (launch/saved/cancelled), 2 = unavailable
(no PySide6 or display). Anything else (including tracebacks) means
internal error. Anything on stderr is diagnostic noise the parent logs.

Usage: python -m tkarcade.gui.edit [--appid ID] [--pick]
       [--can-launch | --no-can-launch] [--menu]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys


def _ensure_qapp(tool: str) -> bool:
    """Lazy Qt import + display check. False means 'unavailable'."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        print(f"tkarcade: {tool} needs PySide6 installed", file=sys.stderr)
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(f"tkarcade: {tool} needs a display", file=sys.stderr)
        return False
    return True


def menu_timeout(appid: str) -> int:
    """Countdown seconds for the pre-launch menu (0 = wait forever)."""
    from .. import config as cfgmod

    try:
        return max(0, int(cfgmod.load_effective(appid).general.menu_timeout or 0))
    except Exception:
        return 0


def game_name(appid: str) -> str:
    """Display name for the window title ('' when unknown)."""
    from .. import steam as steammod

    try:
        names = {a: n for a, n in steammod.list_games()}
        names.update(steammod.local_names())
    except Exception:
        return ""
    return names.get(appid, "")


def run_editor(appid: str, menu: bool = False, can_launch: bool = True, pick: bool = False):
    """Show the editor (or the pre-launch menu); returns (outcome, appid).

    Outcomes: 'launch', 'saved', 'cancelled' or 'unavailable' (the QML
    side could not be created). A window closed some other way counts as
    'cancelled': never launch on unknown user intent.
    """
    from PySide6.QtWidgets import QApplication

    from .i18n import install_translations, preferred_language
    from .kirigami_app import build_engine

    app = QApplication.instance() or QApplication(sys.argv)
    install_translations(app, preferred_language())
    engine, _model, _filter = build_engine("Editor.qml")
    roots = engine.rootObjects()
    if not roots:
        print("tkarcade: could not load the editor interface", file=sys.stderr)
        return "unavailable", appid
    root = roots[0]
    result = {"outcome": "cancelled", "appid": appid}

    def on_decided(outcome, decided_appid) -> None:
        result["outcome"] = str(outcome or "cancelled")
        result["appid"] = str(decided_appid or appid)
        app.quit()

    root.decided.connect(on_decided)
    root.setProperty("mode", "menu" if menu else "edit")
    root.setProperty("appid", (appid or "").strip())
    root.setProperty("name", game_name(appid))
    root.setProperty("canLaunch", bool(can_launch))
    root.setProperty("pick", bool(pick))
    root.setProperty("timeout", menu_timeout(appid) if menu else 0)
    # Editor.qml is an invisible 1x1 host: start() is what creates the real
    # window (settings, picker or pre-launch menu). Without this call the
    # child opens nothing and app.exec() waits forever -- the CLI --edit and
    # --menu flows hung until Ctrl+C while the QML harness (which calls
    # start() itself) stayed green.
    root.start()
    app.exec()
    return result["outcome"], result["appid"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tkarcade.gui.edit")
    p.add_argument("--appid", default="")
    p.add_argument("--pick", action="store_true", help="show a game picker when no AppID is given")
    p.add_argument(
        "--can-launch",
        dest="can_launch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="hide the launch button when there is no game command to run",
    )
    p.add_argument(
        "--menu",
        action="store_true",
        help="show the Launch / Settings / Cancel menu instead of the editor",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tool = "--menu" if args.menu else "--edit"
    if not _ensure_qapp(tool):
        return 2
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    appid = (args.appid or "").strip()
    outcome, picked = run_editor(
        appid,
        menu=args.menu,
        can_launch=args.can_launch,
        pick=bool(args.pick and not appid),
    )
    if outcome == "unavailable":
        return 2
    print(json.dumps({"outcome": outcome, "appid": picked}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
