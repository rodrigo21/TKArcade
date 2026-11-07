"""Runtime discovery: Wine, Proton and graphics-layer installations.

Read-only on purpose: Proton installs are managed by ProtonPlus/ProtonUp-Qt
and Wine comes from the distro (or an explicit path). Graphics versions are
read from the managed installs (written by the GUI-only
`runtime_archives` helper) and the configured directories; this module
itself never downloads, updates or unpacks anything.
Stdlib only: the launcher imports this on every game start.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config as cfgmod
from . import steam as steammod
from . import xdg

#: DLL a version directory must ship to count as an installed layer.
GRAPHICS_DLLS = {"dxvk": "d3d11.dll", "vkd3d": "d3d12.dll"}

#: Source subdirectory -> wine target (64-bit prefixes mirror system32).
_DLL_TARGETS = (("x64", "system32"), ("x32", "syswow64"), ("x86", "syswow64"))


@dataclass(frozen=True)
class ProtonInstall:
    """One Proton/GE/DW install directory."""

    name: str
    path: Path


@dataclass(frozen=True)
class GraphicsVersion:
    """One DXVK or vkd3d-proton version directory."""

    kind: str  # "dxvk" | "vkd3d"
    name: str
    root: Path

    def files(self) -> list[tuple[Path, str]]:
        """(source DLL, wine target dir) pairs for this version."""
        dll = GRAPHICS_DLLS.get(self.kind, "")
        out: list[tuple[Path, str]] = []
        for sub, target in _DLL_TARGETS:
            folder = self.root / sub
            if not (folder / dll).is_file():
                continue
            out.extend((src, target) for src in sorted(folder.glob("*.dll")))
        return out

    def complete(self) -> bool:
        """True when the 64-bit side is usable (32-bit is optional)."""
        return (self.root / "x64" / GRAPHICS_DLLS.get(self.kind, "")).is_file()


def _split_dirs(extra: str) -> list[Path]:
    out = []
    for raw in str(extra or "").split(os.pathsep):
        text = raw.strip()
        if text:
            out.append(Path(text).expanduser())
    return out


def _looks_like_proton(path: Path) -> bool:
    try:
        return (path / "proton").is_file()
    except OSError:
        return False


#: Distro-packaged Steam tree (Arch, Debian): its Proton is the system one.
SYSTEM_STEAM_ROOT = Path("/usr/share/steam")


def proton_base_dirs() -> list[Path]:
    """Proton install roots: the system tree first, then every Steam library."""
    out: list[Path] = []
    system = SYSTEM_STEAM_ROOT
    if system.is_dir():
        out += [system / "compatibilitytools.d", system / "steamapps" / "common"]
    for root in steammod.steam_roots():
        out.append(root / "compatibilitytools.d")
    for library in steammod.library_paths():
        # library_paths() hands back <library>/steamapps; compat tools are
        # read from both spellings Steam uses.
        out += [
            library / "compatibilitytools.d",
            library.parent / "compatibilitytools.d",
            library / "common",
        ]
    return out


def _add_proton(found: dict[Path, ProtonInstall], path: Path) -> None:
    try:
        if path.is_dir():
            found.setdefault(path.resolve(), ProtonInstall(path.name, path.resolve()))
    except OSError:
        pass


def _scan_proton_base(found: dict[Path, ProtonInstall], base: Path) -> None:
    try:
        children = sorted(base.iterdir())
    except OSError:
        return
    for entry in children:
        try:
            if entry.is_dir() and _looks_like_proton(entry):
                _add_proton(found, entry)
        except OSError:
            continue


def proton_installs() -> list[ProtonInstall]:
    """Installed Proton builds, system first, then every Steam library.

    The order is the discovery order (``proton_base_dirs``), so the first
    entry is the build a game with no explicit choice should use.
    Deduplicated by real path.
    """
    found: dict[Path, ProtonInstall] = {}
    for base in proton_base_dirs():
        _scan_proton_base(found, base)
    return list(found.values())


def pick_proton(installs: list[ProtonInstall], name: str = "") -> ProtonInstall | None:
    """The named install, else the first discovered (None = none at all)."""
    text = str(name or "").strip().casefold()
    if text:
        for install in installs:
            if install.name.casefold() == text:
                return install
    return installs[0] if installs else None


def find_proton(value: str) -> ProtonInstall | None:
    """Resolve a configured Proton path or compatibilitytools name."""
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_dir():
        return ProtonInstall(path.name, path.resolve()) if _looks_like_proton(path) else None
    low = text.casefold()
    for install in proton_installs():
        if install.name.casefold() == low:
            return install
    return None


def wine_path() -> str:
    """The Wine found on PATH ("" = none)."""
    for name in ("wine", "wine64"):
        found = shutil.which(name)
        if found:
            return found
    return ""


def wine_executable(path: str) -> str:
    """Executable for a stored path or a bare command name ("" = missing)."""
    text = str(path or "").strip()
    if not text:
        return ""
    candidate = Path(text).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return os.fspath(candidate)
    return shutil.which(text) or ""


@dataclass
class WineVersion:
    name: str
    path: str  # resolved executable, or the stored path when missing
    ok: bool


def wine_versions(text: str = "") -> list[WineVersion]:
    """Configured Wine entries in stored order (PATH excluded)."""
    out: list[WineVersion] = []
    for name, path in cfgmod.parse_wine_versions(text):
        found = wine_executable(path)
        out.append(WineVersion(name, found or path, bool(found)))
    return out


def wine_binary(override: str = "", versions: str = "") -> str:
    """Wine executable: a managed entry name, a path/name, else PATH."""
    text = str(override or "").strip()
    if text:
        for entry in cfgmod.parse_wine_versions(versions):
            if entry[0].casefold() == text.casefold():
                return wine_executable(entry[1])
        return wine_executable(text)
    return wine_path()


#: Steam Linux Runtime name -> directory umu keeps under <data>/umu. scout is
#: not a runtime directory: umu ships it as a compatibility tool instead.
_UMU_RUNTIME_DIRS = {"soldier": "steamrt2", "sniper": "steamrt3", "steamrt4": "steamrt4"}


def umu_root() -> Path:
    """Where umu keeps its downloads."""
    return xdg.data_home() / "umu"


def steam_runtime_dir(name: str) -> Path | None:
    """Directory umu installs a Steam Linux Runtime into (None = unknown name)."""
    text = str(name or "").strip().lower()
    if text == "scout":
        return umu_root() / "compatibilitytools" / "umu-scout"
    variant = _UMU_RUNTIME_DIRS.get(text)
    return umu_root() / variant if variant else None


def steam_runtime_installed(name: str) -> bool:
    """Whether umu already downloaded the runtime (it fetches it on first run)."""
    path = steam_runtime_dir(name)
    return bool(path and path.is_dir())


def _version_key(name: str) -> tuple:
    return (tuple(int(p) for p in re.findall(r"\d+", name)), name.casefold())


#: Preset ids the Runtime manager offers per layer -> GitHub owner/repo.
GRAPHICS_FORKS = {
    "sarek": "zeyadadev/DXVK-Sarek",
    "gplasync": "Waim908/dxvk-gplasync-mirror",
}


def graphics_repo(source: str = "") -> str:
    """GitHub owner/repo behind a ``[ui] dxvk_source``/``vkd3d_source`` ("" = official)."""
    text = str(source or "").strip()
    if text.startswith("custom:"):
        return text.split(":", 1)[1].strip()
    return GRAPHICS_FORKS.get(text, "")


#: Distro builds of a graphics layer (one version per tree, read-only).
SYSTEM_GRAPHICS_DIRS = {
    "dxvk": (Path("/usr/share/dxvk"), Path("/usr/local/share/dxvk")),
    "vkd3d": (
        Path("/usr/share/vkd3d-proton"),
        Path("/usr/local/share/vkd3d-proton"),
    ),
}


def system_graphics_roots(kind: str) -> list[Path]:
    """System-wide trees that hold version DLLs (existing ones only)."""
    return [path for path in SYSTEM_GRAPHICS_DIRS.get(kind, ()) if path.is_dir()]


def _graphics_roots(kind: str) -> list[Path]:
    """Managed installs, the system trees, then the registered folders."""
    return [
        xdg.runtimes_dir() / kind,
        *system_graphics_roots(kind),
        *[Path(item).expanduser() for item in cfgmod.external_dirs(kind)],
    ]


def graphics_versions(kind: str) -> list[GraphicsVersion]:
    """Installed versions for one layer, newest first.

    The managed directory comes first, then the registered ones. A
    directory counts as a version when it holds x64/<dll> (or x32/x86);
    a directory without the DLL is treated as a parent of version dirs.
    Deduplicated by real path.
    """
    found: dict[Path, GraphicsVersion] = {}
    for root in _graphics_roots(kind):
        try:
            if not root.is_dir():
                continue
            seen = GraphicsVersion(kind, root.name, root).complete()
            candidates = [root] if seen else []
            if not seen:
                candidates = [p for p in sorted(root.iterdir()) if p.is_dir()]
        except OSError:
            continue
        for cand in candidates:
            version = GraphicsVersion(kind, cand.name, cand)
            if version.complete():
                found.setdefault(cand.resolve(), version)
    return sorted(found.values(), key=lambda v: _version_key(v.name), reverse=True)


def pick_graphics(kind: str, name: str = "") -> GraphicsVersion | None:
    """Newest installed version, the one named `name`, or None."""
    versions = graphics_versions(kind)
    wanted = str(name or "").strip()
    if wanted:
        return next((v for v in versions if v.name == wanted), None)
    return versions[0] if versions else None
