"""Library readers: Lutris DB/YAML, Faugus JSON, mapping and matching."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import yaml

from tkarcade import config as C
from tkarcade import library_import as li


def _lutris_env(xdg_env) -> tuple[Path, Path]:
    data = Path(xdg_env["data"]) / "lutris"
    config = Path(xdg_env["config"]) / "lutris"
    (data / "runners").mkdir(parents=True, exist_ok=True)
    (config / "games").mkdir(parents=True, exist_ok=True)
    return data, config


def _write_db(path: Path, rows: list[dict], categories: dict[int, list[str]] | None = None) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table games (
            id integer primary key, name text, slug text, runner text,
            executable text, directory text, installed integer,
            configpath text, service text, service_id text,
            steamid text, gogid text, humblestoreid text
        );
        create table categories (id integer primary key, name text unique);
        create table games_categories (game_id integer, category_id integer);
        """
    )
    for row in rows:
        con.execute(
            "insert into games (id, name, slug, runner, executable, directory, installed, "
            "configpath, service, service_id, steamid, gogid, humblestoreid) "
            "values (:id, :name, :slug, :runner, :executable, :directory, :installed, "
            ":configpath, :service, :service_id, :steamid, :gogid, :humblestoreid)",
            {
                "executable": "",
                "directory": "",
                "service": "",
                "service_id": "",
                "steamid": "",
                "gogid": "",
                "humblestoreid": "",
                **row,
            },
        )
    for game_id, names in (categories or {}).items():
        for name in names:
            con.execute("insert or ignore into categories (name) values (?)", (name,))
            category_id = con.execute(
                "select id from categories where name = ?", (name,)
            ).fetchone()[0]
            con.execute(
                "insert into games_categories (game_id, category_id) values (?, ?)",
                (game_id, category_id),
            )
    con.commit()
    con.close()


def _write_yml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, default_flow_style=False), encoding="utf-8")


def test_lutris_wine_game_maps(xdg_env, monkeypatch):
    data, config = _lutris_env(xdg_env)
    install = Path(xdg_env["home"]) / "Games" / "doom"
    install.mkdir(parents=True)
    _write_db(
        data / "pga.db",
        [
            {
                "id": 1,
                "name": "Doom",
                "slug": "doom",
                "runner": "wine",
                "installed": 1,
                "configpath": "doom-1",
                "directory": str(install),
            }
        ],
        {1: ["FPS", "Retro"]},
    )
    _write_yml(
        config / "games" / "doom-1.yml",
        {
            "game": {
                "exe": "$GAMEDIR/doom.exe",
                "args": "-w 1280",
                "working_dir": "$GAMEDIR",
                "prefix": "$GAMEDIR/prefix",
            },
            "system": {
                "env": {"DXVK_HUD": "1", "BINDIR": "$GAMEDIR/bin"},
                "mangohud": True,
                "gamemode": True,
                "prelaunch_command": "$GAMEDIR/pre.sh",
                "postexit_command": "echo done",
            },
            "wine": {"version": "system"},
        },
    )
    monkeypatch.setattr(li.runtimes, "wine_path", lambda: "/usr/bin/wine")

    games, hint = li.list_games("lutris")
    assert hint == ""
    assert len(games) == 1
    game = games[0]
    assert game.source_id == "doom"
    assert game.exe == str(install / "doom.exe")
    assert game.args == "-w 1280"
    assert game.working_dir == str(install)
    assert game.prefix == str(install / "prefix")
    assert game.runtime == "wine"
    assert game.runtime_tool == "/usr/bin/wine"
    assert game.categories == ["FPS", "Retro"]
    assert game.env == {"DXVK_HUD": "1", "BINDIR": str(install / "bin")}
    assert game.mangohud is True and game.gamemode is True
    assert game.pre_command == str(install / "pre.sh")
    assert game.post_command == "echo done"

    cfg, notes = li.to_gameconfig(game, "local-doom")
    assert notes == []
    assert cfg.general.custom_executable == str(install / "doom.exe")
    assert cfg.runtime.type == "wine"
    assert cfg.runtime.prefix == str(install / "prefix")
    assert cfg.runtime.prefix_exact is True
    assert cfg.pre_post.run_in_shell is True
    assert cfg.general.categories == ["FPS", "Retro"]
    assert cfg.notes.text == "Imported from Lutris."


def test_lutris_store_steam_native_and_unsupported(xdg_env, monkeypatch):
    data, _config = _lutris_env(xdg_env)
    _write_db(
        data / "pga.db",
        [
            {
                "id": 1,
                "name": "GOG Game",
                "slug": "gog-game",
                "runner": "wine",
                "installed": 1,
                "configpath": "missing-1",
                "service": "gog",
                "service_id": "",
                "gogid": "1207",
            },
            {
                "id": 2,
                "name": "Steam Game",
                "slug": "steam-game",
                "runner": "steam",
                "installed": 1,
                "configpath": "missing-2",
                "service": "steam",
                "service_id": "570",
            },
            {
                "id": 3,
                "name": "Native Game",
                "slug": "native-game",
                "runner": "linux",
                "installed": 1,
                "configpath": "missing-3",
            },
            {
                "id": 4,
                "name": "Emulated",
                "slug": "emulated",
                "runner": "dolphin",
                "installed": 1,
                "configpath": "missing-4",
            },
        ],
    )
    monkeypatch.setattr(li.runtimes, "wine_path", lambda: "/usr/bin/wine")

    games, _ = li.list_games("lutris")
    by_name = {game.name: game for game in games}
    assert by_name["GOG Game"].store_kind == "gog"
    assert by_name["GOG Game"].store_id == "1207"
    assert by_name["GOG Game"].runtime == "wine"
    assert "game config not found" in " ".join(by_name["GOG Game"].notes)
    assert by_name["Steam Game"].runtime == "steam"
    assert by_name["Steam Game"].steam_appid == "570"
    assert by_name["Native Game"].runtime == "native"
    assert by_name["Emulated"].problem
    assert by_name["Emulated"].runtime == "unsupported"


def test_lutris_custom_pga_path(xdg_env):
    data, config = _lutris_env(xdg_env)
    custom = Path(xdg_env["home"]) / "Custom" / "pga.db"
    custom.parent.mkdir(parents=True)
    _write_db(custom, [])
    (data / "pga.db").unlink(missing_ok=True)
    (config / "lutris.conf").write_text(
        "[lutris]\npga_path = " + str(custom) + "\n", encoding="utf-8"
    )
    assert li.lutris_library_path() == custom


def _write_faugus(xdg_env, games: list[dict], config: dict | None = None) -> None:
    data = Path(xdg_env["data"]) / "faugus-launcher"
    config_dir = Path(xdg_env["config"]) / "faugus-launcher"
    data.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (data / "games.json").write_text(json.dumps(games), encoding="utf-8")
    (config_dir / "config.json").write_text(json.dumps(config or {}), encoding="utf-8")


def test_faugus_game_maps(xdg_env, tmp_path, monkeypatch):
    proton = tmp_path / "GE-Proton9-15"
    proton.mkdir()
    (proton / "proton").write_text("#!/bin/sh\n")
    monkeypatch.setattr(
        li.runtimes,
        "proton_installs",
        lambda: [li.runtimes.ProtonInstall(proton.name, proton.resolve())],
    )
    prefix = tmp_path / "prefix"
    exe = tmp_path / "game.exe"
    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "elden-ring",
                "title": "Elden Ring",
                "path": str(exe),
                "prefix": str(prefix),
                "runner": str(proton),
                "launch_arguments": "DXVK_HUD=1\nWINE_FULLSCREEN_FSR=1\n--wrapper-thing",
                "game_arguments": "-fullscreen",
                "mangohud": "MANGOHUD=1",
                "gamemode": "gamemoderun",
                "no_sleep": True,
                "category": ["Souls", "RPG"],
                "pre_launch": "echo pre",
                "post_launch": "echo post",
                "sdl_enabled": True,
            }
        ],
    )
    games, hint = li.list_games("faugus")
    assert hint == ""
    game = games[0]
    assert game.runtime == "umu"
    assert game.runtime_tool == str(proton.resolve())
    assert game.prefix == str(prefix)
    assert game.args == "-fullscreen"
    assert game.env["DXVK_HUD"] == "1"
    assert game.env["PROTON_PREFER_SDL"] == "1"
    assert game.categories == ["Souls", "RPG"]
    assert game.mangohud is True and game.gamemode is True
    assert game.inhibit_idle is True
    assert any("has no environment equivalent" in note for note in game.notes)
    cfg, _notes = li.to_gameconfig(game, "local-elden-ring")
    assert cfg.runtime.type == "umu"
    assert cfg.runtime.prefix_exact is True
    assert cfg.session.inhibit_idle is True


def test_norm_exe_never_resolves(monkeypatch):
    def boom(self):
        raise AssertionError("Path.resolve must not be called")

    monkeypatch.setattr(Path, "resolve", boom)
    assert li._norm_exe("/mnt/Windows/F/../F/game.exe") == "/mnt/Windows/F/game.exe"


def test_offline_autofs_marks_candidate_unavailable(xdg_env, monkeypatch):
    mounts = (("/", "ext4"), ("/mnt/Windows/F", "autofs"))
    monkeypatch.setattr(li, "_mount_table", lambda: mounts)
    assert li._offline_mount("/mnt/Windows/F/game.exe") == "/mnt/Windows/F"
    assert li._offline_mount("/mnt/Windows/F2/game.exe") == ""
    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "offline",
                "title": "Offline Game",
                "path": "/mnt/Windows/F/game.exe",
                "runner": "Linux-Native",
            }
        ],
    )
    games, _ = li.list_games("faugus")
    assert games[0].problem == "External drive not connected: /mnt/Windows/F"
    found, _ = li.candidates("faugus")
    assert found[0].state == "unavailable"
    assert found[0].detail == "External drive not connected: /mnt/Windows/F"


def test_faugus_runner_never_stats(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("Path.is_dir must not be called")

    monkeypatch.setattr(Path, "is_dir", boom)
    runtime, tool, steam_runtime, problem = li._faugus_runner(
        "/mnt/Windows/F/GE-Proton9-15", {}, []
    )
    assert runtime == "unsupported"
    assert tool == "" and steam_runtime == ""
    assert "not found in the discovered installs" in problem


def test_faugus_steam_native_default_and_unknown(xdg_env, tmp_path):
    runtime = tmp_path / "steamrt"
    runtime.mkdir()
    _write_faugus(
        xdg_env,
        [
            {"gameid": "steam", "title": "Steam Entry", "path": "570", "runner": "Steam"},
            {
                "gameid": "native",
                "title": "Native",
                "path": "/usr/bin/game",
                "runner": "Linux-Native",
                "runtime": "umu-sniper",
            },
            {"gameid": "default", "title": "Default", "path": "/x.exe", "runner": "Default"},
            {"gameid": "unknown", "title": "Unknown", "path": "/y.exe", "runner": "latest"},
        ],
        {"default-runner": str(tmp_path / "missing-proton")},
    )
    games, _ = li.list_games("faugus")
    by_name = {game.name: game for game in games}
    assert by_name["Steam Entry"].runtime == "steam"
    assert by_name["Steam Entry"].steam_appid == "570"
    assert by_name["Native"].runtime == "native"
    assert by_name["Native"].steam_runtime == "sniper"
    assert by_name["Default"].problem
    assert by_name["Unknown"].problem


def test_candidates_and_import_create_and_profile(xdg_env, tmp_path):
    existing_exe = tmp_path / "existing.exe"
    new_exe = tmp_path / "new.exe"
    existing = C.GameConfig()
    existing.general.appid = "local-existing"
    existing.general.name = "Existing"
    existing.general.custom_executable = str(existing_exe)
    C.save(existing)

    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "existing",
                "title": "Existing From Faugus",
                "path": str(existing_exe),
                "runner": "Linux-Native",
            },
            {
                "gameid": "new",
                "title": "New Game",
                "path": str(new_exe),
                "runner": "Linux-Native",
            },
        ],
    )
    found, hint = li.candidates("faugus")
    assert hint == ""
    states = {candidate.game.source_id: candidate.state for candidate in found}
    assert states == {"existing": "existing", "new": "new"}
    existing_candidate = next(c for c in found if c.game.source_id == "existing")
    assert existing_candidate.target == "local-existing"

    result = li.import_games("faugus", ["existing", "new"])
    assert result.profiled == ["local-existing"]
    assert result.created == ["local-new-game"]
    assert C.profile_file("local-existing", "faugus").is_file()
    created = C.load("local-new-game")
    assert created.general.name == "New Game"
    assert created.runtime.type == "native"


def test_store_match_wins_over_executable(xdg_env, tmp_path):
    saved = C.GameConfig()
    saved.general.appid = "local-store"
    saved.general.name = "Store Game"
    saved.general.custom_executable = str(tmp_path / "other.exe")
    saved.store.kind = "gog"
    saved.store.id = "1207"
    C.save(saved)
    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "gog",
                "title": "Store Game",
                "path": str(tmp_path / "new.exe"),
                "runner": "Linux-Native",
            }
        ],
    )
    # Faugus has no store field; use Lutris for the match instead.
    data, _config = _lutris_env(xdg_env)
    _write_db(
        data / "pga.db",
        [
            {
                "id": 1,
                "name": "Store Game",
                "slug": "store-game",
                "runner": "linux",
                "installed": 1,
                "configpath": "",
                "service": "gog",
                "service_id": "1207",
            }
        ],
    )
    found, _ = li.candidates("lutris")
    assert found[0].state == "existing"
    assert found[0].target == "local-store"


def test_import_skips_unavailable(xdg_env):
    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "bad",
                "title": "Bad Runner",
                "path": "/x",
                "runner": "unknown",
            }
        ],
    )
    result = li.import_games("faugus", ["bad"])
    assert result.created == [] and result.profiled == []
    assert result.skipped and "no TKArcade equivalent" in result.skipped[0][1]


def test_lutris_version_gamescope_and_mangohud_env(xdg_env, monkeypatch):
    """The name's [version] splits; gamescope and MangoHud env map natively."""
    data, config = _lutris_env(xdg_env)
    mangohud_dir = Path(xdg_env["config"]) / "MangoHud"
    mangohud_dir.mkdir(parents=True)
    conf = mangohud_dir / "No_Display.conf"
    conf.write_text("fps\n", encoding="utf-8")
    _write_db(
        data / "pga.db",
        [
            {
                "id": 1,
                "name": "Game [v1.2]",
                "slug": "game",
                "runner": "wine",
                "installed": 1,
                "configpath": "game-1",
            },
            {
                "id": 2,
                "name": "Other",
                "slug": "other",
                "runner": "wine",
                "installed": 1,
                "configpath": "other-2",
            },
        ],
    )
    _write_yml(
        config / "games" / "game-1.yml",
        {
            "system": {
                "mangohud": False,
                "gamemode": False,
                "gamescope": True,
                "gamescope_window_mode": "-b",
                "gamescope_game_res": "1280x720",
                "gamescope_output_res": "1920x1080",
                "gamescope_fps_limiter": "60",
                "gamescope_flags": "-S fit",
                "gamescope_force_grab_cursor": True,
                "gamescope_hdr": True,
                "env": {
                    "MANGOHUD": "1",
                    "MANGOHUD_DLSYM": "1",
                    "MANGOHUD_CONFIGFILE": str(conf),
                    "ENABLE_VKBASALT": "0",
                    "VKBASALT_CONFIG_FILE": "/x/vk.conf",
                },
            }
        },
    )
    _write_yml(
        config / "games" / "other-2.yml",
        {
            "system": {
                "env": {"MANGOHUD_CONFIGFILE": "/elsewhere/Display.conf"},
            }
        },
    )
    monkeypatch.setattr(li.runtimes, "wine_path", lambda: "/usr/bin/wine")
    games, _hint = li.list_games("lutris")
    game = next(g for g in games if g.source_id == "game")
    assert game.name == "Game"
    assert game.version == "v1.2"
    assert game.mangohud is True
    assert game.mangohud_args == "--dlsym"
    assert game.mangohud_config == "No_Display.conf"
    assert game.env == {"ENABLE_VKBASALT": "0", "VKBASALT_CONFIG_FILE": "/x/vk.conf"}
    assert game.gamescope is True
    assert game.gamescope_args == (
        "-b -w 1280 -h 720 -W 1920 -H 1080 -r 60 -S fit --force-grab-cursor --hdr-enabled"
    )
    cfg, _notes = li.to_gameconfig(game, "local-game")
    assert cfg.metadata.version == "v1.2"
    assert cfg.mangohud.enable is True
    assert cfg.mangohud.args == "--dlsym"
    assert cfg.mangohud.config_file == "No_Display.conf"
    assert cfg.gamescope.enable is True
    assert cfg.gamescope.args.startswith("-b -w 1280 -h 720")
    # A config file outside the MangoHud directory has no native equivalent.
    other = next(g for g in games if g.source_id == "other")
    assert other.mangohud_config == ""
    assert other.env == {"MANGOHUD_CONFIGFILE": "/elsewhere/Display.conf"}


def test_import_starts_from_global_defaults(xdg_env, monkeypatch):
    """Imported games inherit Global Defaults; the source only adds to them."""
    defaults = C.GameConfig()
    defaults.mangohud.enable = True
    defaults.gamescope.enable = True
    defaults.gamescope.args = "-f"
    defaults.gamemode.feral_gamemode = True
    defaults.session.inhibit_idle = True
    defaults.env.vars = {"DEFAULT_VAR": "1"}
    defaults.pre_post.pre_command = "echo default"
    C.save_defaults(defaults)
    game = li.LibraryGame(
        source="lutris",
        source_id="plain",
        name="Plain",
        exe="/games/plain.exe",
        runtime="wine",
        env={"IMPORTED_VAR": "2"},
        mangohud=False,
        gamemode=False,
        gamescope=False,
        inhibit_idle=False,
    )
    cfg, _notes = li.to_gameconfig(game, "local-plain")
    assert cfg.mangohud.enable is True
    assert cfg.gamescope.enable is True
    assert cfg.gamescope.args == "-f"
    assert cfg.gamemode.feral_gamemode is True
    assert cfg.session.inhibit_idle is True
    assert cfg.env.vars == {"DEFAULT_VAR": "1", "IMPORTED_VAR": "2"}
    assert cfg.pre_post.pre_command == "echo default"
    assert cfg.pre_post.run_in_shell is False


def test_profile_base_keeps_the_live_config(xdg_env):
    """A profile for an existing game starts from its live config."""
    base = C.GameConfig()
    base.general.appid = "local-live"
    base.metadata.description = "Typed synopsis"
    base.mangohud.config_file = "Display.conf"
    game = li.LibraryGame(
        source="lutris",
        source_id="live",
        name="Live",
        exe="/games/live.exe",
        runtime="wine",
        mangohud_config="No_Display.conf",
    )
    cfg, _notes = li.to_gameconfig(game, "local-live", base=base, set_name=False)
    assert cfg.metadata.description == "Typed synopsis"
    assert cfg.general.name == ""  # the live game keeps its own name
    assert cfg.mangohud.config_file == "No_Display.conf"


def test_faugus_title_version_splits(xdg_env):
    _write_faugus(
        xdg_env,
        [
            {
                "gameid": "vn",
                "title": "Some Game [v0.9]",
                "path": "/bin/true",
                "runner": "linux",
            }
        ],
    )
    games, _hint = li.list_games("faugus")
    assert games[0].name == "Some Game"
    assert games[0].version == "v0.9"
