"""Kirigami game list model (QtCore only, no widgets)."""

import time
from pathlib import Path

from tkarcade import config as C


def test_steam_metadata_fills_only_empty_and_unlocked(qgui_app, xdg_env):
    """A new Steam game absorbs the store answer; typed and locked stay."""
    from tkarcade.gui.model import _fill_steam_metadata

    cfg = C.GameConfig()
    cfg.general.appid = "steam-620"
    cfg.metadata.developer = "Typed Studio"
    cfg.metadata.locked = "publisher"
    payload = {
        "description": "Store synopsis.",
        "developer": "Store Studio",
        "publisher": "Store Publisher",
        "genre": "Action",
        "series": "",
        "age_ratings": ["PEGI 12", "Bogus 99"],
        "date": "1993-12-10",
        "tags": ["Action", "Action", "Single-player"],
    }
    assert _fill_steam_metadata(cfg, payload) is True
    assert cfg.metadata.description == "Store synopsis."
    assert cfg.metadata.developer == "Typed Studio"
    assert cfg.metadata.publisher == ""
    assert cfg.metadata.genre == "Action"
    assert cfg.metadata.series == ""
    assert cfg.metadata.age_ratings == ["PEGI 12"]
    assert cfg.metadata.date == "1993-12-10"
    assert cfg.metadata.tags == ["Action", "Single-player"]
    # Second pass changes nothing: only the locked field is still empty.
    assert _fill_steam_metadata(cfg, payload) is False


def test_steam_metadata_drops_an_invalid_date(qgui_app, xdg_env):
    """A date the config cannot store stays out of the auto-fill."""
    from tkarcade.gui.model import _fill_steam_metadata

    cfg = C.GameConfig()
    cfg.general.appid = "steam-70"
    assert _fill_steam_metadata(cfg, {"date": "soon"}) is False
    assert cfg.metadata.date == ""


def _model(qgui_app):
    from tkarcade.gui.model import GameListModel

    return GameListModel()


def _rows(model):
    return [
        (
            model.data(model.index(i, 0), model.IdRole),
            model.data(model.index(i, 0), model.NameRole),
            model.data(model.index(i, 0), model.OriginRole),
            model.data(model.index(i, 0), model.PlayedRole),
            model.data(model.index(i, 0), model.TierRole),
        )
        for i in range(model.rowCount())
    ]


def test_model_lists_steam_and_local_sorted(qgui_app, xdg_env):
    steam = C.GameConfig()
    steam.general.appid = "213"
    C.save(steam)
    local = C.GameConfig()
    local.general.appid = "local-zebra"
    local.general.name = "Zebra"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    rows = _rows(_model(qgui_app))
    assert rows == [
        ("steam-213", "steam-213", "Steam", "—", ""),
        ("local-zebra", "Zebra", "Local", "—", ""),
    ]


def test_reload_drops_the_steam_games_cache(qgui_app, xdg_env, monkeypatch, tmp_path):
    from tkarcade import steam

    root = tmp_path / "steamapps"
    root.mkdir()
    (root / "appmanifest_10.acf").write_text('"AppState"\n{\n"appid" "10"\n}\n')
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    model = _model(qgui_app)
    assert [a for a, _n in steam.list_games()] == ["steam-10"]
    (root / "appmanifest_11.acf").write_text('"AppState"\n{\n"appid" "11"\n}\n')
    model.refresh()
    assert [a for a, _n in steam.list_games()] == ["steam-10"]  # cached
    model.reload()
    assert [a for a, _n in steam.list_games()] == ["steam-10", "steam-11"]
    model._stop_timers()
    model.deleteLater()
    qgui_app.processEvents()


def test_model_add_local_validation(qgui_app, xdg_env, tmp_path):
    model = _model(qgui_app)
    assert model.addLocal("", "/bin/true") == ""
    assert model.addLocal("Doom", "/nonexistent/doom") == ""
    exe = tmp_path / "doom"
    exe.write_text("#!/bin/sh\n")
    first = model.addLocal("Doom", str(exe))
    assert first == "local-doom"
    assert model.addLocal("Doom", str(exe)) == "local-doom-2"
    saved = C.load("local-doom")
    assert (saved.general.name, saved.runtime.type) == ("Doom", "native")
    assert saved.general.custom_executable == str(exe)


def test_model_play_routes(qgui_app, xdg_env, monkeypatch, tmp_path):
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    assert model.play("213") is True
    assert opened == ["steam://rungameid/213"]
    assert L.menu_skip_path("213").exists()
    calls = []
    monkeypatch.setattr(L, "launch_local_detached", lambda appid: calls.append(appid))
    assert model.play("local-doom") is True
    assert calls == ["local-doom"]


def test_launch_local_detached_spawns(xdg_env, monkeypatch):
    import subprocess
    import sys

    from tkarcade import launcher as L

    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or None)
    # A stale system package on PATH must never be the child: the spawn
    # goes through the interpreter that owns this install.
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/tkarcade")
    monkeypatch.setattr(sys, "executable", "/opt/venv/bin/python")
    L.launch_local_detached("local-doom")
    assert L.menu_skip_path("local-doom").exists()  # one-shot skip planted
    (args, kwargs) = calls[0]
    assert args[0] == [
        "/opt/venv/bin/python",
        "-m",
        "tkarcade.launcher",
        "--game-id",
        "local-doom",
    ]
    assert kwargs.get("start_new_session") is True


def test_model_role_names_are_game_prefixed(qgui_app):
    from tkarcade.gui.model import GameListModel

    roles = GameListModel().roleNames()
    assert sorted(roles.values()) == [
        b"gameCategory",
        b"gameCover",
        b"gameIcon",
        b"gameId",
        b"gameInstallDir",
        b"gameInstalledAt",
        b"gameIssueLevel",
        b"gameIssuesTip",
        b"gameLastPlayed",
        b"gameLastSecs",
        b"gameName",
        b"gameOrigin",
        b"gamePlatform",
        b"gamePlayed",
        b"gamePlayedSecs",
        b"gamePlayedTip",
        b"gameReleaseDate",
        b"gameRunning",
        b"gameRuntime",
        b"gameStatus",
        b"gameStatusBg",
        b"gameStatusFg",
        b"gameTier",
        b"gameTierBg",
        b"gameTierFg",
        b"gameWine",
    ]


def test_model_counts(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid in ("213", "local-a", "local-b"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    model = GameListModel()
    assert (model.totalCount, model.steamCount, model.localCount) == (3, 1, 2)


def test_model_counts_visible_to_qml(qgui_app, xdg_env):
    """Count properties must live on the QMetaObject (post-hoc fails QML)."""
    from tkarcade.gui.model import GameListModel

    meta = GameListModel.staticMetaObject
    names = {meta.property(i).name() for i in range(meta.propertyCount())}
    assert {"totalCount", "steamCount", "localCount", "steamDetectedCount"} <= names


def test_model_play_failure_consumes_skip(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    assert model.play("213") is False
    assert not L.menu_skip_path("213").exists()


def test_model_play_reports_launch(qgui_app, xdg_env, monkeypatch):
    """play() reports (ok, kind, name, detail) so the UI can speak.

    The widgets wrote the status line and the handoff warnings in the
    same code path the tray used; the QML shell gets the same events.
    """
    from PySide6.QtGui import QDesktopServices

    from tkarcade import launcher as L
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    reports = []
    model.launchReported.connect(lambda *args: reports.append(args))

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    assert model.play("213") is False
    assert reports[-1][0] is False
    assert reports[-1][1] == "steam"

    monkeypatch.setattr(L, "launch_local_detached", lambda appid: None)
    assert model.play("local-doom") is True
    ok, kind, name, detail = reports[-1]
    assert (ok, kind, detail) == (True, "local", "")
    assert name != ""

    def boom(appid):
        raise OSError("spawn failed")

    monkeypatch.setattr(L, "launch_local_detached", boom)
    assert model.play("local-doom") is False
    assert reports[-1][0] is False
    assert reports[-1][3] == "spawn failed"


def test_proxy_sort_by_role(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)

    def ids():
        return [
            proxy.data(proxy.index(r, 0), GameListModel.IdRole) for r in range(proxy.rowCount())
        ]

    assert ids() == ["a-game", "b-game"]  # source order (name-sorted)
    proxy.sortBy("gameId", False)
    assert ids() == ["a-game", "b-game"]
    proxy.sortBy("gameId", True)
    assert ids() == ["b-game", "a-game"]
    proxy.sortBy("nope", False)  # unknown role falls back to name
    assert ids() == ["a-game", "b-game"]


def test_filter_model_source_and_text(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid, name in (("213", ""), ("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        C.save(cfg)
    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)

    def shown():
        return sorted(
            proxy.data(proxy.index(i, 0), GameListModel.IdRole) for i in range(proxy.rowCount())
        )

    assert shown() == ["local-doom", "local-quake", "steam-213"]
    proxy.sourceKey = "local"
    assert shown() == ["local-doom", "local-quake"]
    proxy.sourceKey = "steam"
    assert shown() == ["steam-213"]
    proxy.sourceKey = "all"
    proxy.textQuery = "doom"
    assert shown() == ["local-doom"]
    proxy.textQuery = "LOCAL-"
    assert shown() == ["local-doom", "local-quake"]
    proxy.textQuery = ""
    assert shown() == ["local-doom", "local-quake", "steam-213"]


def test_open_protondb_rejects_local(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().openProtonDB("local-doom") is False


def test_open_protondb_handoff(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from tkarcade.gui.model import GameListModel

    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    assert GameListModel().openProtonDB("42") is True
    assert opened == ["https://www.protondb.com/app/42"]


def test_played_tip_role(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    tip = proxy.data(proxy.index(0, 0), GameListModel.PlayedTipRole)
    assert tip == "No Recorded Sessions"


def test_ludusavi_open_reports(qgui_app, xdg_env, monkeypatch):
    import shutil
    import subprocess

    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert GameListModel().openLudusavi() == "Ludusavi Was Not Found in PATH."
    monkeypatch.setattr(shutil, "which", lambda _name: "/var/lib/flatpak/exports/bin/ludusavi")
    assert GameListModel().openLudusavi().startswith("Flatpak Ludusavi Detected")
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/ludusavi")
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args: calls.append(args))
    assert GameListModel().openLudusavi() == ""
    assert calls == [["/usr/bin/ludusavi"]]


def test_about_text_names_program(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    body = GameListModel().aboutText()
    assert "TKArcade" in body and "GPL-3.0-or-later" in body
    assert "Steam and Local Game Launch Wrapper" in body


def test_steam_running_falls_back_to_the_flatpak_process(qgui_app, xdg_env, monkeypatch):
    import subprocess

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    calls = []
    returns = [1, 0]

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, returns[len(calls) - 1])

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert model.steamRunning() is True
    assert calls == [
        ["pgrep", "-x", "steam"],
        ["pgrep", "-f", "[c]om.valvesoftware.Steam"],
    ]
    calls.clear()
    returns[:] = [1, 1]
    assert model.steamRunning() is False
    calls.clear()
    returns[:] = [2]
    assert model.steamRunning() is True


def test_history_summary_empty_without_log(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().historySummary() == []


def test_copy_text_roundtrip(qgui_app, xdg_env):
    from PySide6.QtGui import QGuiApplication

    from tkarcade.gui.model import GameListModel

    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        assert "unavailable" in GameListModel().copyText("x").lower()
    else:
        assert GameListModel().copyText("tkarcade %command%").startswith("Copied")
        assert clipboard.text() == "tkarcade %command%"


def test_fetch_missing_killswitch(qgui_app, xdg_env, monkeypatch):
    import os
    import threading

    from tkarcade.gui.model import GameListModel

    calls = []
    monkeypatch.setattr(threading, "Thread", lambda **kw: calls.append(kw) or FakeThread())
    os.environ.pop("TKARCADE_NO_BG_FETCH", None)

    class FakeThread:
        def start(self):
            pass

    GameListModel().fetchMissing()
    assert len(calls) == 1


def test_added_steam_game_fetches_its_tier_at_once(qgui_app, xdg_env, monkeypatch):
    """Adding a Steam game looks up ProtonDB now, not on the next start."""
    import tkarcade.gui.model as modelmod
    from tkarcade import protondb as pdb
    from tkarcade.gui.model import GameListModel

    class FakeThread:
        def __init__(self, target=None, args=(), **kwargs):
            self._target, self._args = target, args

        def start(self):
            self._target(*self._args)

    monkeypatch.delenv("TKARCADE_NO_BG_FETCH", raising=False)
    monkeypatch.setattr(modelmod.threading, "Thread", FakeThread)
    monkeypatch.setattr(modelmod.rdmod, "refresh", lambda appid: {})
    art_calls = []
    monkeypatch.setattr(
        modelmod.artmod,
        "fetch_best",
        lambda target, *a, **k: (
            art_calls.append(target) or {"art": {}, "provider": "", "error": ""}
        ),
    )
    fetched = []
    monkeypatch.setattr(pdb, "refresh", lambda appid, target="": fetched.append(appid) or {})
    model = GameListModel()

    assert model.saveGame("steam-620", {"name": "Portal 2"}) == "steam-620"
    assert fetched == ["steam-620"]

    fetched.clear()
    assert model.saveGame("steam-440", {"name": "Team Fortress 2"}) == "steam-440"
    assert fetched == ["steam-440"]

    # An existing game is not looked up again on every save.
    fetched.clear()
    assert model.saveGame("steam-620", {}) == "steam-620"
    assert fetched == []

    # A new local game gets its name-based art lookup as well.
    local = model.addLocal("Zebra", "/bin/true")
    assert local.startswith("local-")
    assert art_calls[-1] == local


def test_detected_runtime_kind_follows_steam_mapping(qgui_app, xdg_env, monkeypatch):
    """The Runtime kind comes from Steam's own compat mapping."""
    from tkarcade import proton as P
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(P, "default_compat_tool", lambda: "proton_experimental")
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: "proton_9")
    assert model.detectedRuntimeKind("steam-620") == "proton"
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: "steamlinuxruntime_sniper")
    assert model.detectedRuntimeKind("steam-620") == "native"
    # No per-game entry: Steam applies its default tool.
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    assert model.detectedRuntimeKind("steam-620") == "proton"
    monkeypatch.setattr(P, "default_compat_tool", lambda: None)
    assert model.detectedRuntimeKind("steam-620") == ""
    assert model.detectedRuntimeKind("local-zebra") == ""


def test_detected_runtime_keeps_the_tool_version(qgui_app, xdg_env, monkeypatch):
    """The game dialog shows the compat tool and its version."""
    from tkarcade import proton as P
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(P, "default_compat_tool", lambda: "proton_9")
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    monkeypatch.setattr(P, "tool_version", lambda tool: "9.0-4")
    assert model.detectedRuntime("steam-620") == "proton_9 (9.0-4)"


def test_download_latest_graphics_runs_worker(qgui_app, xdg_env, monkeypatch):

    from tkarcade.gui import model as M

    class FakeThread:
        def __init__(self, target=None, args=(), **kwargs):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr(M.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        M.archivesmod,
        "download_latest",
        lambda kind, progress=None, repo="": (progress("Halfway."), "")[1],
    )
    model = M.GameListModel()
    progress: list[tuple[str, str]] = []
    finished: list[tuple[str, str]] = []
    changed: list[bool] = []
    model.archiveProgress.connect(lambda kind, text: progress.append((kind, text)))
    model.archiveFinished.connect(lambda kind, text: finished.append((kind, text)))
    model.archivesChanged.connect(lambda: changed.append(True))
    model.downloadLatestGraphics("dxvk")
    assert ("dxvk", "Halfway.") in progress
    assert finished == [("dxvk", "")]
    assert changed == [True]
    assert model._archive_busy == set()
    model.downloadLatestGraphics("wine")
    assert finished[-1] == ("wine", "Unknown Runtime Layer.")


def test_download_latest_reports_helper_errors(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    class FakeThread:
        def __init__(self, target=None, args=(), **kwargs):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    def fail(kind, progress=None, repo=""):
        raise RuntimeError("boom")

    monkeypatch.setattr(M.threading, "Thread", FakeThread)
    monkeypatch.setattr(M.archivesmod, "download_latest", fail)
    model = M.GameListModel()
    finished: list[tuple[str, str]] = []
    changed: list[bool] = []
    model.archiveFinished.connect(lambda kind, text: finished.append((kind, text)))
    model.archivesChanged.connect(lambda: changed.append(True))
    model.downloadLatestGraphics("vkd3d")
    assert finished == [("vkd3d", "vkd3d download failed: boom")]
    assert changed == []


def test_graphics_state_extracts_pending_archives(qgui_app, xdg_env, monkeypatch):
    from tkarcade import xdg
    from tkarcade.gui import model as M

    class FakeThread:
        def __init__(self, target=None, args=(), **kwargs):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    cache = xdg.archives_cache_dir()
    cache.mkdir(parents=True)
    (cache / "dxvk-2.7.1.tar.gz").write_bytes(b"x")
    monkeypatch.setattr(M.threading, "Thread", FakeThread)
    monkeypatch.setattr(M.archivesmod, "sync_archives", lambda progress=None: ["dxvk-2.7.1"])
    model = M.GameListModel()
    changed: list[bool] = []
    model.archivesChanged.connect(lambda: changed.append(True))
    model.graphicsState("")
    assert changed == [True]
    assert model._archive_sync_running is False


def test_remove_and_profiles_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    profiles = C.profiles_dir("local-doom")
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / "default.toml").write_text("[general]\n")
    model = GameListModel()
    assert model.leftoverProfiles(["local-doom"]) == ["local-doom"]
    assert model.cleanProfiles(["local-doom"]) == 1
    assert model.removeGames(["local-doom"]) == ""
    assert not C.game_file("local-doom").exists()


def test_uninstalled_games_lists_missing_installs(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    steamapps = xdg_env["home"] / ".local/share/Steam/steamapps"
    (steamapps / "common" / "Doom").mkdir(parents=True)
    (steamapps / "appmanifest_40.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"40"\n\t"installdir"\t\t"Doom"\n}\n',
        encoding="utf-8",
    )
    for appid, exe in (
        ("steam-40", ""),
        ("steam-41", ""),
        ("local-good", "/bin/true"),
        ("local-gone", "/nonexistent/game"),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.custom_executable = exe
        cfg.runtime.type = "native"
        C.save(cfg)
    missing = GameListModel().uninstalledGames()
    assert sorted(missing) == ["local-gone", "steam-41"]


def test_leftovers_include_logs_history_and_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade import config as C
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    base = tmp_path / "pfx"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    prefix.mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    profiles = C.profiles_dir("local-doom")
    profiles.mkdir(parents=True)
    (profiles / "default.toml").write_text("[general]\n")
    logs = xdg.games_log_dir()
    logs.mkdir(parents=True, exist_ok=True)
    xdg.game_log_file("local-doom").write_text("log\n", encoding="utf-8")
    (logs / "local-doom" / "proton").mkdir(parents=True)
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-01-02T10:00:00 appid=local-doom exit=0 dur=60 cmd=tkarcade\n", encoding="utf-8"
    )
    model = GameListModel()
    assert model.orphanedLeftovers() == []  # live config holds it
    model.removeGames(["local-doom"])
    rows = model.leftoverData(["local-doom"])
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Doom"
    assert row["profiles"] == 1
    assert row["session_log"] is True
    assert row["proton_log"] is True
    assert row["history"] == 1
    assert row["prefix"] == str(prefix.resolve())
    assert model.cleanLeftovers(["local-doom"], False) == 1
    assert not profiles.exists()
    assert not xdg.game_log_file("local-doom").exists()
    assert not (logs / "local-doom").exists()
    assert "local-doom" not in xdg.log_file().read_text(encoding="utf-8")
    assert prefix.is_dir()  # unchecked option keeps the prefix


def test_leftover_prefix_option_deletes_owned_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    base = tmp_path / "pfx"
    prefix = C.prefix_dir("local-quake", str(base), "", "", "Quake")
    prefix.mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-quake"
    cfg.general.name = "Quake"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    model = GameListModel()
    model.removeGames(["local-quake"])
    rows = model.orphanedLeftovers()  # nothing left: prefix not discoverable
    assert rows == []
    rows = model.leftoverData(["local-quake"])
    assert len(rows) == 1
    assert rows[0]["prefix"] == str(prefix.resolve())
    assert model.cleanLeftovers(["local-quake"], True) == 1
    assert not prefix.exists()


def test_orphaned_leftovers_finds_unconfigured_logs(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    logs = xdg.games_log_dir()
    logs.mkdir(parents=True)
    xdg.game_log_file("gone-game").write_text("log\n", encoding="utf-8")
    (logs / "gone-game" / "proton").mkdir(parents=True)
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-01-02T10:00:00 appid=gone-game exit=1 dur=10 cmd=tkarcade\n", encoding="utf-8"
    )
    model = GameListModel()
    rows = model.orphanedLeftovers()
    assert [r["appid"] for r in rows] == ["gone-game"]
    assert rows[0]["session_log"] is True
    assert rows[0]["proton_log"] is True
    assert rows[0]["history"] == 1
    assert model.cleanLeftovers(["gone-game"], False) == 1
    assert model.orphanedLeftovers() == []


def test_validate_report_uses_the_game_name(qgui_app, xdg_env, monkeypatch):
    from tkarcade import config as C
    from tkarcade import launcher
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    monkeypatch.setattr(
        launcher, "validate_game", lambda appid: [f"{appid}: custom_executable not found"]
    )
    report = GameListModel().validateReport("local-doom")
    assert report["name"] == "Doom"
    assert report["issues"] == ["custom_executable not found"]


def test_clear_history_removes_log_lines(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    log = xdg.log_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "2026-01-01T10:00:00 appid=42 exit=0 dur=60\n2026-01-01T11:00:00 appid=43 exit=0 dur=30\n",
        encoding="utf-8",
    )
    assert GameListModel().clearHistory("42") == 1
    assert "appid=42" not in log.read_text(encoding="utf-8")
    assert "appid=43" in log.read_text(encoding="utf-8")


def test_column_prefs_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)
    assert proxy.columnLogical(0) == 0
    proxy.moveColumn(11, 1)
    assert [proxy.columnLogical(c) for c in range(13)] == [0, 1, 5, 11, 7, 3, 6, 12, 8, 9, 4, 2, 10]
    assert C.load_preferences().column_order.split(",")[:4] == ["0", "1", "5", "11"]
    proxy.showOrigin = False
    assert "5" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert [proxy.columnLogical(c) for c in range(13)] == [0, 1, 11, 5, 7, 3, 6, 12, 8, 9, 4, 2, 10]
    assert C.load_preferences().hidden_columns == "2,4,8,9,10"


def test_column_width_autofit_persists(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    proxy = _filtered(qgui_app)
    assert proxy.columnWidth(1) == 0
    width = proxy.autofitColumn(1)
    assert width >= 40  # header title alone guarantees the minimum
    assert proxy.columnWidth(1) == width
    assert f"1={width}" in C.load_preferences().column_widths.split(",")
    import json

    assert json.loads(proxy.columnWidthsJson()) == {"1": width}
    assert proxy.autofitColumn(99) == 0
    fresh = GameFilterModel()
    fresh.setSourceModel(GameListModel())
    assert fresh.columnWidth(1) == width
    fresh.fitDefaults()
    assert 40 <= fresh.columnWidth(1) <= 300
    assert 40 <= fresh.columnWidth(2) <= 300
    proxy.resetColumns()
    assert 40 <= proxy.columnWidth(1) <= 300  # reset fits, capped
    assert C.load_preferences().column_widths != ""


def test_column_width_drag_preview_then_save(qgui_app, xdg_env):

    proxy = _filtered(qgui_app)
    proxy.setColumnWidth(2, 150)
    assert proxy.columnWidth(2) == 150
    assert C.load_preferences().column_widths == ""  # preview: no save yet
    proxy.saveColumnWidths()
    assert C.load_preferences().column_widths == "2=150"
    proxy.setColumnWidth(2, 5)  # below minimum: rejected
    assert proxy.columnWidth(2) == 150
    proxy.setColumnWidth(99, 150)  # unknown column: rejected
    assert proxy.columnWidth(99) == 0


def test_role_id_maps_names(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.roleId("gameId") == GameListModel.IdRole
    assert model.roleId("gameName") == GameListModel.NameRole
    assert model.roleId("nope") == -1


def test_row_data_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    row = proxy.rowData(0)
    assert row["gameId"] == "local-doom"
    assert row["gameName"] == "Doom"
    assert proxy.rowData(99) == {}


def test_drawer_mode_roundtrip(qgui_app, xdg_env):
    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.drawerMode() == "collapsible"
    model.saveDrawerMode("overlay")
    assert C.load_preferences().drawer_mode == "overlay"
    model.saveDrawerMode("bogus")
    assert C.load_preferences().drawer_mode == "collapsible"


def test_drawer_collapsed_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.drawerCollapsed() is True
    model.saveDrawerCollapsed(False)
    assert C.load_preferences().drawer_collapsed is False
    assert GameListModel().drawerCollapsed() is False


def test_settings_load_save_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["name"] == "Doom"
    assert fields["runtime_type"] == "native"
    assert fields["is_steam"] is False
    assert fields["profiles"] == []
    out = dict(fields)
    out["name"] = "Doom II"
    out["menu_timeout"] = 30
    out["notes"] = "rip and tear"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.general.name == "Doom II"
    assert reloaded.general.menu_timeout == 30
    assert reloaded.notes.text == "rip and tear"
    assert model.saveGame("nope-missing", {}) == ""
    assert model.loadGame("nope-missing")["name"] == ""
    assert model.saveGame("", {"name": "", "custom_executable": "/bin/true"}) == ""


def test_settings_save_keeps_a_custom_winedebug(qgui_app, xdg_env):
    """A hand-written WINEDEBUG value survives an unrelated dialog save."""
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "steam-99"
    cfg.runtime.type = "proton"
    cfg.debug.winedebug = "+d3d11"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("steam-99")
    assert fields["winedebug"] == "+d3d11"
    out = dict(fields)
    out["notes"] = "changed"
    assert model.saveGame("steam-99", out) == "steam-99"
    assert C.load("steam-99").debug.winedebug == "+d3d11"


def test_steam_status_probe_runs_in_the_background(qgui_app, xdg_env, monkeypatch):
    """A forced launch-options probe returns at once and reports later."""
    from PySide6.QtTest import QSignalSpy

    import tkarcade.gui.model as modelmod
    from tkarcade import __version__ as gui_version
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    monkeypatch.delenv("TKARCADE_NO_BG_FETCH", raising=False)
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    calls = []
    monkeypatch.setattr(
        S,
        "launch_options_status",
        lambda appid: calls.append(appid) or ("ok", "tkarcade %command%"),
    )
    monkeypatch.setattr(
        modelmod, "_path_tkarcade_version", lambda: ("/usr/bin/tkarcade", gui_version)
    )
    model = GameListModel()
    spy = QSignalSpy(model.steamStatusReady)
    rows = model.dependencyStatus("620", {}, check_steam=True)
    entry = next(row for row in rows if row["key"] == "steam-options")
    assert entry["msg"] == "steam-unknown"
    if not spy.count():
        spy.wait(2000)
    assert spy.count() >= 1
    rows = model.dependencyStatus("620", {}, check_steam=False)
    entry = next(row for row in rows if row["key"] == "steam-options")
    assert entry["msg"] == "steam-ok"
    assert calls == ["620"]


def test_metadata_suffix_and_name_split(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    out = dict(model.loadGame("local-doom"))
    out["name"] = "Doom [v1.2]"
    out["tag"] = "Beta"
    assert model.saveGame("local-doom", out) == "local-doom"
    saved = C.load("local-doom")
    assert saved.general.name == "Doom"
    assert saved.metadata.version == "v1.2"
    assert saved.metadata.tag == "Beta"
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    assert proxy.rowData(0)["gameName"] == "Doom [v1.2] (Beta)"
    assert model.metadataDateValid("2026-10") is True
    assert model.metadataDateValid("2026-13") is False


def test_metadata_fields_and_status_role(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    cfg.metadata.description = "A synopsis."
    cfg.metadata.developer = "id Software"
    cfg.metadata.publisher = "Bethesda"
    cfg.metadata.genre = "Action, Shooter"
    cfg.metadata.series = "Doom"
    cfg.metadata.age_ratings = ["PEGI 12", "ESRB T"]
    cfg.metadata.region = "world"
    cfg.metadata.status = "completed"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["description"] == "A synopsis."
    assert fields["developer"] == "id Software"
    assert fields["age_ratings"] == ["PEGI 12", "ESRB T"]
    assert fields["region"] == "world"
    assert fields["status"] == "completed"
    out = dict(fields)
    out["status"] = "playing"
    assert model.saveGame("local-doom", out) == "local-doom"
    assert C.load("local-doom").metadata.status == "playing"
    model.refresh()
    proxy = GameFilterModel()
    proxy.setSourceModel(model)
    assert proxy.rowData(0)["gameStatus"] == "playing"
    assert proxy.rowData(0)["gameStatusBg"] == "#81C784"
    assert proxy.rowData(0)["gameStatusFg"] == "#000000"
    assert model.data(model.index(0, 0), GameListModel.StatusRole) == "playing"
    groups = model.ageRatingGroups()
    assert [group["name"] for group in groups] == [
        "ACB",
        "CERO",
        "ClassInd",
        "ESRB",
        "GRAC",
        "IARC",
        "PEGI",
        "USK",
    ]
    assert [group["default"] for group in groups] == [
        False,
        True,
        True,
        True,
        False,
        False,
        True,
        False,
    ]
    assert "PEGI 12" in groups[6]["ratings"]
    assert isinstance(model.symbolFontFamily(), str)


def test_protondb_info_reads_the_cache(qgui_app, xdg_env):
    import json
    import time

    from tkarcade import protondb as P
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    path = P.cache_path("steam-620")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"saved": int(time.time()), "data": {"tier": "gold"}}),
        encoding="utf-8",
    )
    model = GameListModel()
    info = model.protonDBInfo("steam-620")
    assert info["tier"] == "Gold"
    assert info["bg"] == "#FFC107"
    assert model.protonDBInfo("local-doom") == {}


def test_local_steam_link_reaches_the_tier_and_the_page(qgui_app, xdg_env, monkeypatch):
    import json
    import time

    from PySide6.QtGui import QDesktopServices

    from tkarcade import protondb as P
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.metadata.steam_appid = "620"
    C.save(cfg)
    path = P.cache_path("local-doom")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"saved": int(time.time()), "target": "620", "data": {"tier": "platinum"}}),
        encoding="utf-8",
    )
    model = GameListModel()
    assert model.protonDBInfo("local-doom")["tier"] == "Platinum"
    # A draft whose link has no data yet is not rated.
    assert model.protonDBInfo("local-doom", "621")["tier"] == ""
    opened = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True
    )
    assert model.openProtonDB("local-doom") is True
    assert opened == ["https://www.protondb.com/app/620"]
    assert model.contextActions("local-doom")["protondb_appid"] == "620"


def test_fetch_metadata_targets_the_store_link(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.metadata.steam_appid = "620"
    C.save(cfg)
    model = M.GameListModel()
    got = []
    model.metadataFetched.connect(lambda appid, data: got.append((appid, data)))
    calls = []
    monkeypatch.setattr(
        M.metamod,
        "download",
        lambda provider, appid, target="": (
            calls.append((provider, appid, target))
            or {"description": "Portal", "developer": "Valve"}
        ),
    )
    model._metadata_worker("local-doom", "steam", model._steam_target("local-doom"))
    assert calls == [("steam", "local-doom", "620")]
    assert got == [("local-doom", {"description": "Portal", "developer": "Valve"})]

    # No Steam AppID: the dialog is told at once, without a worker.
    got.clear()
    model.fetchMetadata("local-other", "steam", "")
    assert got == [("local-other", {})]


def test_metadata_provider_workers(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    model = M.GameListModel()
    choices = []
    got = []
    model.metadataChoices.connect(lambda appid, rows: choices.append((appid, rows)))
    model.metadataFetched.connect(lambda appid, data: got.append((appid, data)))
    monkeypatch.setattr(
        M.metamod,
        "search",
        lambda provider, query: [{"id": "v2002", "name": query}] if provider == "vndb" else [],
    )
    model._metadata_search_worker("local-sg", "vndb", "Steins;Gate")
    assert choices == [("local-sg", [{"id": "v2002", "name": "Steins;Gate"}])]

    calls = []
    monkeypatch.setattr(
        M.metamod,
        "download",
        lambda provider, appid, target="": (
            calls.append((provider, appid, target)) or {"description": "Syn"}
        ),
    )
    model._metadata_worker("local-sg", "vndb", "v2002")
    model._metadata_worker("local-hades", "igdb", "1145360")
    assert calls == [("vndb", "local-sg", "v2002"), ("igdb", "local-hades", "1145360")]
    assert got == [
        ("local-sg", {"description": "Syn"}),
        ("local-hades", {"description": "Syn"}),
    ]

    # An unknown provider and an empty title answer at once, no worker.
    got.clear()
    model.fetchMetadata("local-sg", "nope", "")
    assert got == [("local-sg", {})]
    choices.clear()
    model.searchMetadata("local-sg", "vndb", "  ")
    assert choices == [("local-sg", [])]


def test_igdb_configured_needs_both_parts(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.igdbConfigured() is False
    prefs = C.Preferences()
    prefs.igdb_client_id = "cid"
    C.save_preferences(prefs)
    assert model.igdbConfigured() is False
    prefs.igdb_client_secret = "sec"
    C.save_preferences(prefs)
    assert model.igdbConfigured() is True


def test_igdb_id_survives_the_form_map(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    appid = model.saveGame(
        "",
        {
            "name": "Hades",
            "custom_executable": "/bin/true",
            "runtime_type": "native",
            "igdb_id": " 1145360 ",
        },
    )
    assert C.load(appid).metadata.igdb_id == "1145360"
    assert model.loadGame(appid)["igdb_id"] == "1145360"


def test_vndb_id_survives_the_form_map(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    appid = model.saveGame(
        "",
        {
            "name": "Steins;Gate",
            "custom_executable": "/bin/true",
            "runtime_type": "native",
            "vndb_id": "V2002",
        },
    )
    assert C.load(appid).metadata.vndb_id == "v2002"
    assert model.loadGame(appid)["vndb_id"] == "v2002"


def test_metadata_locks_survive_the_form_map(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    appid = model.saveGame(
        "",
        {
            "name": "Doom",
            "custom_executable": "/bin/true",
            "runtime_type": "native",
            "locked": "developer, bogus, description",
        },
    )
    assert C.load(appid).metadata.locked == "description,developer"
    assert model.loadGame(appid)["locked"] == "description,developer"


def test_settings_create_and_profiles(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    created = model.saveGame(
        "", {"name": "Doom", "custom_executable": "/bin/true", "runtime_type": "native"}
    )
    assert created.startswith("local-")
    assert C.load(created).general.name == "Doom"
    assert model.saveGameProfile(created, "fast", {"custom_executable": "/bin/true"}) is True
    assert model.loadGame(created)["profiles"] == ["fast"]
    assert model.saveGameProfile(created, "", {}) is False
    assert model.profileExists(created, "fast") is True
    assert model.profileExists(created, "missing") is False
    assert model.cloneGameProfile(created, "fast", "faster", {}) is True
    assert model.cloneGameProfile(created, "missing", "x", {}) is False
    assert model.cloneGameProfile(created, "fast", "fast", {}) is False
    assert (
        model.cloneGameProfile(created, "", "livecopy", {"custom_executable": "/bin/true"}) is True
    )
    assert model.profileExists(created, "livecopy") is True
    content = model.profileContent(created, "fast")
    assert content["custom_executable"] == "/bin/true"
    assert model.profileContent(created, "missing") == {}
    assert C.load(created).general.active_profile == ""
    assert model.markActiveProfile(created, "fast") is True
    assert C.load(created).general.active_profile == "fast"
    out = dict(model.loadGame(created))
    out["name"] = "Doom II"
    out["active_profile"] = "fast"
    assert model.saveGame(created, out) == created
    assert C.load(created).general.name == "Doom"
    assert C.load_profile(created, "fast").general.name == "Doom II"
    assert model.deleteGameProfile(created, "fast") is True
    assert C.load(created).general.active_profile == ""
    assert model.loadGame(created)["profiles"] == ["faster", "livecopy"]


def test_settings_env_prepost_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.env.vars = {"FOO": "bar", "QUOTED": "a b"}
    cfg.pre_post.pre_command = "/bin/echo"
    cfg.pre_post.pre_args = ["a b", "c"]
    cfg.pre_post.timeout = 30
    cfg.pre_post.run_in_shell = True
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert {"key": "FOO", "value": "bar"} in fields["env_vars"]
    assert fields["pre_args"] == "'a b' c"
    assert fields["pp_timeout"] == 30
    assert fields["run_in_shell"] is True
    out = dict(fields)
    out["env_vars"] = [{"key": "NEW", "value": "1"}, {"key": "", "value": "x"}]
    out["pre_args"] = 'x "y z"'
    out["pp_timeout"] = 9999
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.env.vars == {"NEW": "1"}
    assert reloaded.pre_post.pre_args == ["x", "y z"]
    assert reloaded.pre_post.timeout == 3600


def test_settings_gamemode_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.gamemode.feral_gamemode = True
    C.save(cfg)
    model = GameListModel()
    assert model.loadGame("local-doom")["gamemode_feral"] is True
    out = dict(model.loadGame("local-doom"))
    out["gamemode_feral"] = False
    out["gamemode_cachy"] = True
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.gamemode.feral_gamemode is False
    assert reloaded.gamemode.cachyos_game_performance is True


def test_settings_display_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.display.provider = "x11"
    cfg.display.output = "DP-1"
    cfg.display.mode = "1920x1080@60"
    cfg.display.dip_seconds = 5
    cfg.gamescope.enable = True
    cfg.gamescope.args = "-f"
    cfg.mangohud.config_file = "foo.conf"
    cfg.rtupscale.enable = True
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["display_provider"] == "x11"
    assert fields["display_mode"] == "1920x1080@60"
    assert fields["dip_seconds"] == 5
    assert fields["gamescope_args"] == "-f"
    out = dict(fields)
    out["display_provider"] = "bogus"
    out["dip_seconds"] = 99
    out["rt_args"] = "-m 4x24"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.display.provider == "auto"
    assert reloaded.display.dip_seconds == 15
    assert reloaded.rtupscale.args == "-m 4x24"
    assert model.displayModesMatch("1920x1080@60", "1920x1080@60") is True
    assert model.displayModesMatch("1920x1080@60", "1280x720@60") is False
    assert model.displayModesMatch("garbage", "1920x1080@60") is False
    assert "1080p 144Hz Fullscreen" in model.gamescopePresets()
    assert model.gamescopePreset("1080p 144Hz Fullscreen") == "-f -W 1920 -H 1080 -r 144"
    assert model.gamescopePreset("nope") == ""
    assert model.mangohudConfigs() == []
    assert model.createMangohudConfig("test-game", "minimal") != ""
    assert "test-game.conf" in model.mangohudConfigs()
    assert model.createMangohudConfig("", "minimal") == ""


def test_library_schema_slots(qgui_app, xdg_env, tmp_path):
    import os

    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    model = GameListModel()
    assert model.allCategories() == []
    assert model.setCategories([], "Action") == "Select Games First."
    assert model.setCategories(["local-doom"], "Action, Retro ,") == (
        "Set 2 Categor(ies) on 1 Game(s)."
    )
    assert C.load("local-doom").general.categories == ["Action", "Retro"]
    assert model.allCategories() == ["Action", "Retro"]
    assert model.categoryPresence(["local-doom"]) == {"Action": 1, "Retro": 1}
    assert model.categoryPresence([]) == {"Action": 0, "Retro": 0}
    assert model.categoryCounts() == {"Action": 1, "Retro": 1}
    assert model.setCategories(["local-doom"], "Action, action , ACTION") == (
        "Set 1 Categor(ies) on 1 Game(s)."
    )
    assert C.load("local-doom").general.categories == ["Action"]
    # Categories outlive their tags: Retro stays on record without games.
    assert model.allCategories() == ["Action", "Retro"]
    assert model.categoryCounts() == {"Action": 1, "Retro": 0}
    assert model.categoryIcons() == {"Action": "folder", "Retro": "folder"}
    art = tmp_path / "icon.png"
    art.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert model.storeArtwork("local-doom", "icon", os.fspath(art)) == ""
    assert C.load("local-doom").artwork.icon.endswith("icon.png")
    assert model.storeArtwork("local-doom", "icon", os.fspath(tmp_path / "nope.png")) != ""
    assert model.clearArtwork("local-doom", "icon") is True
    assert C.load("local-doom").artwork.icon == ""
    assert isinstance(model.wineTools(), list)
    assert model.applyWineVersion("local-doom", "proton_9") == (
        "Version Selection Needs a Steam Game."
    )
    local_prefix = model.prefixDir("local-doom")
    assert local_prefix.endswith("/prefixes/Doom")
    assert model.ensurePrefix("local-doom") == ""
    assert os.path.isdir(local_prefix)
    assert model.clearCustomPrefix("local-doom") == f"Cleared {local_prefix}."
    assert not os.path.exists(local_prefix)


def test_category_editor_slots(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid, name, cats in (
        ("local-doom", "Doom", ["Action"]),
        ("local-quake", "Quake", ["Retro"]),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.general.custom_executable = "/bin/true"
        cfg.general.categories = cats
        C.save(cfg)
    model = GameListModel()
    # The refresh sync keeps tags found on disk on record.
    assert [(c.name, c.icon) for c in C.load_categories()] == [
        ("Action", "folder"),
        ("Retro", "folder"),
    ]
    assert model.categoryGameRows("Action") == [
        {"appid": "local-doom", "name": "Doom", "state": 2},
        {"appid": "local-quake", "name": "Quake", "state": 0},
    ]
    assert model.setCategoryGames("Action", ["local-doom", "local-quake"]) == ("Updated 1 Game(s).")
    assert C.load("local-quake").general.categories == ["Retro", "Action"]
    assert model.setCategoryGames("Action", []) == "Updated 2 Game(s)."
    assert C.load("local-doom").general.categories == []
    assert C.load("local-quake").general.categories == ["Retro"]
    assert model.allCategories() == ["Action", "Retro"]
    assert model.categoryCounts() == {"Action": 0, "Retro": 1}
    model.setCategoryIcon("Action", "applications-games")
    assert model.categoryIcons() == {
        "Action": "applications-games",
        "Retro": "folder",
    }
    assert model.deleteCategory("retro") == "Deleted Retro."
    assert C.load("local-quake").general.categories == []
    assert C.load_categories()[0].name == "Action"
    assert model.allCategories() == ["Action"]
    assert model.deleteCategory("") == "Pick a Category First."


def test_library_columns_roles(qgui_app, xdg_env):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.categories = ["Action"]
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    assert model.columnCount() == 13
    row = model.rowData(0)
    assert row["gamePlatform"] == "Linux"
    assert row["gameCategory"] == "Action"
    assert row["gameRuntime"] == "Native"
    assert row["gameReleaseDate"] == "—"
    assert row["gameLastPlayed"] == "—"
    assert row["gameLastSecs"] == -1
    assert row["gameInstalledAt"][:2] == "20"
    game_filter = GameFilterModel()
    game_filter.setSourceModel(model)
    assert game_filter.columnCount() == 13
    assert game_filter._order == [0, 1, 11, 5, 7, 3, 6, 12, 8, 9, 4, 2, 10]
    assert game_filter._hidden == {2, 4, 8, 9, 10}
    assert game_filter.showLastPlayed is True
    assert game_filter.showReleaseDate is True
    game_filter.sortBy("gameLastSecs", True)


def test_release_date_manual_wins_over_steam_cache(qgui_app, xdg_env):
    import json

    from tkarcade import releasedate as rd
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "steam-213"
    C.save(cfg)
    path = rd.cache_path("steam-213")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"saved": int(time.time()), "date": "2025-08-28"}), encoding="utf-8")

    def dates():
        model = GameListModel()
        return {
            model.data(model.index(i, 0), model.IdRole): model.rowData(i)["gameReleaseDate"]
            for i in range(model.rowCount())
        }

    assert dates()["steam-213"] == "2025-08-28"
    cfg.metadata.date = "1993-12-10"
    C.save(cfg)
    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    C.save(local)
    cells = dates()
    assert cells["steam-213"] == "1993-12-10"
    assert cells["local-doom"] == "—"


def test_installed_cell_prefers_stamp_then_birth_time(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    stamp = C.load("local-doom").general.installed_at
    expected = stamp.replace("T", " ")[:16]
    assert expected != ""
    assert GameListModel().rowData(0)["gameInstalledAt"] == expected
    path = C.game_file("local-doom")
    path.write_text(
        path.read_text(encoding="utf-8").replace(stamp, ""),
        encoding="utf-8",
    )
    fallback = C.installed_stamp(path).replace("T", " ")[:16]
    assert fallback != ""
    assert GameListModel().rowData(0)["gameInstalledAt"] == fallback


def test_wine_column_dash_and_proton_names(qgui_app, xdg_env, monkeypatch):
    from tkarcade import proton as pmod
    from tkarcade.gui.model import GameListModel

    for appid, name, kind, tool in (
        ("steam-214", "", "native", ""),
        ("steam-213", "", "proton", ""),
        ("local-doom", "Doom", "umu", "/opt/GE-Proton9-1"),
        ("local-quake", "Quake", "native", "/usr/bin/wine"),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.runtime.type = kind
        cfg.runtime.tool = tool
        C.save(cfg)

    def wine_cells():
        model = GameListModel()
        return {
            model.data(model.index(i, 0), model.IdRole): model.rowData(i)["gameWine"]
            for i in range(model.rowCount())
        }

    monkeypatch.setattr(pmod, "compat_tool_name", lambda appid: "steamlinuxruntime_sniper")
    cells = wine_cells()
    assert cells["steam-214"] == "—"  # Steam native: no Wine
    assert cells["steam-213"] == "—"  # Steam Linux Runtime tool, not Wine
    assert cells["local-doom"] == "GE-Proton9-1"  # basename, not PROTONPATH
    assert cells["local-quake"] == "—"  # stale tool on a native game
    monkeypatch.setattr(pmod, "compat_tool_name", lambda appid: "proton_9")
    assert wine_cells()["steam-213"] == "proton_9"


def test_runtime_column_short_labels(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid, name, kind, steam_runtime in (
        ("steam-213", "", "native", ""),
        ("local-a", "A", "native", "sniper"),
        ("local-b", "B", "native", ""),
        ("local-c", "C", "umu", ""),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.runtime.type = kind
        cfg.runtime.steam_runtime = steam_runtime
        cfg.runtime.tool = "/opt/GE-Proton9-1" if kind == "umu" else ""
        C.save(cfg)
    model = GameListModel()
    cells = {
        model.data(model.index(i, 0), model.IdRole): model.rowData(i)["gameRuntime"]
        for i in range(model.rowCount())
    }
    assert cells["steam-213"] == "SLR"
    assert cells["local-a"] == "SLR 3.0"
    assert cells["local-b"] == "Native"
    assert cells["local-c"] == "UMU"


def test_history_summary_carries_installed(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "steam-42"
    cfg.general.name = "Doom"
    C.save(cfg)
    log = xdg.log_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("2026-01-01T10:00:00 appid=steam-42 exit=0 dur=60 cmd=doom\n", encoding="utf-8")
    summary = GameListModel().historySummary()
    assert summary[0]["appid"] == "steam-42"
    stamp = C.load("steam-42").general.installed_at
    assert summary[0]["installed"] == stamp.replace("T", " ")[:16]


def test_finished_session_refreshes_played_columns(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    assert model.rowData(0)["gameLastPlayed"] == "—"
    xdg.log_file().parent.mkdir(parents=True, exist_ok=True)
    xdg.log_file().write_text(
        "2026-01-02T10:00:00 appid=local-doom exit=0 dur=60 cmd=tkarcade\n",
        encoding="utf-8",
    )
    model._poll_history()
    row = model.rowData(0)
    assert row["gamePlayed"] == "1m 00s"
    assert row["gamePlayedSecs"] == 60
    assert row["gameLastPlayed"] == "2026-01-02 10:00"
    resets = []
    model.modelReset.connect(lambda: resets.append(True))
    model._poll_history()
    assert resets == []


def test_settings_preview_diff(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    res = model.previewCommand(
        "local-doom", {"custom_executable": "/bin/true", "runtime_type": "native"}
    )
    assert "/bin/true" in res["command"]
    assert isinstance(res["warnings"], list)
    assert res["wrappers"] != ""
    assert model.diffDefaults("", {}) == ""
    diff = model.diffDefaults(
        "local-doom", {"custom_executable": "/bin/true", "runtime_type": "native"}
    )
    assert "custom_executable" in diff


def test_settings_load_warning(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    assert GameListModel().loadGame("local-doom")["load_warning"] == ""
    C.game_file("local-doom").write_text("general = [broken\n")
    assert "invalid TOML" in GameListModel().loadGame("local-doom")["load_warning"]


def test_settings_tool_availability(qgui_app, xdg_env, monkeypatch):
    import shutil

    from tkarcade.gui.model import GameListModel

    assert GameListModel().toolAvailable("sh") is True
    assert GameListModel().toolAvailable("tkarcade-no-such-tool-xyz") is False
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    assert GameListModel().toolAvailable("sh") is False


def test_settings_dependency_status(qgui_app, xdg_env, monkeypatch):
    import shutil as shutilmod

    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    model = GameListModel()
    existing = lambda name, *a, **k: f"/usr/bin/{name}"  # noqa: E731

    # A clean local game: no prefix, every probed tool present but off.
    monkeypatch.setattr(shutilmod, "which", existing)
    rows = model.dependencyStatus("local-doom", {})
    by_key = {row["key"]: row for row in rows}
    assert by_key["custom_prefix"]["msg"] == "prefix-none"
    assert by_key["mangohud"]["kind"] == "ok"
    assert by_key["mangohud"]["msg"] == "binary-off"
    assert by_key["mangohud"]["args"] == ["mangohud", "/usr/bin/mangohud"]
    # The wording is QML's business (GameSettings.statusText).
    assert "text" not in by_key["mangohud"]
    # Steam options only exist for Steam games.
    assert "steam-options" not in by_key
    # Both wheels are listed while neither is enabled.
    assert "gamemoderun" in by_key and "game-performance" in by_key

    # Cachy's wheel sidelines Feral's (and vice versa).
    keys = [row["key"] for row in model.dependencyStatus("local-doom", {"gamemode_cachy": True})]
    assert "game-performance" in keys and "gamemoderun" not in keys
    keys = [row["key"] for row in model.dependencyStatus("local-doom", {"gamemode_feral": True})]
    assert "gamemoderun" in keys and "game-performance" not in keys

    # Missing binaries: a warning when enabled, a note when off.
    monkeypatch.setattr(shutilmod, "which", lambda name, *a, **k: None)
    by_key = {
        row["key"]: row for row in model.dependencyStatus("local-doom", {"mangohud_enable": True})
    }
    assert by_key["mangohud"]["kind"] == "warn"
    assert by_key["mangohud"]["msg"] == "binary-missing"
    assert by_key["gamescope"]["kind"] == "note"
    assert by_key["rt-upscale"]["msg"] == "binary-absent"

    # Empty hook paths stay hidden; a broken one warns and links to its folder.
    monkeypatch.setattr(shutilmod, "which", lambda name, *a, **k: None)
    sibling = C.game_file("local-doom").parent
    rows = model.dependencyStatus(
        "local-doom", {"pre_command": str(sibling / "gone.sh"), "post_command": ""}
    )
    by_key = {row["key"]: row for row in rows}
    assert "post_hook" not in by_key
    assert by_key["pre_hook"]["kind"] == "warn"
    assert by_key["pre_hook"]["msg"] == "hook-missing"
    assert by_key["pre_hook"]["args"] == ["pre-hook", str(sibling / "gone.sh")]
    assert by_key["pre_hook"]["link"] == str(sibling)

    # The prefix probe reports the wrapper it would run ('' when missing).
    monkeypatch.setattr(shutilmod, "which", existing)
    rows = model.dependencyStatus("local-doom", {"custom_prefix": "zink-run"})
    entry = next(r for r in rows if r["key"] == "custom_prefix")
    assert entry["msg"] == "binary-ok"
    assert entry["args"] == ["zink-run", "/usr/bin/zink-run"]


def test_settings_dependency_steam_options_cached(qgui_app, xdg_env, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    calls = []

    def probe(appid):
        calls.append(appid)
        return "ok", "tkarcade %command%"

    monkeypatch.setattr(S, "launch_options_status", probe)
    # The row compares the `tkarcade` on PATH with this build: pin the
    # probe so the test never spawns an installed binary.
    import tkarcade.gui.model as modelmod
    from tkarcade import __version__ as gui_version

    monkeypatch.setattr(
        modelmod, "_path_tkarcade_version", lambda: ("/usr/bin/tkarcade", gui_version)
    )
    model = GameListModel()
    rows = model.dependencyStatus("620", {}, check_steam=True)
    assert [row["key"] for row in rows].count("steam-options") == 1
    entry = next(row for row in rows if row["key"] == "steam-options")
    # The raw options travel to QML, which words and translates the line.
    assert entry["msg"] == "steam-ok"
    assert entry["args"] == ["tkarcade %command%"]
    # Keystroke refreshes reuse the probe; the dialog asks again explicitly.
    model.dependencyStatus("620", {"mangohud_enable": True})
    model.dependencyStatus("620", {"mangohud_enable": True})
    assert calls == ["620"]
    model.dependencyStatus("620", {}, check_steam=True)
    assert calls == ["620", "620"]

    # A stale system package is named instead of silently launching it.
    monkeypatch.setattr(
        modelmod, "_path_tkarcade_version", lambda: ("/usr/bin/tkarcade", "0.0.0.old")
    )
    entry = next(
        row for row in model.dependencyStatus("620", {}, True) if row["key"] == "steam-options"
    )
    assert entry["kind"] == "warn"
    assert entry["msg"] == "steam-stale"
    assert entry["args"] == ["/usr/bin/tkarcade", "0.0.0.old", gui_version]
    # Not on PATH at all: Steam would fail to expand the options.
    monkeypatch.setattr(modelmod, "_path_tkarcade_version", lambda: ("", ""))
    entry = next(
        row for row in model.dependencyStatus("620", {}, True) if row["key"] == "steam-options"
    )
    assert entry["msg"] == "steam-no-binary"


def test_settings_env_bulk_preset(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.envToText([{"key": "A", "value": "1"}, {"key": "", "value": "x"}]) == "A=1"
    assert model.textToEnv("# c\n\nA=1\nB = x y\nBAD\n=novalue\n") == [
        {"key": "A", "value": "1"},
        {"key": "B", "value": " x y"},
    ]
    labels = model.envPresetLabels()
    assert len(labels) > 0
    name = model.envPresetName(labels[0])
    assert name != ""
    assert model.envPresetName("no such preset") == ""
    assert isinstance(model.envPresetMismatch(name, ""), str)
    res = model.applyEnvPreset([], name)
    assert res["added"] > 0
    again = model.applyEnvPreset(res["rows"], name)
    assert again["added"] == 0
    assert len(again["rows"]) == len(res["rows"])


def test_env_preset_checks_the_local_proton(qgui_app, xdg_env, tmp_path, monkeypatch):
    """Proton-only presets match the runtime a local game launches with."""
    from tkarcade.gui.model import GameListModel

    proton = tmp_path / "GE-Proton9-20"
    proton.mkdir()
    (proton / "proton").write_text("#!/bin/sh\n")
    for appid, kind, tool in (
        ("local-umu", "umu", str(proton)),
        ("local-wine", "wine", ""),
        ("local-native", "native", ""),
        ("steam-620", "proton", ""),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.type = kind
        cfg.runtime.tool = tool
        C.save(cfg)

    model = GameListModel()
    name = "Proton Wayland"
    assert model.envPresetMismatch(name, "local-umu") == ""
    # No Proton at all: the preset's tuple cannot match.
    assert model.envPresetMismatch(name, "local-wine") == "ge/cachyos/dw Proton"
    assert model.envPresetMismatch(name, "local-native") == "ge/cachyos/dw Proton"
    # A Steam game with no compat-tool mapping stays unknown (offered).
    monkeypatch.setattr("tkarcade.proton.compat_tool_name", lambda appid: None)
    assert model.envPresetMismatch(name, "steam-620") == ""
    monkeypatch.setattr("tkarcade.proton.compat_tool_name", lambda appid: "proton_9")
    assert model.envPresetMismatch(name, "steam-620") == "ge/cachyos/dw Proton"

    cachy = tmp_path / "proton-cachyos-slr"
    cachy.mkdir()
    (cachy / "proton").write_text("#!/bin/sh\n")
    cfg = C.load("local-umu")
    cfg.runtime.tool = str(cachy)
    C.save(cfg)
    assert model.envPresetMismatch(name, "local-umu") == ""
    # umu without a Proton install is as unusable as no Proton at all.
    cfg.runtime.tool = ""
    C.save(cfg)
    assert model.envPresetMismatch(name, "local-umu") == "ge/cachyos/dw Proton"


def test_clone_reset_games(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid in ("local-doom", "local-quake"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = appid
        cfg.runtime.prefix_name = f"{appid}-prefix"
        if appid == "local-doom":
            cfg.general.custom_executable = "/bin/true"
            cfg.runtime.type = "wine"
            cfg.runtime.tool = "/opt/wine/bin/wine"
            cfg.runtime.prefix = "/tmp/doom-prefix"
        C.save(cfg)
    template = C.load_defaults()
    template.general.menu_timeout = 7
    C.save_defaults(template)
    prof = C.profiles_dir("local-doom")
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "fast.toml").write_text("[general]\n")
    model = GameListModel()
    targets = model.cloneTargets("local-doom")
    assert targets == [["local-quake", "local-quake"]]
    assert model.cloneGameTo("local-doom", "???", False) == "Invalid game ID: ???"
    assert model.cloneGameTo("local-doom", "local-doom", False) == "Source and Target Are the Same."
    assert model.cloneGameTo("local-doom", "local-quake", False) == "OVERWRITE"
    assert model.cloneGameTo("local-doom", "local-new", False) == "Cloned local-doom to local-new."
    assert C.game_file("local-new").is_file()
    assert (C.profiles_dir("local-new") / "fast.toml").is_file()
    assert model.cloneGameTo("local-doom", "570", False) == (
        "Cloned local-doom to steam-570. Review the Runtime for the New Origin."
    )
    assert C.game_file("steam-570").is_file()
    assert model.cloneGameTo("local-doom", "Doom2", False) == "Cloned local-doom to local-doom2."
    assert C.game_file("local-doom2").is_file()
    assert model.cloneGameTo("local-doom", "local-quake", True).startswith("Cloned")
    # The template carries the game's identity; every other field is the
    # Global Defaults template.
    tpl = model.templateGame("local-doom")
    assert tpl["name"] == "local-doom"
    assert tpl["custom_executable"] == "/bin/true"
    assert tpl["runtime_type"] == "wine"
    assert tpl["runtime_tool"] == "/opt/wine/bin/wine"
    assert tpl["runtime_prefix"] == "/tmp/doom-prefix"
    assert tpl["runtime_prefix_name"] == "local-doom-prefix"
    assert tpl["menu_timeout"] == 7
    assert model.resetGames([]) == "Select Games First."
    assert model.resetGames(["local-doom"]) == "Reset 1 Game(s) to the Global Defaults Template."
    reset = C.load("local-doom")
    assert reset.general.name == "local-doom"
    assert reset.general.custom_executable == "/bin/true"
    assert reset.runtime.type == "wine"
    assert reset.runtime.tool == "/opt/wine/bin/wine"
    assert reset.runtime.prefix == "/tmp/doom-prefix"
    assert reset.runtime.prefix_name == "local-doom-prefix"
    assert reset.general.menu_timeout == 7
    assert (C.profiles_dir("local-doom") / "fast.toml").is_file()
    assert model.resetGames(["steam-570"]) == "Reset 1 Game(s) to the Global Defaults Template."
    assert C.load("steam-570").general.name == ""


def test_settings_steam_create(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    assert model.saveGame("99", {"runtime_type": "proton"}) == "99"
    assert C.game_file("99").is_file()
    assert C.load("99").runtime.type == "proton"


def test_icon_name_first_available(qgui_app, xdg_env, monkeypatch):
    from PySide6.QtGui import QIcon

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: name == "table")
    assert model.iconName(["view-column", "table"]) == "table"
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: True)
    assert model.iconName(["view-column", "table"]) == "view-column"
    monkeypatch.setattr(QIcon, "hasThemeIcon", lambda name: False)
    assert model.iconName(["view-column", "table"]) == "view-column"
    assert model.iconName([]) == ""


def test_settings_ludusavi_system_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.ludusavi.enable = True
    cfg.ludusavi.name_override = "Doom 3"
    cfg.session.inhibit_idle = True
    cfg.network.block_internet = True
    cfg.nightlight.disable_during_game = True
    cfg.nightlight.provider = "plasma"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("local-doom")
    assert fields["ludusavi_enable"] is True
    assert fields["ludusavi_restore"] is True
    assert fields["ludusavi_name"] == "Doom 3"
    assert fields["inhibit_idle"] is True
    assert fields["block_internet"] is True
    assert fields["nl_provider"] == "plasma"
    assert model.gameLogFile("local-doom").endswith("local-doom.log")
    out = dict(fields)
    out["ludusavi_backup"] = False
    out["notify_on_launch"] = False
    out["nl_provider"] = "bogus"
    assert model.saveGame("local-doom", out) == "local-doom"
    reloaded = C.load("local-doom")
    assert reloaded.ludusavi.backup is False
    assert reloaded.notifications.notify_on_launch is False
    assert reloaded.nightlight.provider == "auto"


def test_settings_wine_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "steam-99"
    cfg.runtime.fresh_prefix = True
    cfg.runtime.winetricks_verbs = ["dotnet48"]
    cfg.runtime.tool = "GE-Proton9-1"
    cfg.runtime.prefix = "/tmp/opencode/pfx"
    cfg.debug.proton_log = True
    cfg.debug.winedebug = "+err"
    C.save(cfg)
    model = GameListModel()
    fields = model.loadGame("steam-99")
    assert fields["fresh_prefix"] is True
    assert fields["winetricks_verbs"] == "dotnet48"
    assert fields["runtime_tool"] == "GE-Proton9-1"
    assert fields["runtime_prefix"] == "/tmp/opencode/pfx"
    assert fields["proton_log"] is True
    assert fields["winedebug"] == "+err"
    assert model.protonLogDir("steam-99").endswith("steam-99/proton")
    out = dict(fields)
    out["winedebug"] = "+d3d11"
    out["winetricks_verbs"] = "vcrun2022 dotnet48"
    out["runtime_tool"] = "wine-9.0"
    assert model.saveGame("steam-99", out) == "steam-99"
    reloaded = C.load("steam-99")
    assert reloaded.debug.winedebug == "+d3d11"
    assert reloaded.runtime.winetricks_verbs == ["vcrun2022", "dotnet48"]
    assert reloaded.runtime.tool == "wine-9.0"


def test_prefix_name_state_and_choices(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    base = tmp_path / "prefixes"
    (base / "Doom" / "drive_c").mkdir(parents=True)
    (base / "Doom" / "system.reg").write_text("")
    (base / "NotAPrefix").mkdir()

    for appid, name in (("local-a", "Doom"), ("local-b", "Doom")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.prefix_name = name
        C.save(cfg)

    model = GameListModel()
    fields = model.loadGame("local-a")
    assert fields["runtime_prefix_name"] == "Doom"
    out = dict(fields)
    out["runtime_prefix_name"] = "Doom Eternal"
    assert model.saveGame("local-a", out) == "local-a"
    assert C.load("local-a").runtime.prefix_name == "Doom Eternal"

    state = model.prefixNameState("local-a", "Doom")
    assert state["target"] == str(base / "Doom")
    assert state["sanitized"] == "Doom"
    assert state["renamed"] is False
    assert state["exists"] is True
    assert state["is_prefix"] is True
    assert len(state["shared"]) == 1

    renamed = model.prefixNameState("local-a", "My Doom")
    assert renamed["sanitized"] == "MyDoom"
    assert renamed["renamed"] is True
    assert renamed["exists"] is False

    # A typed dir is the base: the prefix is always a subfolder of it.
    custom = tmp_path / "elsewhere" / "base"
    state = model.prefixNameState("local-a", "Doom", str(custom))
    assert state["target"] == str(custom / "Doom")
    assert state["exists"] is False
    # With no explicit name the game name derives the folder.
    derived = model.prefixNameState("local-a", "", "", "TK's good-game_1")
    assert derived["target"] == str(base / "TKsGoodGame1")
    assert derived["renamed"] is False

    choices = model.prefixChoices("local-a")
    assert [c["name"] for c in choices] == ["Doom"]
    assert choices[0]["path"] == str(base / "Doom")

    # A per-game base wins over the Preferences base for the picker.
    other_base = tmp_path / "other"
    other_prefix = other_base / "Styled"
    (other_prefix / "drive_c").mkdir(parents=True)
    (other_prefix / "system.reg").write_text("")
    custom_choices = model.prefixChoices("local-a", str(other_base))
    assert [c["name"] for c in custom_choices] == ["Styled"]
    assert custom_choices[0]["path"] == str(other_prefix)


def test_prefix_name_state_steam_uses_the_custom_dir(qgui_app, xdg_env, tmp_path):
    """A Steam field is the compatdata dir itself, never <base>/<stem>."""
    from tkarcade.gui.model import GameListModel

    custom = tmp_path / "custom-compatdata"
    (custom / "pfx").mkdir(parents=True)
    for appid in ("steam-99", "steam-100"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.type = "proton"
        cfg.runtime.prefix = str(custom)
        C.save(cfg)

    model = GameListModel()
    state = model.prefixNameState("steam-99", "", str(custom), "")
    assert state["steam"] is True
    assert state["target"] == str(custom)
    assert state["exists"] is True
    assert state["renamed"] is False
    assert state["shared"] == ["steam-100"]

    # An empty field means Steam's default dir: no target to report.
    default = model.prefixNameState("steam-99", "", "", "")
    assert default["target"] == ""
    assert default["exists"] is False
    assert default["shared"] == []

    local = model.prefixNameState("local-x", "", "", "")
    assert local["steam"] is False
    assert local["target"] != ""


def test_resolved_prefix_keeps_local_compatdata_dirs(qgui_app, xdg_env, tmp_path):
    """Only a Steam game's compatdata dir is Steam-owned."""
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "compatdata" / "custom")
    C.save_preferences(prefs)
    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.runtime.type = "wine"
    C.save(local)
    prefix = tmp_path / "compatdata" / "custom" / "local-doom"
    prefix.mkdir(parents=True)

    steam_dir = tmp_path / "steam" / "compatdata" / "77"
    steam_dir.mkdir(parents=True)
    steam = C.GameConfig()
    steam.general.appid = "steam-77"
    steam.runtime.prefix = str(steam_dir)
    C.save(steam)

    model = GameListModel()
    assert model._resolved_prefix("local-doom") == prefix.resolve()
    assert model._resolved_prefix("steam-77") is None


def test_prefix_users_skip_steam_default(qgui_app, xdg_env, tmp_path, monkeypatch):
    """Sharing counts local and custom prefixes; Steam's compatdata is Steam's."""
    from tkarcade.gui.model import GameListModel

    compatdata = tmp_path / "steamapps" / "compatdata" / "77"
    compatdata.mkdir(parents=True)
    monkeypatch.setenv("STEAM_ROOT", str(tmp_path))
    custom = tmp_path / "custom"
    base = tmp_path / "base"
    for appid, kind, prefix in (
        ("steam-77", "proton", ""),
        ("steam-78", "proton", str(custom)),
        ("local-doom", "wine", str(base)),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.type = kind
        cfg.runtime.prefix = prefix
        C.save(cfg)

    model = GameListModel()
    users = model._prefix_users(C.load_preferences())
    assert users[str(custom)] == ["steam-78"]
    assert str(compatdata) not in users
    assert users[str(base / "local-doom")] == ["local-doom"]


def test_launch_runtime_label_names_the_runtime(qgui_app, xdg_env, tmp_path, monkeypatch):
    """The pre-launch line follows the config instead of assuming Proton."""
    from tkarcade import proton as P
    from tkarcade.gui.model import GameListModel

    proton = tmp_path / "GE-Proton9-20"
    proton.mkdir()
    (proton / "proton").write_text("#!/bin/sh\n")
    wine = tmp_path / "wine"
    wine.write_text("#!/bin/sh\n")
    wine.chmod(0o755)
    for appid, kind, tool in (
        ("steam-620", "proton", ""),
        ("local-umu", "umu", str(proton)),
        ("local-wine", "wine", str(wine)),
        ("local-native", "native", ""),
        ("steam-730", "native", ""),
        ("local-broken", "proton", ""),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.runtime.type = kind
        cfg.runtime.tool = tool
        C.save(cfg)

    monkeypatch.setattr(P, "tool_display", lambda appid: "GE-Proton9-20 (build 1)")
    model = GameListModel()
    assert model.launchRuntimeLabel("") == "—"
    assert model.launchRuntimeLabel("steam-620") == "Proton: GE-Proton9-20 (build 1)"
    assert model.launchRuntimeLabel("local-umu") == "UMU: GE-Proton9-20"
    assert model.launchRuntimeLabel("local-wine") == "Wine: wine"
    assert model.launchRuntimeLabel("local-native") == "Native"
    assert model.launchRuntimeLabel("steam-730") == "Steam Runtime"
    # Proton is Steam's own: an invalid local pairing labels nothing.
    assert model.launchRuntimeLabel("local-broken") == "Runtime Not Set"
    assert model.launchRuntimeLabel("missing") == "Runtime Not Set"

    native = C.load("local-native")
    native.runtime.steam_runtime = "sniper"
    C.save(native)
    assert model.launchRuntimeLabel("local-native") == "Steam Runtime (sniper)"


def test_row_skips_protondb_for_local_games(qgui_app, xdg_env, monkeypatch):
    """A local game without a Steam store link keeps the column blank."""
    from tkarcade.gui import model as M

    for appid in ("local-doom", "steam-620"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    model = M.GameListModel()
    calls = []
    monkeypatch.setattr(
        M.pdbmod, "cached", lambda appid, target="": calls.append(appid) or ({}, False)
    )
    local = model._row("local-doom", {}, {})
    assert calls == []
    assert local[4] == ""
    steam = model._row("steam-620", {}, {})
    assert calls == ["steam-620"]
    assert steam[4] == ""


def test_row_uses_the_local_steam_link(qgui_app, xdg_env, monkeypatch):
    """A local game with a Steam store link shows the cached tier."""
    from tkarcade.gui import model as M

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.metadata.steam_appid = "620"
    C.save(cfg)
    model = M.GameListModel()
    calls = []

    def fake_cached(appid, target=""):
        calls.append((appid, target))
        return {"tier": "gold"}, True

    monkeypatch.setattr(M.pdbmod, "cached", fake_cached)
    row = model._row("local-doom", {}, {})
    assert calls == [("local-doom", "620")]
    assert row[4] == "Gold"


def test_row_styles_a_pending_tier(qgui_app, xdg_env, monkeypatch):
    """A tier without its own style left the badge a black bar."""
    from tkarcade.gui import model as M

    cfg = C.GameConfig()
    cfg.general.appid = "steam-620"
    C.save(cfg)
    model = M.GameListModel()
    monkeypatch.setattr(M.pdbmod, "cached", lambda appid, target="": ({"tier": "pending"}, True))
    row = model._row("steam-620", {}, {})
    assert row[4] == "Pending"
    assert row[5] == "#757575"
    assert row[6] == "#000000"


def test_save_game_pins_the_prefix_folder(qgui_app, xdg_env, tmp_path):
    """The name-derived folder is stored, so a rename never moves it."""
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    model = GameListModel()
    fields = model.factoryGame("")
    fields.update(
        {
            "name": "TK's good-game_1",
            "custom_executable": "/bin/true",
            "runtime_type": "wine",
        }
    )
    appid = model.saveGame("", fields)
    assert appid
    cfg = C.load(appid)
    assert cfg.runtime.prefix_name == "TKsGoodGame1"
    pinned = C.prefix_dir(appid, cfg.runtime.prefix, prefs.prefix_base, cfg.runtime.prefix_name)
    assert pinned == tmp_path / "prefixes" / "TKsGoodGame1"

    # Renaming the game keeps both the stored name and the path.
    out = dict(model.loadGame(appid))
    out["name"] = "Renamed"
    assert model.saveGame(appid, out) == appid
    cfg = C.load(appid)
    assert cfg.runtime.prefix_name == "TKsGoodGame1"
    assert (
        C.prefix_dir(appid, cfg.runtime.prefix, prefs.prefix_base, cfg.runtime.prefix_name)
        == pinned
    )


def test_ensure_and_clear_the_local_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    base = tmp_path / "prefixes"
    for appid, name in (("local-a", "Doom"), ("local-b", "Doom")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.runtime.type = "wine"
        cfg.runtime.prefix_name = "Doom"  # both share the same prefix
        C.save(cfg)
    model = GameListModel()
    assert model.ensurePrefix("local-a") == ""
    assert (base / "Doom").is_dir()
    # The base itself is never the target, and a shared prefix is refused.
    assert model.clearCustomPrefix("local-a").startswith("Shared Prefix")
    assert (base / "Doom").is_dir()
    (C.game_file("local-b")).unlink()
    assert model.clearCustomPrefix("local-a") == f"Cleared {base / 'Doom'}."
    assert not (base / "Doom").exists()
    assert base.is_dir()


def test_clear_prefix_refuses_a_non_prefix_directory(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    prefix = tmp_path / "prefixes" / "Doom"
    prefix.mkdir(parents=True)
    (prefix / "save.dat").write_text("saves", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix_name = "Doom"
    C.save(cfg)
    model = GameListModel()
    assert model.clearCustomPrefix("local-doom").startswith("Refusing to Delete")
    assert (prefix / "save.dat").is_file()


def test_clear_prefix_deletes_a_real_wine_prefix(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    prefs = C.load_preferences()
    prefs.prefix_base = str(tmp_path / "prefixes")
    C.save_preferences(prefs)
    prefix = tmp_path / "prefixes" / "Doom"
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "system.reg").write_text("", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix_name = "Doom"
    C.save(cfg)
    model = GameListModel()
    assert model.clearCustomPrefix("local-doom") == f"Cleared {prefix}."
    assert not prefix.exists()


def test_cleanup_keeps_a_non_prefix_directory(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    base = tmp_path / "pfx"
    prefix = base / "Doom"
    prefix.mkdir(parents=True)
    (prefix / "save.dat").write_text("saves", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    model = GameListModel()
    model.removeGames(["local-doom"])
    assert model.cleanLeftovers(["local-doom"], True) == 0
    assert (prefix / "save.dat").is_file()


def test_apply_wine_version_keeps_config_vdf_on_dump_failure(
    qgui_app, xdg_env, monkeypatch, tmp_path
):
    import vdf

    from tkarcade.gui.model import GameListModel

    root = tmp_path / "steam"
    (root / "config").mkdir(parents=True)
    config_vdf = root / "config" / "config.vdf"
    original = (
        '"InstallConfigStore"\n'
        "{\n"
        '  "Software"\n'
        "  {\n"
        '    "Valve"\n'
        "    {\n"
        '      "Steam"\n'
        "      {\n"
        '        "CompatToolMapping"\n'
        "        {\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    config_vdf.write_text(original, encoding="utf-8")
    monkeypatch.setenv("STEAM_ROOT", str(root))
    model = GameListModel()
    monkeypatch.setattr(model, "steamRunning", lambda: False)

    def boom(*_args, **_kwargs):
        raise RuntimeError("dump failed")

    monkeypatch.setattr(vdf, "dump", boom)
    assert model.applyWineVersion("steam-570", "proton_9").startswith("Could Not Update")
    assert config_vdf.read_text(encoding="utf-8") == original


def test_context_actions_follow_origin_and_runtime(qgui_app, xdg_env, tmp_path, monkeypatch):
    import os

    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    steam_install = tmp_path / "steam" / "common" / "Game"
    steam_install.mkdir(parents=True)
    compat = tmp_path / "steam" / "compatdata" / "77"
    shader = tmp_path / "steam" / "shadercache" / "77"
    shader.mkdir(parents=True)
    (shader / "cache.bin").write_bytes(b"\0" * 2048)
    monkeypatch.setattr(S, "install_dir", lambda appid: steam_install)
    monkeypatch.setattr(S, "prefix_dir", lambda appid: compat)
    monkeypatch.setattr(S, "shader_dir", lambda appid: shader)

    for appid, runtime in (("steam-77", "proton"), ("steam-78", "native")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = runtime
        cfg.runtime.type = runtime
        C.save(cfg)

    prefs = C.load_preferences()
    prefs.prefix_base = os.fspath(tmp_path / "prefixes")
    C.save_preferences(prefs)

    exe = tmp_path / "games" / "doom" / "doom"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = os.fspath(exe)
    local.runtime.type = "native"
    C.save(local)

    wine = C.GameConfig()
    wine.general.appid = "local-wine"
    wine.general.name = "Wine Game"
    wine.runtime.type = "wine"
    wine.runtime.prefix_name = "WineGame"
    C.save(wine)

    umu = C.GameConfig()
    umu.general.appid = "local-umu"
    umu.general.name = "Umu Game"
    umu.runtime.type = "umu"
    umu.runtime.prefix_name = "UmuGame"
    C.save(umu)
    (tmp_path / "prefixes" / "UmuGame").mkdir(parents=True)

    model = GameListModel()

    proton = model.contextActions("steam-77")
    assert proton["is_steam"] is True
    assert proton["steam_appid"] == "77"
    assert proton["install"] == os.fspath(steam_install)
    assert proton["prefix"] == ""  # compatdata not created yet
    assert proton["prefix_applicable"] is True
    assert proton["shader"] == os.fspath(shader)
    # The size is walked off the GUI thread; the context menu fills in.
    assert proton["shader_size"] == ""
    deadline = time.time() + 5
    while "steam-77" not in model._shader_sizes and time.time() < deadline:
        time.sleep(0.01)
    assert model.shaderSize("steam-77") == "2.0 KB"

    native_steam = model.contextActions("steam-78")
    assert native_steam["install"] == os.fspath(steam_install)
    assert native_steam["prefix"] == ""
    assert native_steam["prefix_applicable"] is False
    assert native_steam["shader"] == os.fspath(shader)

    compat.mkdir(parents=True)
    assert model.contextActions("steam-77")["prefix"] == os.fspath(compat)

    native = model.contextActions("local-doom")
    assert native["is_steam"] is False
    assert native["steam_appid"] == ""
    assert native["install"] == os.fspath(exe.parent)
    assert native["prefix"] == ""
    assert native["prefix_applicable"] is False
    assert native["shader"] == ""
    assert native["shader_size"] == ""

    override = tmp_path / "cwd"
    override.mkdir()
    local.general.launch_cwd = os.fspath(override)
    C.save(local)
    assert model.contextActions("local-doom")["install"] == os.fspath(override)

    wine_actions = model.contextActions("local-wine")
    assert wine_actions["prefix"] == ""  # WINEPREFIX not created yet
    assert wine_actions["prefix_applicable"] is True
    wine_prefix = tmp_path / "prefixes" / "WineGame"
    wine_prefix.mkdir(parents=True)
    assert model.contextActions("local-wine")["prefix"] == os.fspath(wine_prefix)

    umu_actions = model.contextActions("local-umu")
    assert umu_actions["prefix"] == os.fspath(tmp_path / "prefixes" / "UmuGame")
    assert umu_actions["prefix_applicable"] is True
    assert umu_actions["install"] == ""  # no executable configured


def test_settings_defaults_roundtrip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    fields = model.loadDefaults()
    assert fields["gamemode_feral"] is False
    out = dict(fields)
    out["gamemode_feral"] = True
    out["menu_timeout"] = 11
    assert model.saveDefaults(out) is True
    assert C.load_defaults().gamemode.feral_gamemode is True
    assert C.load_defaults().general.menu_timeout == 11
    assert model.factoryGame("local-doom")["name"] == ""
    # Reset applies the template (menu_timeout 11 above), not factory values.
    assert model.templateGame("local-doom")["menu_timeout"] == 11
    assert model.templateGame("local-doom")["appid"] == "local-doom"
    # Downgrade gate: template and live file here are current, the last one
    # stamps a future version.
    assert model.needsNewerApp("local-doom", "") is False
    assert model.needsNewerApp("", "") is False
    C.game_file("local-new").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("local-new").write_text(
        '[general]\nappid = "local-new"\nconfig_version = 999\n', encoding="utf-8"
    )
    assert model.needsNewerApp("local-new", "") is True


def test_settings_coverage_reports(qgui_app, xdg_env):
    import threading

    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    done, out = threading.Event(), []
    model.coverageFinished.connect(lambda s, d: (out.append((s, d)), done.set()))
    model.checkCoverage("local-missing", "")
    import time

    deadline = time.monotonic() + 30
    while not done.is_set() and time.monotonic() < deadline:
        qgui_app.processEvents()
        done.wait(0.05)
    assert done.is_set()
    assert out[0][0] in ("covered", "no-local-saves", "no-entry", "unavailable")


def test_settings_coverage_uses_the_dialog_name(qgui_app, xdg_env, monkeypatch):
    """A local game resolves saves by the dialog name, before any Save."""
    import time

    from tkarcade.backends import ludusavi as lumod
    from tkarcade.gui.model import GameListModel

    seen = []
    monkeypatch.setattr(
        lumod,
        "check_coverage",
        lambda appid, name="": (seen.append((appid, name)), ("no-entry", ""))[1],
    )
    model = GameListModel()

    def run(*args):
        out = []
        model.coverageFinished.connect(lambda s, d: out.append((s, d)))
        model.checkCoverage(*args)
        deadline = time.monotonic() + 30
        while not out and time.monotonic() < deadline:
            qgui_app.processEvents()
            time.sleep(0.01)
        model.coverageFinished.disconnect()
        assert out, f"no coverage result for {args}"
        return out[0]

    # The dialog name, the override, then Steam (its id infers the title).
    run("local-dialog", "", "Doom")
    run("local-dialog", "Other", "Doom")
    run("12345", "", "Portal 2")
    assert seen == [
        ("local-dialog", "Doom"),
        ("local-dialog", "Other"),
        ("12345", ""),
    ]

    # Without a dialog name a local game falls back to the saved one.
    cfg = C.GameConfig()
    cfg.general.appid = "local-saved"
    cfg.general.name = "Quake"
    C.save(cfg)
    run("local-saved", "", "")
    assert seen[-1] == ("local-saved", "Quake")


def test_export_import_tarball_roundtrip(qgui_app, xdg_env, tmp_path):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "steam-99"
    C.save(cfg)
    model = GameListModel()
    dest = tmp_path / "out.tar.gz"
    assert "Exported to" in model.exportTarball(str(dest))
    assert dest.is_file()
    assert model.exportTarball("") == ""
    assert model.exportTarball(str(tmp_path / "missing" / "x.tar.gz")).startswith("Export Failed")
    C.game_file("steam-99").unlink()
    assert model.importTarball(str(dest)) == "Imported 1 Game(s)"
    assert C.game_file("steam-99").is_file()
    assert model.importTarball("") == ""
    assert model.importTarball(str(tmp_path / "nope.tar.gz")).startswith("Import Failed")


def test_stl_import_flow(qgui_app, xdg_env, monkeypatch):
    import os
    from pathlib import Path

    import tkarcade.steam as steammod
    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(steammod, "list_games", lambda: [("steam-99", "Doom 3")])
    cfg = C.GameConfig()
    cfg.general.appid = "steam-99"
    C.save(cfg)
    stl_id = Path(os.environ["XDG_CONFIG_HOME"]) / "steamtinkerlaunch" / "gamecfgs" / "id"
    stl_id.mkdir(parents=True)
    (stl_id / "99.conf").write_text('USE_GAMEMODE="1"\n')
    model = GameListModel()
    assert model.stlCandidates() == [["steam-99", "Doom 3"]]
    assert "steamtinkerlaunch' Profile" in model.importStl(["steam-99"])
    assert C.profile_file("steam-99", "steamtinkerlaunch").is_file()
    assert "Skipped" in model.importStl(["steam-100"])
    assert model.importStl([]) == "Nothing Selected."


def test_import_predecessor_without_source(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    assert GameListModel().importPredecessor().startswith("Import Failed")


def _filtered(qgui_app, appids=("213", "local-doom")):
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid in appids:
        cfg = C.GameConfig()
        cfg.general.appid = appid
        if not appid[0].isdigit():
            cfg.general.name = "Doom"
        C.save(cfg)
    source = GameListModel()
    proxy = GameFilterModel()
    proxy.setSourceModel(source)
    return proxy


def test_proxy_is_thirteen_column_table(qgui_app, xdg_env):
    from PySide6.QtCore import Qt

    proxy = _filtered(qgui_app)
    assert proxy.columnCount() == 13
    assert proxy.columnCount(proxy.index(0, 0)) == 0
    assert [proxy.headerData(c, Qt.Orientation.Horizontal) for c in range(13)] == [
        "#",
        "Game",
        "Release Date",
        "Origin",
        "Platform",
        "Played",
        "Last Played",
        "Installed",
        "Runtime",
        "Wine",
        "ProtonDB",
        "Game ID",
        "Install Dir",
    ]
    assert proxy.data(proxy.index(0, 0)) == "1"
    # Sorted by name: the local game ("Doom") comes before "steam-213".
    assert proxy.data(proxy.index(0, 1)) == "Doom"
    assert proxy.data(proxy.index(1, 11)) == "steam-213"
    assert proxy.data(proxy.index(1, 3)) == "Steam"
    assert proxy.data(proxy.index(9, 0)) is None
    # custom roles stay row-based: delegates keep working per column
    from tkarcade.gui.model import GameListModel

    assert proxy.data(proxy.index(1, 4), GameListModel.IdRole) == "steam-213"


def test_proxy_move_hide_reset_columns(qgui_app, xdg_env):
    proxy = _filtered(qgui_app)
    proxy.moveColumn(11, 1)
    assert proxy.columnCount() == 13
    assert (
        proxy.headerData(2, __import__("PySide6.QtCore", fromlist=["x"]).Qt.Orientation.Horizontal)
        == "Origin"
    )
    assert C.load_preferences().column_order.split(",")[:4] == ["0", "1", "5", "11"]
    proxy.showOrigin = False
    assert proxy.columnCount() == 13  # hidden columns keep mapped slots
    assert "5" in C.load_preferences().hidden_columns.split(",")
    proxy.resetColumns()
    assert proxy.columnCount() == 13
    assert C.load_preferences().hidden_columns == "2,4,8,9,10"
    proxy.moveColumn(0, -1)  # edge: no-op, stays valid
    assert proxy.columnCount() == 13


def test_proxy_columns_migrate_saved_layout_once(qgui_app, xdg_env):
    prefs = C.load_preferences()
    prefs.column_order = "0,1,2,3,4,5,6,7,8,9,10,11,12"
    prefs.hidden_columns = "2,9"
    C.save_preferences(prefs)  # no column_layout_version: pre-defaults
    from tkarcade.gui.model import GameFilterModel, GameListModel

    proxy = GameFilterModel()
    proxy.setSourceModel(GameListModel())
    assert proxy._order == [0, 1, 11, 5, 7, 3, 6, 12, 8, 9, 4, 2, 10]
    assert proxy._hidden == {2, 4, 8, 9, 10}
    prefs = C.load_preferences()
    assert prefs.column_layout_version == C.COLUMN_LAYOUT_VERSION
    assert prefs.column_order == "0,1,11,5,7,3,6,12,8,9,4,2,10"
    assert prefs.hidden_columns == "2,4,8,9,10"
    # Once versioned, a custom layout survives the next load.
    prefs.column_order = "0,1,2,3,4,5,6,7,8,9,10,11,12"
    prefs.hidden_columns = ""
    C.save_preferences(prefs)
    again = GameFilterModel()
    again.setSourceModel(GameListModel())
    assert again._order == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert again._hidden == set()


def test_refresh_counts_only_steam_detected(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    model = GameListModel()
    model.refresh()
    assert model.steamDetectedCount == 0  # local games must not inflate it


def test_game_issues_cache_invalidated_on_refresh(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-broken"
    cfg.general.name = "Broken"
    cfg.general.custom_executable = "/nonexistent/doom"
    cfg.runtime.type = "native"
    C.save(cfg)  # missing executable -> validation issue
    model = GameListModel()
    assert model.gameIssues("local-broken") != []
    fixed = C.load("local-broken")
    fixed.general.custom_executable = "/bin/true"
    C.save(fixed)
    model.refresh()
    assert model.gameIssues("local-broken") == []


def test_issue_roles_expose_level_and_tip(qgui_app, xdg_env):
    from tkarcade.gui.model import GameListModel

    for appid, exe, post in (
        ("local-bad", "/nonexistent/game", ""),
        ("local-warn", "/bin/true", "/nonexistent/post"),
    ):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.custom_executable = exe
        cfg.pre_post.post_command = post
        cfg.runtime.type = "native"
        C.save(cfg)
    model = GameListModel()
    model.refresh()
    rows = {
        model.data(model.index(row, 0), GameListModel.IdRole): model.index(row, 0)
        for row in range(model.rowCount())
    }
    assert model.data(rows["local-bad"], GameListModel.IssueLevelRole) == "error"
    assert model.data(rows["local-warn"], GameListModel.IssueLevelRole) == "warning"
    tip = model.data(rows["local-bad"], GameListModel.IssuesTipRole)
    assert "Error: custom_executable not found" in tip
    assert "local-bad:" not in tip


def test_tray_recents_rows(qgui_app, xdg_env, monkeypatch):
    """Tray recents: [appid, label], gated by the quick-launch prefs."""
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(
        model,
        "historySummary",
        lambda: [
            {"appid": "99", "name": "Doom 3", "total": "1h"},
            {"appid": "local-doom", "name": "Doom", "total": "30m"},
        ],
    )
    prefs = C.load_preferences()
    prefs.tray_quick_launch = False
    C.save_preferences(prefs)
    assert model.trayRecentGames() == []
    prefs.tray_quick_launch = True
    prefs.tray_quick_count = 1
    C.save_preferences(prefs)
    assert model.trayRecentGames() == [["99", "Doom 3 (1h)"]]


def test_tray_action_dispatch(qgui_app, xdg_env, monkeypatch):
    """trayAction: registered entries run, "play:<appid>" plays."""
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    played = []
    monkeypatch.setattr(model, "play", lambda appid: played.append(appid) or True)
    ran = []
    model._tray_actions = {"prefs": lambda: ran.append("prefs")}
    assert model.trayDefaultsAvailable() is False
    model.trayAction("prefs")
    model.trayAction("play:local-doom")
    model.trayAction("")  # unknown entries are ignored
    model.trayAction("nope")
    assert ran == ["prefs"]
    assert played == ["local-doom"]
    model._tray_actions["defaults"] = lambda: None
    assert model.trayDefaultsAvailable() is True


def test_audio_sinks_pair_name_and_label(qgui_app, xdg_env, monkeypatch):
    """audioSinks keeps the node name for config and the label for the UI."""
    from tkarcade.backends import audio as aubackend
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    monkeypatch.setattr(
        aubackend,
        "list_sinks",
        lambda: [("alsa_hdmi", "HDMI Estéreo"), ("alsa_usb", "")],
    )
    assert model.audioSinks() == [["alsa_hdmi", "HDMI Estéreo"], ["alsa_usb", "alsa_usb"]]
    monkeypatch.setattr(aubackend, "list_sinks", lambda: [])
    assert model.audioSinks() == []


def test_model_running_role_and_terminate(qgui_app, xdg_env):
    import json
    import signal
    import subprocess
    import sys

    from tkarcade import running
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-run"
    cfg.general.name = "Runtime"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    try:
        path = running.record_path("local-run")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "appid": "local-run",
                    "pid": child.pid,
                    "start": running.process_start_time(child.pid),
                    "started": 0,
                }
            )
        )
        model = GameListModel()
        model._refresh_running()
        assert model.isRunning("local-run") is True
        assert model.runningIds == ["local-run"]
        row = next(
            i
            for i in range(model.rowCount())
            if model.data(model.index(i, 0), model.IdRole) == "local-run"
        )
        assert model.data(model.index(row, 0), model.RunningRole) is True
        assert model.rowData(row)["gameRunning"] is True
        reported = []
        model.terminateReported.connect(lambda *args: reported.append(args))
        assert model.terminate("local-run") is True
        assert child.wait(timeout=10) == -signal.SIGTERM
        assert reported == [(True, "Runtime", "")]
        model._refresh_running()
        assert model.isRunning("local-run") is False
        assert model.runningIds == []
        assert model.data(model.index(row, 0), model.RunningRole) is False
        # Stop the model's timers before the next test: its 10 s kill
        # timer would otherwise fire mid-QML-suite, in a process that no
        # longer owns the C++ object (pytestqt processes events there).
        model._stop_timers()
        model.deleteLater()
        qgui_app.processEvents()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        running.record_path("local-run").unlink(missing_ok=True)


def test_terminate_escalation_stops_when_the_record_goes(qgui_app, xdg_env, monkeypatch):
    """A game that exits inside the grace period cancels the pending SIGKILL."""
    from tkarcade import running
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-run"
    cfg.general.name = "Running"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    record = {"appid": "local-run", "pid": 4242, "start": 7, "started": 0}
    monkeypatch.setattr(model, "_load_running", lambda: {"local-run": record})
    monkeypatch.setattr(running, "terminate", lambda appid: record)
    model._refresh_running()
    assert model.terminate("local-run") is True
    assert model._kill_timer.isActive() is True
    # The game exits: the record disappears while the launcher's post-hook
    # may still be running, so the escalation must not fire.
    monkeypatch.setattr(model, "_load_running", lambda: {})
    model._refresh_running()
    assert model._kill_timer.isActive() is False
    assert model._kill_record is None
    model._stop_timers()
    model.deleteLater()
    qgui_app.processEvents()


def test_force_kill_requires_the_same_live_record(qgui_app, xdg_env, monkeypatch):
    """SIGKILL only goes out while the very launcher that was signalled lives."""
    from tkarcade import running
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    stale = {"appid": "local-run", "pid": 4242, "start": 7, "started": 0}
    fresh = {"appid": "local-run", "pid": 5252, "start": 9, "started": 0}
    killed = []
    monkeypatch.setattr(running, "kill", lambda record: killed.append(record) or True)
    monkeypatch.setattr(model, "_load_running", lambda: {})
    # The game exited and the launcher is in its post-hook: no record file.
    monkeypatch.setattr(running, "read", lambda appid: None)
    model._kill_record = stale
    model._force_kill()
    assert killed == []
    # A relaunch replaced the record: never kill the new launcher.
    monkeypatch.setattr(running, "read", lambda appid: fresh)
    model._kill_record = stale
    model._force_kill()
    assert killed == []
    # Same launcher still alive: escalate.
    monkeypatch.setattr(running, "read", lambda appid: stale)
    model._kill_record = stale
    model._force_kill()
    assert killed == [stale]
    model._stop_timers()
    model.deleteLater()
    qgui_app.processEvents()


def test_refresh_emits_running_changed(qgui_app, xdg_env, monkeypatch):
    """refresh() notifies runningIds bindings when the running set changes."""
    from PySide6.QtTest import QSignalSpy

    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-run"
    cfg.general.name = "Running"
    cfg.general.custom_executable = "/bin/true"
    cfg.runtime.type = "native"
    C.save(cfg)
    model = GameListModel()
    spy = QSignalSpy(model.runningChanged)
    record = {"appid": "local-run", "pid": 4242, "start": 7, "started": 0}
    monkeypatch.setattr(model, "_load_running", lambda: {"local-run": record})
    model.refresh()
    assert spy.count() == 1
    model.refresh()
    assert spy.count() == 1
    monkeypatch.setattr(model, "_load_running", lambda: {})
    model.refresh()
    assert spy.count() == 2
    model._stop_timers()
    model.deleteLater()
    qgui_app.processEvents()


def test_row_icon_uses_the_cached_artwork(qgui_app, xdg_env):
    """A local game's row icon is its own cached icon."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    icon = artwork.grid_path("local-doom", "icon")
    cover = artwork.grid_path("local-doom", "cover")
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(b"I")
    cover.write_bytes(b"C")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.IconRole) == str(icon)
    assert model.effectiveArtwork("local-doom", "icon") == str(icon)
    assert model.artworkStatus("local-doom") == "partial"
    assert model.artworkStatus("local-missing") == "none"


def test_artwork_preview_url_is_versioned_and_empty_when_missing(qgui_app, xdg_env):
    """The dialog previews the art the views use, stamped for QML caching."""
    import os

    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    icon = artwork.grid_path("local-doom", "icon")
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(b"I")
    model = _model(qgui_app)
    url = model.artworkPreview("local-doom", "icon")
    assert url == f"file://{icon}?v={icon.stat().st_mtime_ns}", url
    # A replaced file gets a new URL, so QML drops the cached picture.
    os.utime(icon, ns=(1, 1))
    assert model.artworkPreview("local-doom", "icon") != url
    assert model.artworkPreview("local-doom", "banner") == ""
    assert model.artworkPreview("local-missing", "icon") == ""


def test_artwork_origin_names_the_source(qgui_app, xdg_env, tmp_path):
    """The dialog's tooltip can say where each kind came from."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    model = _model(qgui_app)
    assert model.artworkOrigin("local-doom", "icon") == ""
    picked = tmp_path / "m.png"
    picked.write_bytes(b"P")
    manual = artwork.store_manual("local-doom", "icon", str(picked))
    assert manual is not None
    assert model.artworkOrigin("local-doom", "icon") == "manual"
    # A downloaded file carries its provider in the sidecar.
    cached = artwork.grid_path("local-doom", "cover")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"C")
    artwork._write_manifest("local-doom", "cover", "sgdb")
    assert model.artworkOrigin("local-doom", "cover") == "cache:sgdb"
    # No sidecar: plain downloaded art.
    other = artwork.grid_path("local-doom", "banner")
    other.write_bytes(b"B")
    assert model.artworkOrigin("local-doom", "banner") == "cache"


def test_artwork_from_url_stores_the_manual_slot(qgui_app, xdg_env, monkeypatch):
    """A pasted URL downloads off-thread into the game's manual slot."""
    from tkarcade import artwork
    from tkarcade import config as C

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    monkeypatch.setattr(artwork, "fetch_image", lambda url, limit=None: (payload, ""))
    model = _model(qgui_app)
    done = []
    model.artworkStored.connect(lambda appid, kind, error: done.append((appid, kind, error)))
    assert model.storeArtworkUrl("local-doom", "cover", "https://x/y.png") == ""
    # The signal crosses threads, so it needs the event loop to arrive.
    for _ in range(100):
        if done:
            break
        qgui_app.processEvents()
        time.sleep(0.02)
    assert done == [("local-doom", "cover", "")], done
    stored = C.load("local-doom").artwork.cover
    assert stored.endswith("cover.png")
    assert Path(stored).read_bytes() == payload


def test_artwork_url_is_validated_before_downloading(qgui_app, xdg_env):
    model = _model(qgui_app)
    assert model.storeArtworkUrl("", "icon", "https://x/y.png") == "no-game"
    assert model.storeArtworkUrl("local-doom", "nope", "https://x/y.png") == "no-kind"
    assert model.storeArtworkUrl("local-doom", "icon", "file:///etc/passwd") == "bad-url"


def test_row_cover_uses_the_cached_artwork(qgui_app, xdg_env):
    """A local game's card cover is its own portrait art."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    C.save(local)
    cover = artwork.grid_path("local-doom", "cover")
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"C")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.CoverRole) == str(cover)
    assert model.rowData(row)["gameCover"] == str(cover)


def test_row_icon_uses_the_artwork_source_appid(qgui_app, xdg_env):
    """An Artwork Source AppID wins over the game's own cached art."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    local.artwork.artwork_appid = "480"
    C.save(local)
    own = artwork.grid_path("local-doom", "icon")
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_bytes(b"OWN")
    shared = artwork.grid_path("480", "icon")
    shared.write_bytes(b"SHARED")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.IconRole) == str(shared)
    assert model.effectiveArtwork("local-doom", "icon") == str(shared)
    assert model.effectiveArtwork("local-doom", "icon", "480") == str(shared)


def test_row_cover_uses_the_artwork_source_appid(qgui_app, xdg_env):
    """The Artwork Source AppID's portrait art is the card cover."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    local.runtime.type = "native"
    local.artwork.artwork_appid = "480"
    C.save(local)
    shared = artwork.grid_path("480", "cover")
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_bytes(b"C")
    model = _model(qgui_app)
    row = next(
        i
        for i in range(model.rowCount())
        if model.data(model.index(i, 0), model.IdRole) == "local-doom"
    )
    assert model.data(model.index(row, 0), model.CoverRole) == str(shared)
    assert model.rowData(row)["gameCover"] == str(shared)


def test_fetch_artwork_uses_the_typed_source_appid(qgui_app, xdg_env, monkeypatch):
    """A typed Artwork Source AppID is the fetch target, even before Save."""
    from tkarcade import artwork

    calls = []

    def fake_best(
        appid, provider="steam", api_key="", kinds=artwork.ART_KINDS, force=False, names=()
    ):
        calls.append((appid, provider, force, tuple(names)))
        return {
            "art": {"cover": __import__("pathlib").Path("/tmp/x.png")},
            "provider": "steam",
            "error": "",
            "name": "",
            "valid": True,
            "game_id": "",
            "candidates": [],
        }

    monkeypatch.setattr(artwork, "fetch_best", fake_best)
    local = C.GameConfig()
    local.general.appid = "local-quake"
    local.general.name = "Quake"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    model = _model(qgui_app)
    started = []
    model.artworkFetched.connect(lambda gid, status, prov: started.append(status))
    # The draft value wins over the saved config, like the old field did.
    assert model.fetchArtwork("local-quake", "", "480") == ""
    for _ in range(50):
        if started:
            break
        qgui_app.processEvents()
        time.sleep(0.05)
    assert started == ["ok"], started
    assert calls == [("480", "steam", True, ())], calls
    # A non-numeric value is reported, not sent to the name search.
    assert model.fetchArtwork("local-quake", "", "not-a-number") == "no-appid"


def test_fetch_artwork_uses_the_game_name_and_its_provider(qgui_app, xdg_env, monkeypatch):
    """A local game fetches by name, with its own provider override."""
    from tkarcade import artwork

    calls = []

    def fake_best(
        appid, provider="steam", api_key="", kinds=artwork.ART_KINDS, force=False, names=()
    ):
        calls.append((appid, provider, api_key, force, tuple(names)))
        return {
            "art": {"cover": __import__("pathlib").Path("/tmp/x.png")},
            "provider": "sgdb",
            "error": "",
            "name": "",
            "valid": False,
            "game_id": "7",
            "candidates": [],
        }

    monkeypatch.setattr(artwork, "fetch_best", fake_best)
    local = C.GameConfig()
    local.general.appid = "local-quake"
    local.general.name = "Quake [v1.0]"
    local.general.custom_executable = "/bin/true"
    local.artwork.provider = "sgdb"
    C.save(local)
    model = _model(qgui_app)
    assert model.fetchArtwork("") == "no-game"
    started = []
    model.artworkFetched.connect(lambda gid, status, prov: started.append((gid, status, prov)))
    assert model.fetchArtwork("local-quake") == ""
    for _ in range(50):
        if started:
            break
        qgui_app.processEvents()
        time.sleep(0.05)
    assert started == [("local-quake", "ok", "sgdb")], started
    # Forced (Fetch Artwork), and the name drops the version first.
    assert calls == [("local-quake", "sgdb", "", True, ("Quake", "Quake [v1.0]"))]
    # Without a name there is nothing to look up.
    local.general.name = ""
    C.save(local)
    assert model.fetchArtwork("local-quake") == "no-appid"


def test_fetch_artwork_reports_name_choices(qgui_app, xdg_env, monkeypatch):
    """Several SteamGridDB entries: the dialog gets the list to ask."""
    from tkarcade import artwork

    def fake_best(
        appid, provider="steam", api_key="", kinds=artwork.ART_KINDS, force=False, names=()
    ):
        return {
            "art": {},
            "provider": "",
            "error": "no-match",
            "name": "",
            "valid": False,
            "game_id": "",
            "candidates": [{"id": "5", "name": "Doom 3"}],
        }

    monkeypatch.setattr(artwork, "fetch_best", fake_best)
    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    model = _model(qgui_app)
    seen = []
    model.artworkChoices.connect(lambda gid, rows: seen.append((gid, rows)))
    model.fetchArtwork("local-doom")
    for _ in range(50):
        if seen:
            break
        qgui_app.processEvents()
        time.sleep(0.05)
    assert seen and seen[0][0] == "local-doom"
    assert seen[0][1][0]["name"] == "Doom 3"


def test_fetch_artwork_game_downloads_the_chosen_id(qgui_app, xdg_env, monkeypatch):
    """Picking a SteamGridDB entry downloads it and remembers the id."""
    from pathlib import Path

    from tkarcade import artwork

    calls = []
    monkeypatch.setattr(
        artwork,
        "fetch_sgdb_game",
        lambda appid, game_id, key, **kw: (
            calls.append((appid, game_id, key)) or {"cover": Path("/tmp/c.png")}
        ),
    )
    monkeypatch.setattr(
        artwork,
        "store_sgdb_id",
        lambda appid, game_id, name="": calls.append(("id", appid, game_id)),
    )
    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    prefs = C.load_preferences()
    prefs.sgdb_api_key = "KEY"
    C.save_preferences(prefs)
    model = _model(qgui_app)
    started = []
    model.artworkFetched.connect(lambda gid, status, prov: started.append(status))
    assert model.fetchArtworkGame("", "7") == "no-game"
    assert model.fetchArtworkGame("local-doom", "7") == ""
    for _ in range(50):
        if started:
            break
        qgui_app.processEvents()
        time.sleep(0.05)
    assert started == ["ok"], started
    assert calls[0] == ("local-doom", "7", "KEY")
    assert calls[1] == ("id", "local-doom", "7")


def test_clear_fetched_artwork_uses_the_game_id(qgui_app, xdg_env):
    """Clear works on a local game: the cache sits under its own id."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    cover = artwork.grid_path("local-doom", "cover")
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"P")
    model = _model(qgui_app)
    assert model.clearFetchedArtwork("") == "no-game"
    assert model.clearFetchedArtwork("local-doom") == "done"
    assert artwork.cached_path("local-doom", "cover") is None
    assert artwork.is_cleared("local-doom") is True
    assert model.artworkStatus("local-doom") == "cleared"
    # The preview goes empty too: no Steam art, no exe icon, no sibling.
    assert model.artworkPreview("local-doom", "cover") == ""


def test_clear_artwork_empties_the_tile(qgui_app, xdg_env):
    """The tile's clear drops the downloaded copy, not only the manual slot."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    cover = artwork.grid_path("local-doom", "cover")
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"P")
    model = _model(qgui_app)
    assert model.artworkPreview("local-doom", "cover") != ""
    assert model.clearArtwork("local-doom", "cover") is True
    assert artwork.cached_path("local-doom", "cover") is None
    assert artwork.is_kind_cleared("local-doom", "cover") is True
    assert model.artworkPreview("local-doom", "cover") == ""


def test_clear_fetched_artwork_uses_the_source_appid(qgui_app, xdg_env):
    """Clear targets the typed AppID, whose cache other games may share."""
    from tkarcade import artwork

    local = C.GameConfig()
    local.general.appid = "local-doom"
    local.general.name = "Doom"
    local.general.custom_executable = "/bin/true"
    C.save(local)
    shared = artwork.grid_path("480", "cover")
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_bytes(b"P")
    model = _model(qgui_app)
    # The draft AppID wins over the saved (empty) config.
    assert model.clearFetchedArtwork("local-doom", "480") == "done"
    assert artwork.cached_path("480", "cover") is None
    assert artwork.is_cleared("480") is True
    assert model.artworkStatus("local-doom", "480") == "cleared"


def test_settings_winetricks_verbs_pending(qgui_app, xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    model = GameListModel()

    # Local game: the WINEPREFIX holds the log directly.
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "winetricks.log").write_text("corefonts\n", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    C.save(cfg)
    state = model.installedVerbs("local-doom", "corefonts vcrun2022")
    assert state["installed"] == ["corefonts"]
    assert state["pending"] == ["vcrun2022"]
    assert model.installedVerbs("local-doom", "") == {"installed": ["corefonts"], "pending": []}

    # Steam game: Steam's compatdata container, log inside its pfx.
    container = tmp_path / "compatdata" / "620"
    (container / "pfx").mkdir(parents=True)
    (container / "pfx" / "winetricks.log").write_text("dotnet48\n", encoding="utf-8")
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    C.save(cfg)
    monkeypatch.setattr(S, "prefix_dir", lambda appid: container)
    assert model.installedVerbs("620", "")["installed"] == ["dotnet48"]
    # A custom prefix wins over Steam's own compatdata dir.
    cfg.runtime.prefix = str(container)
    C.save(cfg)
    monkeypatch.setattr(S, "prefix_dir", lambda appid: tmp_path / "gone")
    assert model.installedVerbs("620", "")["installed"] == ["dotnet48"]


def test_settings_winetricks_gui_refusals(qgui_app, xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S
    from tkarcade.gui.model import GameListModel

    model = GameListModel()
    cfg = C.GameConfig()
    cfg.general.appid = "620"
    cfg.runtime.prefix = str(tmp_path / "pfx")
    C.save(cfg)
    # A custom prefix takes winetricks, which needs the game's Proton.
    from tkarcade import proton as P

    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    assert "Proton" in model.openWinetricksGui("620")
    cfg.runtime.prefix = ""
    C.save(cfg)
    # protontricks refuses games that never ran: it needs their compatdata.
    monkeypatch.setattr(S, "prefix_dir", lambda appid: None)
    assert "Launched Once" in model.openWinetricksGui("620")
    # With a compatdata prefix present the missing binary is the refusal.
    monkeypatch.setattr(S, "prefix_dir", lambda appid: tmp_path / "compatdata" / "620")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert "Protontricks Was Not Found" in model.openWinetricksGui("620")
    # A native local game has nothing to install into.
    local = C.GameConfig()
    local.general.appid = "local-native"
    local.runtime.type = "native"
    C.save(local)
    assert "Wine or Proton" in model.openWinetricksGui("local-native")


def test_settings_winetricks_gui_custom_prefix(qgui_app, xdg_env, fake_bin, tmp_path, monkeypatch):
    """A Steam game with a custom prefix runs winetricks against its pfx."""
    import time

    from tkarcade import proton as P
    from tkarcade.gui.model import GameListModel

    calls = tmp_path / "calls.log"
    fake_bin("winetricks", f'#!/bin/sh\necho "$WINEPREFIX|$WINE|$@" >> "{calls}"\n')
    proton = tmp_path / "GE-Proton9-1"
    (proton / "files" / "bin").mkdir(parents=True)
    (proton / "proton").write_text("#!/bin/sh\n")
    wine = proton / "files" / "bin" / "wine"
    wine.write_text("#!/bin/sh\n")
    wine.chmod(0o755)
    container = tmp_path / "custom-compatdata"
    (container / "pfx" / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "steam-620"
    cfg.runtime.prefix = str(container)
    cfg.runtime.tool = str(proton)  # an explicit tool wins over the mapping
    C.save(cfg)
    monkeypatch.setattr(P, "compat_tool_name", lambda appid: None)
    model = GameListModel()
    assert model.openWinetricksGui("steam-620") == ""
    deadline = time.time() + 5
    while not calls.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert calls.read_text().strip() == f"{container / 'pfx'}|{wine}|--gui"


def test_steam_runtime_state(qgui_app, xdg_env):
    """The dialog hint reads umu's own layout; a missing one is not an error."""
    from pathlib import Path

    model = _model(qgui_app)
    assert model.steamRuntimeState("") == {"installed": False, "label": "", "path": ""}
    assert model.steamRuntimeState("bogus")["label"] == ""
    state = model.steamRuntimeState("sniper")
    assert state["label"] == "Steam Linux Runtime 3.0 (sniper)"
    assert state["path"].endswith("umu/steamrt3")
    assert state["installed"] is False
    Path(state["path"]).mkdir(parents=True)
    assert model.steamRuntimeState("sniper")["installed"] is True


def test_settings_winetricks_gui_launch(qgui_app, xdg_env, fake_bin, tmp_path):
    import time

    from tkarcade.gui.model import GameListModel

    calls = tmp_path / "calls.log"
    fake_bin("winetricks", f'#!/bin/sh\necho "$WINEPREFIX|$WINE|$@" >> "{calls}"\n')
    wine = fake_bin("wine")
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    cfg.runtime.tool = str(wine)
    C.save(cfg)
    model = GameListModel()
    assert model.openWinetricksGui("local-doom") == ""
    deadline = time.time() + 5
    while not calls.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert calls.read_text().strip() == f"{prefix}|{wine}|--gui"


def test_settings_winetricks_gui_reports_failure(qgui_app, xdg_env, fake_bin, tmp_path):
    """A tool that dies leaves its output in a log and the exit is news."""
    import time

    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    fake_bin("winetricks", "#!/bin/sh\necho 'no such verb' >&2\nexit 3\n")
    wine = fake_bin("wine")
    base = tmp_path / "base"
    prefix = C.prefix_dir("local-doom", str(base), "", "", "Doom")
    (prefix / "drive_c").mkdir(parents=True)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.runtime.type = "wine"
    cfg.runtime.prefix = str(base)
    cfg.runtime.tool = str(wine)
    C.save(cfg)
    model = GameListModel()
    seen: list[tuple[str, str]] = []
    model.verbToolClosed.connect(lambda status, detail: seen.append((status, detail)))
    assert model.openWinetricksGui("local-doom") == ""
    deadline = time.time() + 5
    while not seen and time.time() < deadline:
        qgui_app.processEvents()
        time.sleep(0.02)
    log_path = xdg.games_log_dir() / "local-doom-winetricks.log"
    assert seen == [("failed", str(log_path))]
    assert "no such verb" in log_path.read_text(encoding="utf-8")


def _fake_threads(monkeypatch):
    from tkarcade.gui import model as M

    class FakeThread:
        def __init__(self, target=None, args=(), **kwargs):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr(M.threading, "Thread", FakeThread)


def test_fetch_runtime_releases_emits_rows(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    _fake_threads(monkeypatch)
    monkeypatch.setattr(
        M.archivesmod,
        "releases",
        lambda kind, opener=None, repo="": [
            {
                "tag": "v2.7.1",
                "name": "dxvk-2.7.1.tar.gz",
                "url": "https://x/a.tar.gz",
                "size": 5,
                "digest": "sha256:aa",
                "prerelease": False,
            }
        ],
    )
    model = M.GameListModel()
    rows: list = []
    errors: list[str] = []
    model.runtimeReleases.connect(
        lambda kind, items, message: (rows.append((kind, items)), errors.append(message))
    )
    model.fetchRuntimeReleases("dxvk")
    assert rows[0][0] == "dxvk" and rows[0][1][0]["tag"] == "v2.7.1"
    assert errors == [""]
    model.fetchRuntimeReleases("wine")
    assert rows[-1] == ("wine", []) and errors[-1] == "Unknown Runtime Layer."


def test_fetch_runtime_releases_reports_api_errors(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    _fake_threads(monkeypatch)

    def fail(kind, opener=None, repo=""):
        raise M.archivesmod.ArchiveError("HTTP 403")

    monkeypatch.setattr(M.archivesmod, "releases", fail)
    model = M.GameListModel()
    rows: list = []
    errors: list[str] = []
    model.runtimeReleases.connect(
        lambda kind, items, message: (rows.append(items), errors.append(message))
    )
    model.fetchRuntimeReleases("vkd3d")
    assert rows == [[]] and errors == ["HTTP 403"]


def test_install_runtime_release_passes_the_asset(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    _fake_threads(monkeypatch)
    seen: list[tuple] = []

    def install(kind, asset, progress=None, repo=""):
        seen.append((kind, dict(asset), repo))
        return ""

    monkeypatch.setattr(M.archivesmod, "download_release", install)
    model = M.GameListModel()
    finished: list[tuple[str, str]] = []
    changed: list[bool] = []
    model.archiveFinished.connect(lambda kind, text: finished.append((kind, text)))
    model.archivesChanged.connect(lambda: changed.append(True))
    asset = {
        "name": "dxvk-2.6.0.tar.gz",
        "url": "https://x/d.tar.gz",
        "size": 5,
        "digest": "",
        "tag": "v2.6.0",
    }
    model.installRuntimeRelease("dxvk", asset)
    assert seen[0][0] == "dxvk" and seen[0][1]["tag"] == "v2.6.0"
    assert finished == [("dxvk", "")] and changed == [True]
    model.installRuntimeRelease("dxvk", {"url": ""})
    assert finished[-1] == ("dxvk", "Choose a Release First.")


def test_install_runtime_from_url_rejects_an_empty_url(qgui_app, xdg_env, monkeypatch):
    from tkarcade.gui import model as M

    _fake_threads(monkeypatch)
    seen: list[tuple] = []
    monkeypatch.setattr(
        M.archivesmod,
        "install_from_url",
        lambda kind, url, progress=None: (seen.append((kind, url)), "")[1],
    )
    model = M.GameListModel()
    finished: list[tuple[str, str]] = []
    model.archiveFinished.connect(lambda kind, text: finished.append((kind, text)))
    model.installRuntimeFromUrl("vkd3d", "  ")
    assert finished == [("vkd3d", "Enter an Archive URL First.")]
    assert seen == []
    model.installRuntimeFromUrl("vkd3d", "https://x/sarek.tar.gz")
    assert seen == [("vkd3d", "https://x/sarek.tar.gz")]


def test_runtime_versions_lists_managed_versions_with_sources(qgui_app, xdg_env):
    from tkarcade import xdg
    from tkarcade.gui import model as M

    managed = xdg.runtimes_dir() / "dxvk" / "dxvk-sarek-2.4.1"
    (managed / "x64").mkdir(parents=True)
    (managed / "x64" / "d3d11.dll").write_bytes(b"dll")
    M.archivesmod._record_source("dxvk", managed, "url", "", "", "https://x/sarek.tar.gz")
    model = M.GameListModel()
    rows = model.runtimeVersions("dxvk")
    assert rows[0]["name"] == "dxvk-sarek-2.4.1"
    assert rows[0]["origin"] == "url"
    assert model.runtimeVersions("wine") == []


def test_remove_runtime_version_reports_and_refreshes(qgui_app, xdg_env, monkeypatch):
    from tkarcade import xdg
    from tkarcade.gui import model as M

    managed = xdg.runtimes_dir() / "vkd3d" / "vkd3d-proton-3.1"
    (managed / "x64").mkdir(parents=True)
    (managed / "x64" / "d3d12.dll").write_bytes(b"dll")
    model = M.GameListModel()
    changed: list[bool] = []
    model.archivesChanged.connect(lambda: changed.append(True))
    assert model.removeRuntimeVersion("vkd3d", "vkd3d-proton-3.1") == ""
    assert changed == [True]
    assert not managed.exists()
    assert "not a managed version" in model.removeRuntimeVersion("vkd3d", "gone")


def test_wine_manager_slots(qgui_app, xdg_env, fake_bin):
    from tkarcade import config as C
    from tkarcade.gui import model as M

    wine_a = fake_bin("wine-a")
    wine_b = fake_bin("wine-b")
    model = M.GameListModel()
    assert [(r["name"], r["default"]) for r in model.wineVersionRows()] == [("", True)]

    assert model.addWineVersion(str(wine_a)) == ""
    assert "Already" in model.addWineVersion(str(wine_a))
    assert model.addWineVersion("/does/not/exist") != ""
    assert [r["name"] for r in model.wineVersionRows()] == ["", "wine-a"]

    assert model.setWineDefault("wine-a") == ""
    assert [r["default"] for r in model.wineVersionRows()] == [False, True]
    assert model.setWineDefault("gone") != ""

    cfg = C.load("local-wine")
    cfg.general.appid = "local-wine"
    cfg.general.name = "Local Wine"
    cfg.runtime.type = "wine"
    cfg.runtime.tool = "wine-a"
    C.save(cfg)
    assert model.renameWineVersion("wine-a", "dev") == ""
    assert C.load("local-wine").runtime.tool == "dev"
    assert C.load_preferences().wine_default == "dev"

    assert model.addWineVersion(str(wine_b)) == ""
    assert C.load_preferences().wine_default == "dev"
    assert model.removeWineVersion("dev") == ""
    assert C.load_preferences().wine_default == ""
    assert [r["name"] for r in model.wineVersionRows()] == ["", "wine-b"]


def test_proton_manager_slots(qgui_app, xdg_env, fake_bin, monkeypatch):
    from tkarcade import config as C
    from tkarcade import runtimes as R
    from tkarcade.gui import model as M

    system = xdg_env["home"] / "system-steam"
    for name in ("proton-cachyos-slr", "GE-Proton9-1"):
        (system / "compatibilitytools.d" / name).mkdir(parents=True)
        (system / "compatibilitytools.d" / name / "proton").write_text("x\n")
    monkeypatch.setattr(R, "SYSTEM_STEAM_ROOT", system)
    model = M.GameListModel()
    rows = model.protonVersionRows()
    # The system tree comes first; inside it the scanner sorts by name.
    assert [r["name"] for r in rows] == ["GE-Proton9-1", "proton-cachyos-slr"]
    assert [r["default"] for r in rows] == [True, False]

    assert model.setProtonDefault("proton-cachyos-slr") == ""
    assert C.load_preferences().proton_default == "proton-cachyos-slr"
    assert [r["default"] for r in model.protonVersionRows()] == [False, True]
    assert model.setProtonDefault("gone") != ""
    assert model.setProtonDefault("") == ""
    assert [r["default"] for r in model.protonVersionRows()] == [True, False]

    launched: list[list[str]] = []
    monkeypatch.setattr(M.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    fake_bin("protonplus")
    fake_bin("protonup-qt")
    assert model.openProtonManager() == ""
    assert launched and launched[0][0].endswith("protonplus")
    monkeypatch.setattr(M.shutil, "which", lambda name: None)
    assert "Not Found" in model.openProtonManager()


def test_graphics_manager_slots(qgui_app, xdg_env, tmp_path):
    from tkarcade import config as C
    from tkarcade import xdg
    from tkarcade.gui import model as M

    managed = xdg.runtimes_dir() / "dxvk" / "dxvk-2.7.1"
    (managed / "x64").mkdir(parents=True)
    (managed / "x64" / "d3d11.dll").write_bytes(b"dll")
    root = tmp_path / "dxvk-old"
    external = root / "dxvk-2.6.2"
    (external / "x64").mkdir(parents=True)
    (external / "x64" / "d3d11.dll").write_bytes(b"dll")
    model = M.GameListModel()
    assert model.addGraphicsFolder("dxvk", str(root)) == ""
    assert model.addGraphicsFolder("dxvk", str(root)) != ""
    rows = model.runtimeVersions("dxvk")
    assert [r["name"] for r in rows] == ["dxvk-2.7.1", "dxvk-2.6.2"]
    assert [r["external"] for r in rows] == [False, True]

    assert model.setGraphicsDefault("dxvk", "dxvk-2.6.2") == ""
    assert C.load_preferences().dxvk_default == "dxvk-2.6.2"
    assert [r["default"] for r in model.runtimeVersions("dxvk")] == [False, True]
    assert model.setGraphicsDefault("dxvk", "gone") != ""
    assert model.setGraphicsDefault("dxvk", "") == ""

    assert model.graphicsSource("dxvk") == "official"
    assert model.setGraphicsSource("dxvk", "sarek") == ""
    assert model.graphicsSource("dxvk") == "sarek"
    assert model.setGraphicsSource("dxvk", "custom", "not a repo") != ""
    assert model.setGraphicsSource("dxvk", "custom", "Someone/DXVK") == ""
    assert model.graphicsSource("dxvk") == "custom:Someone/DXVK"
    assert model.setGraphicsSource("nope", "official") != ""

    assert model.graphicsFolders("dxvk") == [str(root)]
    assert model.removeGraphicsFolder("dxvk", str(root)) == ""
    assert model.graphicsFolders("dxvk") == []
    assert [r["name"] for r in model.runtimeVersions("dxvk")] == ["dxvk-2.7.1"]


def test_graphics_rows_flag_system_builds(qgui_app, xdg_env, monkeypatch):
    from tkarcade import runtimes as R
    from tkarcade.gui import model as M

    system = xdg_env["home"] / "usr-dxvk"
    (system / "x64").mkdir(parents=True)
    (system / "x64" / "d3d11.dll").write_bytes(b"dll")
    monkeypatch.setattr(R, "SYSTEM_GRAPHICS_DIRS", {"dxvk": (system,)})
    rows = M.GameListModel().runtimeVersions("dxvk")
    assert [(r["name"], r["origin"], r["system"], r["external"]) for r in rows] == [
        ("usr-dxvk", "system", True, True)
    ]


def test_orphaned_leftovers_finds_cached_artwork(qgui_app, xdg_env):
    from tkarcade import artwork as A
    from tkarcade import xdg
    from tkarcade.gui.model import GameListModel

    grid = A.grid_path("steam-620", "cover")
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"png")
    A.manifest_path("steam-620").write_text("{}")
    proton = xdg.app_cache_dir() / "protondb"
    proton.mkdir(parents=True)
    (proton / "steam-620.json").write_text("{}")

    model = GameListModel()
    rows = model.orphanedLeftovers()
    assert len(rows) == 1
    assert rows[0]["appid"] == "steam-620"
    assert rows[0]["artwork"] == 3
    assert model.cleanLeftovers(["steam-620"], False) == 1
    assert A.cache_files("steam-620") == []
    assert not (proton / "steam-620.json").exists()
    assert model.orphanedLeftovers() == []
