"""Graphics layers (DXVK / vkd3d-proton) for local Wine prefixes.

Installing copies the version's DLLs into the prefix and records exactly
what was copied in ``<prefix>/tkarcade-graphics.json``; removing only
deletes those recorded files. Switching layers never deletes anything:
the layer is selected per launch through ``WINEDLLOVERRIDES`` ("n,b"
prefers the copied DLL, "b" forces Wine's own implementation).

Stdlib only: the launcher installs the layer at launch.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import runtimes

MARKER = "tkarcade-graphics.json"
MARKER_VERSION = 1

#: WINEDLLOVERRIDES per layer. The empty layer forces the builtin DLLs so
#: a previously installed layer stops winning until it is removed.
OVERRIDES = {
    "": "d3d9,d3d10core,d3d11,d3d12,dxgi=b",
    "dxvk": "d3d9,d3d10core,d3d11,dxgi=n,b;d3d12=b",
    "vkd3d": "d3d12=n,b;d3d9,d3d10core,d3d11,dxgi=b",
    "vkd3d-wine": "d3d9,d3d10core,d3d11,d3d12,dxgi=b",
}

#: Marker layer key per configured layer.
_LAYER_KIND = {"dxvk": "dxvk", "vkd3d": "vkd3d"}


def overrides(layer: str) -> str:
    """WINEDLLOVERRIDES value for a layer ("" for unknown/off)."""
    return OVERRIDES.get(layer, OVERRIDES[""])


def marker_path(prefix: Path) -> Path:
    return Path(prefix) / MARKER


def read_marker(prefix: Path) -> dict:
    """Marker document, or {} when missing/unreadable (never raises)."""
    try:
        data = json.loads(marker_path(prefix).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_marker(prefix: Path, data: dict) -> None:
    marker_path(prefix).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _safe_dest(prefix: Path, rel: str) -> Path | None:
    """Only accept recorded DLLs inside drive_c/windows/{system32,syswow64}."""
    parts = Path(rel).parts
    if len(parts) != 4 or parts[0] != "drive_c" or parts[1] != "windows":
        return None
    if parts[2] not in ("system32", "syswow64") or not parts[3].lower().endswith(".dll"):
        return None
    if any(p in ("", ".", "..") for p in parts):
        return None
    return Path(prefix) / rel


def layer_dirs(layer: str, prefs: object) -> str:
    """Configured version directories for a graphics layer ("" = none)."""
    if layer == "dxvk":
        return str(getattr(prefs, "dxvk_dirs", "") or "")
    if layer == "vkd3d":
        return str(getattr(prefs, "vkd3d_dirs", "") or "")
    return ""


def installed(prefix: Path) -> dict[str, str]:
    """Layer key -> installed version name, from the marker."""
    layers = read_marker(prefix).get("layers", {})
    if not isinstance(layers, dict):
        return {}
    out = {}
    for key, entry in layers.items():
        if isinstance(entry, dict):
            out[str(key)] = str(entry.get("version", ""))
    return out


def install(prefix: Path, layer: str, prefs: object) -> tuple[bool, list[str]]:
    """Copy the newest version of `layer` into the prefix (idempotent).

    Returns (ok, warnings). Failure never aborts the launch: the launcher
    falls back to the builtin DLLs and reports the warning.
    """
    kind = _LAYER_KIND.get(layer)
    if not kind:
        return True, []
    extra = layer_dirs(layer, prefs)
    version = runtimes.pick_graphics(kind, extra)
    if version is None:
        label = "DXVK" if kind == "dxvk" else "vkd3d-proton"
        return False, [
            f"{label} layer enabled but no version found; check the {label} directories in Preferences"
        ]
    files = version.files()
    if not files:
        return False, [f"{kind}: version {version.name} has no DLLs for this prefix"]
    copied: list[str] = []
    for src, target in files:
        dest_dir = Path(prefix) / "drive_c" / "windows" / target
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        try:
            if not dest.is_file() or dest.read_bytes() != src.read_bytes():
                dest.write_bytes(src.read_bytes())
        except OSError as e:
            return False, [f"{kind}: could not install {src.name}: {e}"]
        copied.append(dest.relative_to(prefix).as_posix())
    marker = read_marker(prefix)
    layers = marker.get("layers") if isinstance(marker.get("layers"), dict) else {}
    previous = layers.get(kind) if isinstance(layers.get(kind), dict) else {}
    old_files = set(previous.get("files", []) or [])
    layers[kind] = {"version": version.name, "files": sorted(old_files | set(copied))}
    marker = {"version": MARKER_VERSION, "layers": layers}
    try:
        _write_marker(prefix, marker)
    except OSError as e:
        return False, [f"{kind}: layer installed but the marker could not be written: {e}"]
    return True, []


def uninstall(prefix: Path, kind: str = "") -> tuple[int, list[str]]:
    """Remove the files TKArcade copied for one layer ("" = every layer).

    Only paths recorded in the marker and inside drive_c/windows are
    touched; anything else in the prefix is left alone.
    """
    marker = read_marker(prefix)
    layers = marker.get("layers") if isinstance(marker.get("layers"), dict) else {}
    keys = [kind] if kind else list(layers)
    removed = 0
    warnings: list[str] = []
    for key in keys:
        entry = layers.get(key) if isinstance(layers.get(key), dict) else {}
        for rel in entry.get("files", []) or []:
            dest = _safe_dest(prefix, str(rel))
            if dest is None:
                warnings.append(f"ignored unsafe marker path: {rel!r}")
                continue
            try:
                if dest.is_file():
                    dest.unlink()
                    removed += 1
            except OSError as e:
                warnings.append(f"could not remove {dest}: {e}")
        layers.pop(key, None)
    try:
        if layers:
            _write_marker(prefix, {"version": MARKER_VERSION, "layers": layers})
        else:
            marker_path(prefix).unlink(missing_ok=True)
    except OSError as e:
        warnings.append(f"could not update the graphics marker: {e}")
    return removed, warnings


def launch_env(prefix: Path, layer: str, prefs: object) -> tuple[dict, list[str]]:
    """Environment for the configured layer, installing it first.

    Empty layer: no overrides unless a previous install left a marker
    (then force the builtin DLLs so the old layer stops winning).
    """
    prefix = Path(prefix)
    if layer in (None, ""):
        if marker_path(prefix).is_file():
            return {"WINEDLLOVERRIDES": overrides("")}, []
        return {}, []
    if layer in _LAYER_KIND:
        ok, warnings = install(prefix, layer, prefs)
        if not ok:
            return {"WINEDLLOVERRIDES": overrides("")}, warnings
    return {"WINEDLLOVERRIDES": overrides(layer)}, []
