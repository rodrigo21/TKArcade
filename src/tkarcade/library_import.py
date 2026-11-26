"""Read Lutris and Faugus libraries (GUI-only, read-only on their files).

The readers map the subset both programs share onto a LibraryGame; the
mapping into a GameConfig happens separately, so the GUI can show a
candidate list first. Nothing here writes to the other launcher's files.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import shlex
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import config as cfgmod
from . import runtimes, xdg
from . import steam as steammod

SOURCES = ("lutris", "faugus")
SOURCE_LABELS = {"lutris": "Lutris", "faugus": "Faugus"}

#: Lutris service names -> the store kinds the config records.
_STORE_ALIASES = {
    "gog": "gog",
    "epic": "epic",
    "epicgames": "epic",
    "amazon": "amazon",
    "humble": "humble",
    "humblebundle": "humble",
    "itch": "itch",
    "itch.io": "itch",
    "ubisoft": "ubisoft",
    "uplay": "ubisoft",
    "ea": "ea",
    "origin": "ea",
    "battlenet": "battlenet",
}

#: Faugus labels that are not an installed Proton directory.
_FAUGUS_RESERVED = (
    "Proton-GE Latest",
    "DW-Proton Latest",
    "Proton-CachyOS Latest",
    "Proton-Wineland Latest",
)
_ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RUNTIME_KINDS = ("wine", "umu", "native")


@dataclass
class LibraryGame:
    """One foreign library entry, before any TKArcade config exists."""

    source: str
    source_id: str
    name: str
    #: Trailing ``[version]`` split off the source name at read time, so
    #: matching, the new ID and the config all see the plain name.
    version: str = ""
    exe: str = ""
    args: str = ""
    working_dir: str = ""
    prefix: str = ""
    runtime: str = ""  # wine|umu|native|steam|unsupported
    runtime_tool: str = ""
    steam_runtime: str = ""
    steam_appid: str = ""
    store_kind: str = ""
    store_id: str = ""
    categories: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    pre_command: str = ""
    post_command: str = ""
    mangohud: bool = False
    mangohud_args: str = ""  # wrapper flags, e.g. --dlsym
    mangohud_config: str = ""  # filename inside the MangoHud config dir
    gamemode: bool = False
    gamescope: bool = False
    gamescope_args: str = ""
    inhibit_idle: bool = False
    notes: list[str] = field(default_factory=list)
    problem: str = ""  # non-empty: no TKArcade launch path


@dataclass
class Candidate:
    """A LibraryGame plus how it maps onto the current library."""

    game: LibraryGame
    target: str = ""  # existing game ID, "" for a new game
    state: str = "new"  # new|existing|unavailable
    detail: str = ""


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() not in ("", "0", "false", "none", "no", "off")


def _expand(value: object, base: str = "") -> str:
    """Expand $GAMEDIR/$HOME/$USER and ~; relative paths join the base."""
    text = str(value or "").strip()
    if not text:
        return ""
    if base:
        text = text.replace("$GAMEDIR", base)
    return os.path.expanduser(os.path.expandvars(text))


def _path(value: object, base: str = "", join_bare: bool = True) -> str:
    text = _expand(value, base)
    if not text or os.path.isabs(text):
        return text
    if join_bare or "/" in text:
        return os.path.normpath(os.path.join(base, text)) if base else text
    return text


def _digits(value: object) -> str:
    text = str(value or "").strip()
    return text if text.isdigit() else ""


def _norm_exe(value: object) -> str:
    """Lexical executable key; never stats a path.

    A stat on an automounted external drive can block the process in
    uninterruptible sleep, so matching compares the path text only.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    text = os.path.expanduser(text)
    return os.path.normcase(os.path.normpath(text))


def _norm_name(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip().casefold()


def _mount_unescape(text: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), text)


def _mount_table() -> tuple[tuple[str, str], ...]:
    """(mountpoint, fstype) from /proc/self/mountinfo; kernel memory only."""
    try:
        text = Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    mounts: list[tuple[str, str]] = []
    for line in text.splitlines():
        left, sep, right = line.partition(" - ")
        fields = left.split()
        if not sep or len(fields) < 5:
            continue
        fstype = right.split()[0] if right.split() else ""
        mounts.append((_mount_unescape(fields[4]), fstype))
    return tuple(mounts)


def _offline_mount(value: object, mounts: tuple[tuple[str, str], ...] | None = None) -> str:
    """Autofs mountpoint holding this path, or "" when not an autofs path.

    An autofs entry still present in mountinfo means the filesystem is not
    mounted: the external drive is disconnected. No stat is attempted.
    """
    text = _expand(value)
    if not text or not os.path.isabs(text):
        return ""
    target = os.path.normpath(text)
    best = ""
    best_type = ""
    for mount, fstype in mounts if mounts is not None else _mount_table():
        prefix = "/" if mount == "/" else mount.rstrip("/") + "/"
        if (target == mount or target.startswith(prefix)) and len(mount) > len(best):
            best = mount
            best_type = fstype
    return best if best and best_type == "autofs" else ""


def _offline_problem(game: LibraryGame, mounts: tuple[tuple[str, str], ...] | None = None) -> str:
    for path in (game.exe, game.prefix, game.working_dir):
        mount = _offline_mount(path, mounts)
        if mount:
            return f"External drive not connected: {mount}"
    return ""


# --- Lutris -------------------------------------------------------------


def _lutris_bases() -> list[Path]:
    home = Path.home()
    bases = [
        xdg.config_home() / "lutris",
        xdg.data_home() / "lutris",
        home / ".var/app/net.lutris.Lutris/config/lutris",
        home / ".var/app/net.lutris.Lutris/data/lutris",
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for base in bases:
        key = os.fspath(base)
        if key not in seen:
            seen.add(key)
            out.append(base)
    return out


def _lutris_conf() -> dict[str, str]:
    out: dict[str, str] = {}
    for base in _lutris_bases():
        path = base / "lutris.conf"
        if not path.is_file():
            continue
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        if parser.has_section("lutris"):
            out.update(dict(parser["lutris"]))
    return out


def lutris_library_path() -> Path | None:
    """Lutris `pga.db`, honoring a custom `pga_path`."""
    custom = _expand(_lutris_conf().get("pga_path", ""))
    if custom:
        path = Path(custom)
        if path.is_file():
            return path
    for base in _lutris_bases():
        path = base / "pga.db"
        if path.is_file():
            return path
    return None


def _lutris_game_config_path(configpath: object) -> Path | None:
    raw = str(configpath or "").strip()
    if not raw:
        return None
    name = raw if raw.endswith(".yml") else f"{raw}.yml"
    for base in _lutris_bases():
        path = base / "games" / name
        if path.is_file():
            return path
    return None


def _read_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as e:  # declared dependency; a source tree may lack it
        raise RuntimeError("PyYAML is not installed, so Lutris game configs cannot be read") from e
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_lutris_rows(db: Path) -> tuple[list[dict], dict[int, list[str]]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in con.execute("select * from games where installed = 1")]
        categories: dict[int, list[str]] = {}
        try:
            query = (
                "select gc.game_id as game_id, c.name as name "
                "from games_categories gc join categories c on c.id = gc.category_id"
            )
            for row in con.execute(query):
                categories.setdefault(int(row["game_id"]), []).append(str(row["name"]))
        except (sqlite3.Error, TypeError):
            categories = {}
        return rows, categories
    finally:
        con.close()


def _lutris_wine(version: str, conf: dict[str, str], data_dir: Path) -> tuple[str, str]:
    """(wine executable, note) for a Lutris `wine.version`."""
    if not version or version == "system":
        found = runtimes.wine_path()
        return found, "" if found else "no system Wine found on PATH"
    roots: list[Path] = []
    custom = _expand(conf.get("runner_dir", ""))
    if custom:
        roots.append(Path(custom))
    roots.append(data_dir / "runners")
    for root in roots:
        base = root / "wine" / version
        for rel in ("bin/wine", "files/bin/wine"):
            candidate = base / rel
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return os.fspath(candidate), ""
    found = runtimes.wine_path()
    note = f"Lutris Wine build {version!r} not found; using the Wine on PATH"
    return found, note


def _lutris_store(row: dict, service: str) -> tuple[str, str, str]:
    """(store kind, store id, Steam AppID) from the DB row."""
    service_id = str(row.get("service_id") or "").strip()
    steam_id = _digits(row.get("steamid"))
    gog_id = str(row.get("gogid") or "").strip()
    if service == "steam":
        return "", "", _digits(service_id) or steam_id
    if service in _STORE_ALIASES:
        store_id = service_id
        if not store_id and service == "gog":
            store_id = gog_id
        if not store_id and service in ("humble", "humblebundle"):
            store_id = str(row.get("humblestoreid") or "").strip()
        return _STORE_ALIASES[service], store_id, ""
    if not service:
        if steam_id:
            return "", "", steam_id
        if gog_id:
            return "gog", gog_id, ""
        humble = str(row.get("humblestoreid") or "").strip()
        if humble:
            return "humble", humble, ""
    return "", "", ""


def _lutris_runtime(
    out: LibraryGame,
    runner: str,
    service: str,
    wine: dict,
    conf: dict[str, str],
    data_dir: Path,
) -> None:
    if service == "steam" or runner == "steam":
        out.runtime = "steam"
        if not out.steam_appid:
            out.notes.append("Steam entry has no AppID")
    elif runner == "wine":
        out.runtime = "wine"
        out.runtime_tool, note = _lutris_wine(str(wine.get("version") or ""), conf, data_dir)
        if note:
            out.notes.append(note)
        if not out.prefix:
            out.notes.append("no Wine prefix recorded")
    elif runner == "linux":
        out.runtime = "native"
    else:
        out.runtime = "unsupported"
        out.problem = f"Lutris runner {runner or 'unknown'!r} has no TKArcade equivalent"


def _gamescope_args(system: dict) -> str:
    """Gamescope options from a Lutris `system` block, its own order."""
    args: list[str] = []
    mode = str(system.get("gamescope_window_mode") or "").strip()
    if mode in ("-f", "-b"):
        args.append(mode)
    for key, flags in (
        ("gamescope_game_res", ("-w", "-h")),
        ("gamescope_output_res", ("-W", "-H")),
    ):
        width, _, height = str(system.get(key) or "").strip().lower().partition("x")
        if width.isdigit() and height.isdigit():
            args.extend([flags[0], width, flags[1], height])
    fps = str(system.get("gamescope_fps_limiter") or "").strip()
    if fps.isdigit():
        args.extend(["-r", fps])
    flags = str(system.get("gamescope_flags") or "").strip()
    if flags:
        args.append(flags)
    if _truthy(system.get("gamescope_force_grab_cursor")):
        args.append("--force-grab-cursor")
    if _truthy(system.get("gamescope_hdr")):
        args.append("--hdr-enabled")
    return " ".join(args)


def _adapt_overlay_env(game: LibraryGame) -> None:
    """Move MangoHud env vars with a native option into it, drop them.

    Everything without an equivalent stays in `[env]` (vkBasalt, DXVK_HUD
    and friends).
    """
    env = game.env
    if _truthy(env.pop("MANGOHUD", "")):
        game.mangohud = True
    if _truthy(env.pop("MANGOHUD_DLSYM", "")):
        game.mangohud_args = "--dlsym"
    config_file = env.get("MANGOHUD_CONFIGFILE", "")
    if config_file:
        path = Path(_expand(config_file))
        if path.parent == xdg.config_home() / "MangoHud" and path.name:
            game.mangohud_config = path.name
            env.pop("MANGOHUD_CONFIGFILE", None)


def _lutris_system(system: dict, directory: str, out: LibraryGame) -> None:
    env = system.get("env")
    if isinstance(env, dict):
        for key, value in env.items():
            name = str(key).strip()
            if name:
                out.env[name] = _expand(value, directory)
    _adapt_overlay_env(out)
    for key, value in (
        ("prelaunch_command", "pre_command"),
        ("postexit_command", "post_command"),
    ):
        text = _expand(system.get(key), directory)
        if text:
            setattr(out, value, text)
    out.mangohud = out.mangohud or _truthy(system.get("mangohud"))
    out.gamemode = _truthy(system.get("gamemode"))
    if _truthy(system.get("gamescope")):
        out.gamescope = True
        out.gamescope_args = _gamescope_args(system)
    if _truthy(system.get("prelaunch_wait")):
        out.notes.append("prelaunch_wait has no equivalent")


def _lutris_game(
    row: dict,
    categories: list[str],
    conf: dict[str, str],
    data_dir: Path,
    mounts: tuple[tuple[str, str], ...],
) -> LibraryGame:
    configpath = row.get("configpath")
    yml_path = _lutris_game_config_path(configpath)
    yml = _read_yaml(yml_path) if yml_path is not None else {}
    game = yml.get("game") if isinstance(yml.get("game"), dict) else {}
    system = yml.get("system") if isinstance(yml.get("system"), dict) else {}
    wine = yml.get("wine") if isinstance(yml.get("wine"), dict) else {}

    directory = _path(game.get("directory") or row.get("directory"), "", True)
    runner = str(row.get("runner") or "").strip().casefold()
    service = str(row.get("service") or "").strip().casefold()
    store_kind, store_id, steam_appid = _lutris_store(row, service)
    if not steam_appid:
        steam_appid = _digits(game.get("appid"))
    if service == "steam" or runner == "steam":
        steam_appid = steam_appid or _digits(row.get("service_id")) or _digits(row.get("steamid"))

    name, version = cfgmod.split_name_version(str(row.get("name") or "").strip() or "Unnamed")
    out = LibraryGame(
        source="lutris",
        source_id=str(row.get("slug") or configpath or row.get("id") or ""),
        name=name,
        version=version,
        exe=_path(game.get("exe") or row.get("executable"), directory, False),
        args=str(game.get("args") or "").strip(),
        working_dir=_path(game.get("working_dir"), directory, True),
        prefix=_path(game.get("prefix"), directory, True),
        store_kind=store_kind,
        store_id=store_id,
        steam_appid=steam_appid,
        categories=cfgmod.normalize_categories(categories),
    )
    _lutris_runtime(out, runner, service, wine, conf, data_dir)
    _lutris_system(system, directory, out)
    if not out.exe and out.runtime != "steam":
        out.notes.append("no executable recorded")
    if yml_path is None and runner == "wine":
        out.notes.append("Lutris game config not found; executable and prefix may be empty")
    offline = _offline_problem(out, mounts)
    if offline:
        out.problem = offline if not out.problem else f"{out.problem}; {offline}"
    return out


def _yaml_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("yaml") is not None


def _lutris_games() -> tuple[list[LibraryGame], str]:
    if not _yaml_available():
        return [], "PyYAML is not installed, so Lutris game configs cannot be read"
    db = lutris_library_path()
    if db is None:
        return [], "No Lutris library found"
    try:
        rows, categories = _read_lutris_rows(db)
    except (OSError, sqlite3.Error) as e:
        return [], f"Could not read the Lutris library: {e}"
    conf = _lutris_conf()
    mounts = _mount_table()
    data_dir = db.parent
    for base in _lutris_bases():
        if base / "pga.db" == db:
            data_dir = base
            break
    games: list[LibraryGame] = []
    for row in rows:
        try:
            game_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            game_id = 0
        try:
            games.append(_lutris_game(row, categories.get(game_id, []), conf, data_dir, mounts))
        except Exception as e:  # one malformed row must not hide the rest
            games.append(
                LibraryGame(
                    source="lutris",
                    source_id=str(row.get("slug") or row.get("id") or ""),
                    name=str(row.get("name") or "Unnamed"),
                    runtime="unsupported",
                    problem=f"could not read this entry: {e}",
                )
            )
    games.sort(key=lambda g: g.name.casefold())
    return games, ""


# --- Faugus -------------------------------------------------------------


def _faugus_paths() -> tuple[list[Path], list[Path]]:
    home = Path.home()
    data = [
        xdg.data_home() / "faugus-launcher" / "games.json",
        home / ".var/app/io.github.Faugus.faugus-launcher/data/faugus-launcher/games.json",
    ]
    config = [
        xdg.config_home() / "faugus-launcher" / "config.json",
        home / ".var/app/io.github.Faugus.faugus-launcher/config/faugus-launcher/config.json",
    ]
    return data, config


def faugus_library_path() -> Path | None:
    for path in _faugus_paths()[0]:
        if path.is_file():
            return path
    return None


def _faugus_config() -> dict:
    for path in _faugus_paths()[1]:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _faugus_steam_runtime(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text or text == "disable-runtime":
        return "", ""
    text = text.removeprefix("umu-")
    runtime = cfgmod.normalize_steam_runtime(text)
    if runtime:
        return runtime, ""
    return "", f"Steam Linux Runtime {text!r} has no equivalent"


def _faugus_runner_name(value: object, config: dict) -> str:
    name = str(value or "").strip()
    if name == "Default":
        return str(config.get("default-runner") or "").strip()
    return name


def _faugus_system_proton(installs: list[runtimes.ProtonInstall]) -> tuple[str, str, str, str]:
    for install in installs:
        if install.name == "proton-cachyos-slr":
            return "umu", os.fspath(install.path), "", ""
    return (
        "umu",
        "/usr/share/steam/compatibilitytools.d/proton-cachyos-slr",
        "",
        "system Proton-CachyOS not found",
    )


def _faugus_proton_path(
    name: str, installs: list[runtimes.ProtonInstall]
) -> tuple[str, str, str, str] | None:
    path = _expand(name)
    if not path:
        return None
    wanted = _norm_exe(path)
    base = Path(path).name
    for install in installs:
        if _norm_exe(install.path) == wanted or install.name == base:
            return "umu", os.fspath(install.path), "", ""
    if os.path.isabs(path):
        return (
            "unsupported",
            "",
            "",
            f"Proton build {name!r} not found in the discovered installs",
        )
    return None


def _faugus_runner(
    value: object, config: dict, installs: list[runtimes.ProtonInstall]
) -> tuple[str, str, str, str]:
    """(runtime, tool, steam_runtime, problem) for a Faugus runner field.

    The runner path is never stat'ed: a disconnected external drive would
    block. It is matched against the already-discovered Proton installs.
    """
    name = _faugus_runner_name(value, config)
    simple = {
        "Linux-Native": ("native", "", "", ""),
        "Steam": ("steam", "", "", ""),
    }
    if name in simple:
        return simple[name]
    if name == "Proton-CachyOS (System)":
        return _faugus_system_proton(installs)
    if name in _FAUGUS_RESERVED:
        return "unsupported", "", "", f"reserved runner {name!r}; pick an installed Proton build"
    found = _faugus_proton_path(name, installs)
    if found is not None:
        return found
    if not name:
        return "unsupported", "", "", "no runner recorded"
    return "unsupported", "", "", f"runner {name!r} has no TKArcade equivalent"


def _faugus_env(text: object, notes: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = shlex.split(line, posix=True)
        except ValueError:
            notes.append(f"{line!r} has unbalanced quotes; dropped")
            continue
        if len(parts) == 1:
            key, sep, value = parts[0].partition("=")
            if sep and _ENV_KEY.fullmatch(key) and not key.startswith("-"):
                env[key] = value
                continue
        notes.append(f"{line!r} has no environment equivalent")
    return env


def _faugus_runtime(
    entry: dict, config: dict, installs: list[runtimes.ProtonInstall]
) -> tuple[str, str, str, str, str]:
    """(runtime, tool, steam_runtime, Steam AppID, problem)."""
    runtime, tool, steam_runtime, problem = _faugus_runner(entry.get("runner"), config, installs)
    steam_appid = _digits(entry.get("path")) if runtime == "steam" else ""
    if runtime == "steam" and not steam_appid:
        problem = "Steam entry has no numeric AppID"
    if runtime == "native":
        steam_runtime, note = _faugus_steam_runtime(entry.get("runtime"))
        if note:
            problem = note
    return runtime, tool, steam_runtime, steam_appid, problem


def _faugus_categories(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value] if value else []
    elif not isinstance(value, list):
        value = []
    return cfgmod.normalize_categories(value)


def _faugus_extra_notes(entry: dict, game: LibraryGame) -> None:
    for key, label in (
        ("protonfix", "protonfix"),
        ("addapp", "the additional application"),
        ("lossless_enabled", "lossless scaling"),
        ("discord_rpc", "Discord RPC"),
    ):
        if _truthy(entry.get(key)):
            game.notes.append(f"{label} has no equivalent")
    if not game.exe and game.runtime != "steam":
        game.notes.append("no executable recorded")
    if game.runtime in ("wine", "umu") and not game.prefix:
        game.notes.append("no Wine prefix recorded")


def _faugus_game(
    entry: dict,
    config: dict,
    installs: list[runtimes.ProtonInstall],
    mounts: tuple[tuple[str, str], ...],
) -> LibraryGame:
    title, version = cfgmod.split_name_version(str(entry.get("title") or "").strip() or "Unnamed")
    runtime, tool, steam_runtime, steam_appid, problem = _faugus_runtime(entry, config, installs)
    game = LibraryGame(
        source="faugus",
        source_id=str(entry.get("gameid") or title),
        name=title,
        version=version,
        exe=_path(entry.get("path")),
        args=str(entry.get("game_arguments") or "").strip(),
        prefix=_path(entry.get("prefix")),
        runtime=runtime,
        runtime_tool=tool,
        steam_runtime=steam_runtime,
        steam_appid=steam_appid,
        categories=_faugus_categories(entry.get("category")),
        mangohud=_truthy(entry.get("mangohud")),
        gamemode=_truthy(entry.get("gamemode")),
        inhibit_idle=_truthy(entry.get("no_sleep")),
        pre_command=_expand(entry.get("pre_launch")),
        post_command=_expand(entry.get("post_launch")),
    )
    game.env = _faugus_env(entry.get("launch_arguments"), game.notes)
    if _truthy(entry.get("sdl_enabled")):
        game.env["PROTON_PREFER_SDL"] = "1"
    _adapt_overlay_env(game)
    _faugus_extra_notes(entry, game)
    offline = _offline_problem(game, mounts)
    if offline:
        problem = offline if not problem else f"{problem}; {offline}"
    if problem:
        game.runtime = "unsupported"
        game.problem = problem
    return game


def _faugus_games() -> tuple[list[LibraryGame], str]:
    path = faugus_library_path()
    if path is None:
        return [], "No Faugus library found"
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as e:
        return [], f"Could not read the Faugus library: {e}"
    if not isinstance(data, list):
        return [], "The Faugus library is not a list of games"
    config = _faugus_config()
    installs = runtimes.proton_installs()
    mounts = _mount_table()
    games = [
        _faugus_game(entry, config, installs, mounts) for entry in data if isinstance(entry, dict)
    ]
    games.sort(key=lambda g: g.name.casefold())
    return games, ""


def list_games(source: str) -> tuple[list[LibraryGame], str]:
    """(games, hint) for one source; never raises for missing files."""
    if source == "lutris":
        return _lutris_games()
    if source == "faugus":
        return _faugus_games()
    return [], f"Unknown import source {source!r}"


# --- Mapping and matching ----------------------------------------------


def _apply_source_fields(cfg: cfgmod.GameConfig, game: LibraryGame, set_name: bool) -> None:
    """The per-game fields a non-Steam source writes onto a config."""
    if set_name:
        cfg.general.name = game.name
        cfg.metadata.version = game.version
    cfg.general.custom_executable = game.exe
    cfg.runtime.type = game.runtime if game.runtime in _RUNTIME_KINDS else ""
    cfg.runtime.tool = game.runtime_tool
    cfg.runtime.prefix = game.prefix
    cfg.runtime.prefix_exact = bool(game.prefix) and game.runtime in ("wine", "umu")
    cfg.runtime.steam_runtime = game.steam_runtime
    if game.store_kind:
        cfg.store.kind = game.store_kind
        cfg.store.id = game.store_id
    if game.mangohud:
        cfg.mangohud.enable = True
    if game.mangohud_args and game.mangohud_args not in cfg.mangohud.args:
        cfg.mangohud.args = " ".join(filter(None, [cfg.mangohud.args, game.mangohud_args]))
    if game.mangohud_config:
        cfg.mangohud.config_file = game.mangohud_config
    if game.gamescope:
        cfg.gamescope.enable = True
        cfg.gamescope.args = game.gamescope_args
    if game.gamemode:
        cfg.gamemode.feral_gamemode = True


def _apply_launch_fields(cfg: cfgmod.GameConfig, game: LibraryGame) -> None:
    """Launch behaviour every source writes: args, cwd, env, hooks."""
    cfg.general.launch_args = game.args
    cfg.general.launch_cwd = game.working_dir
    cfg.general.categories = cfgmod.normalize_categories(game.categories)
    cfg.env.vars = {**cfg.env.vars, **game.env}
    if game.inhibit_idle:
        cfg.session.inhibit_idle = True
    if game.pre_command:
        cfg.pre_post.pre_command = game.pre_command
    if game.post_command:
        cfg.pre_post.post_command = game.post_command
    if game.pre_command or game.post_command:
        cfg.pre_post.run_in_shell = True


def to_gameconfig(
    game: LibraryGame,
    appid: str,
    *,
    base: cfgmod.GameConfig | None = None,
    steam: bool = False,
    set_name: bool = True,
) -> tuple[cfgmod.GameConfig, list[str]]:
    """A complete GameConfig for one imported entry, plus its notes.

    `base` is the starting point: Global Defaults for a new game, the live
    config for an existing game's profile. The source fills what it has; a
    launcher toggle only turns something on, so a stored value the source
    does not know about survives.
    """
    cfg = base if base is not None else cfgmod.load_defaults()
    cfg.general.appid = appid
    if not steam:
        _apply_source_fields(cfg, game, set_name)
    _apply_launch_fields(cfg, game)
    cfg.notes.text = f"Imported from {SOURCE_LABELS.get(game.source, game.source)}."
    return cfg, list(game.notes)


@dataclass
class _Index:
    appids: set[str] = field(default_factory=set)
    steam: dict[str, str] = field(default_factory=dict)
    store: dict[tuple[str, str], str] = field(default_factory=dict)
    exe: dict[str, list[str]] = field(default_factory=dict)
    name: dict[str, list[str]] = field(default_factory=dict)

    def add(self, table: dict, key, appid: str) -> None:
        table.setdefault(key, []).append(appid)


def _config_index() -> _Index:
    index = _Index()
    for appid, name in steammod.list_games():
        numeric = steammod.steam_appid(appid)
        if numeric:
            index.steam[numeric] = name
    for appid in cfgmod.list_appids():
        try:
            cfg = cfgmod.load(appid)
        except Exception:
            continue
        index.appids.add(appid)
        if cfg.store.kind and cfg.store.id:
            index.store[(cfg.store.kind, cfg.store.id)] = appid
        exe = _norm_exe(cfg.general.custom_executable)
        if exe:
            index.add(index.exe, exe, appid)
        name = _norm_name(cfg.general.name)
        if name:
            index.add(index.name, name, appid)
    return index


def _match(game: LibraryGame, index: _Index) -> str:
    if game.steam_appid:
        target = f"steam-{game.steam_appid}"
        if target in index.appids or game.steam_appid in index.steam:
            return target
        return ""
    if game.store_kind and game.store_id:
        hit = index.store.get((game.store_kind, game.store_id))
        if hit:
            return hit
    exe = _norm_exe(game.exe)
    hits = index.exe.get(exe, []) if exe else []
    if len(hits) == 1:
        return hits[0]
    hits = index.name.get(_norm_name(game.name), [])
    if len(hits) == 1:
        return hits[0]
    return ""


def candidates(source: str) -> tuple[list[Candidate], str]:
    """Usable entries with their target, plus the reader hint."""
    games, hint = list_games(source)
    index = _config_index()
    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for game in games:
        if game.problem:
            out.append(Candidate(game, state="unavailable", detail=game.problem))
            continue
        if game.runtime == "steam" and not game.steam_appid:
            out.append(Candidate(game, state="unavailable", detail="Steam entry has no AppID"))
            continue
        target = _match(game, index)
        if game.runtime == "steam" and not target:
            out.append(
                Candidate(game, state="unavailable", detail="Steam game is not installed here")
            )
            continue
        key = (
            ("target", target) if target else ("game", _norm_exe(game.exe) or _norm_name(game.name))
        )
        if key in seen:
            continue
        seen.add(key)
        if target:
            out.append(Candidate(game, target=target, state="existing", detail=target))
        else:
            out.append(Candidate(game, state="new", detail=game.exe or game.prefix))
    return out, hint


@dataclass
class ImportResult:
    created: list[str] = field(default_factory=list)
    profiled: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    notes: dict[str, list[str]] = field(default_factory=dict)


def import_games(source: str, keys: list[str] | tuple[str, ...]) -> ImportResult:
    """Import the selected source keys: live configs for new, profiles for old."""
    chosen = {str(key) for key in keys or []}
    result = ImportResult()
    found, _hint = candidates(source)
    by_key = {candidate.game.source_id: candidate for candidate in found}
    for key in chosen:
        candidate = by_key.get(key)
        if candidate is None:
            result.skipped.append((key, "no longer in the library"))
            continue
        if candidate.state == "unavailable":
            result.skipped.append((candidate.game.name, candidate.detail))
            continue
        game = candidate.game
        try:
            if candidate.target:
                cfg, notes = to_gameconfig(
                    game,
                    candidate.target,
                    base=cfgmod.load(candidate.target),
                    steam=candidate.target.startswith("steam-"),
                    set_name=False,
                )
                cfgmod.save_profile(candidate.target, source, cfg)
                result.profiled.append(candidate.target)
            else:
                appid = cfgmod.new_local_id(game.name)
                cfg, notes = to_gameconfig(game, appid)
                cfgmod.save(cfg)
                result.created.append(appid)
        except Exception as e:
            result.skipped.append((game.name, f"save failed: {e}"))
            continue
        if notes:
            result.notes[game.name] = notes
    return result
