"""Runtime discovery: Wine, Proton and graphics-layer installations.

Read-only on purpose: Proton installs are managed by ProtonPlus/ProtonUp-Qt
and Wine comes from the distro (or an explicit path), so TKArcade only
lists what is already on disk and never downloads or updates anything.
Stdlib only: the launcher imports this on every game start.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

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
    low = path.name.lower()
    try:
        if (path / "proton").is_file() or (path / "version").is_file():
            return True
    except OSError:
        return False
    return "proton" in low or low.startswith(("ge-", "dw-", "wine"))


def proton_base_dirs() -> list[Path]:
    """Steam's compat install roots (compatibilitytools.d + steamapps/common)."""
    out: list[Path] = []
    for root in steammod.steam_roots():
        out += [root / "compatibilitytools.d", root / "steamapps" / "common"]
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


def proton_installs(extra: str = "") -> list[ProtonInstall]:
    """Installed Proton builds: Steam roots plus the configured extra dirs.

    Each extra entry is either an install directory itself or a directory
    holding one install per subdirectory. Sorted by name, deduplicated by
    real path.
    """
    found: dict[Path, ProtonInstall] = {}
    bases = proton_base_dirs()
    for entry in _split_dirs(extra):
        if _looks_like_proton(entry):
            _add_proton(found, entry)
        else:
            bases.append(entry)
    for base in bases:
        _scan_proton_base(found, base)
    return sorted(found.values(), key=lambda p: p.name.casefold())


def find_proton(value: str, extra: str = "") -> ProtonInstall | None:
    """Resolve a configured Proton path or compatibilitytools name."""
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_dir():
        return ProtonInstall(path.name, path.resolve())
    low = text.casefold()
    for install in proton_installs(extra):
        if install.name.casefold() == low:
            return install
    return None


def wine_binary(override: str = "") -> str:
    """Wine executable: explicit path/name first, else PATH ('' = none)."""
    text = str(override or "").strip()
    if text:
        path = Path(text).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return os.fspath(path)
        return shutil.which(text) or ""
    for name in ("wine", "wine64"):
        found = shutil.which(name)
        if found:
            return found
    return ""


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


def graphics_dirs(kind: str, extra: str = "") -> list[Path]:
    """Configured dirs plus the built-in Lutris runtime locations."""
    rt = "dxvk" if kind == "dxvk" else "vkd3d"
    defaults = [
        xdg.data_home() / "lutris" / "runtime" / rt,
        Path.home() / ".var/app/net.lutris.Lutris/data/lutris/runtime" / rt,
    ]
    return defaults + _split_dirs(extra)


def _version_key(name: str) -> tuple:
    return (tuple(int(p) for p in re.findall(r"\d+", name)), name.casefold())


def graphics_versions(kind: str, extra: str = "") -> list[GraphicsVersion]:
    """Installed versions for one layer, newest first.

    A directory counts as a version when it holds x64/<dll> (or x32/x86);
    a directory without the DLL is treated as a parent of version dirs.
    Deduplicated by real path.
    """
    found: dict[Path, GraphicsVersion] = {}
    for root in graphics_dirs(kind, extra):
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


def pick_graphics(kind: str, extra: str = "") -> GraphicsVersion | None:
    """Newest installed version of a layer, or None."""
    versions = graphics_versions(kind, extra)
    return versions[0] if versions else None
