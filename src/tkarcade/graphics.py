"""Graphics layers (DXVK / vkd3d-proton) for local Wine prefixes.

Installing copies the version's DLLs into the prefix and records exactly
what was copied in ``<prefix>/tkarcade-graphics.json``; removing only
deletes those recorded files. Switching layers never deletes anything:
each layer is selected per launch through ``WINEDLLOVERRIDES`` ("n,b"
prefers the copied DLL, "b" forces Wine's own implementation). DXVK and
vkd3d-proton cover different Direct3D versions, so both can be enabled.

Stdlib only: the launcher installs the layer at launch.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import runtimes

MARKER = "tkarcade-graphics.json"
MARKER_VERSION = 1

#: WINEDLLOVERRIDES fragments. DXVK and vkd3d-proton cover different
#: Direct3D versions, so a prefix can run both; anything not enabled is
#: forced to the builtin DLL so a layer copied earlier stops winning.
_BUILTIN = "d3d9,d3d10core,d3d11,d3d12,dxgi=b"
_DXVK = "d3d9,d3d10core,d3d11,dxgi=n,b"
_VKD3D = "d3d12=n,b"

#: Marker layer key per installed layer.
_LAYER_KIND = {"dxvk": "dxvk", "vkd3d": "vkd3d"}


def overrides(dxvk: bool = False, vkd3d: str = "") -> str:
    """WINEDLLOVERRIDES value for the enabled layers.

    ``vkd3d`` is "" (Wine builtin), "proton" (vkd3d-proton) or "wine"
    (forced builtin, same effect as "" but explicit).
    """
    if not dxvk and vkd3d != "proton":
        return _BUILTIN
    parts = [_DXVK if dxvk else "d3d9,d3d10core,d3d11,dxgi=b"]
    parts.append(_VKD3D if vkd3d == "proton" else "d3d12=b")
    return ";".join(parts)


def enabled_kinds(dxvk: bool, vkd3d: str) -> list[str]:
    """Layer kinds that must be copied into the prefix for this setting."""
    kinds = []
    if dxvk:
        kinds.append("dxvk")
    if vkd3d == "proton":
        kinds.append("vkd3d")
    return kinds


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


def launch_env(prefix: Path, dxvk: bool, vkd3d: str, prefs: object) -> tuple[dict, list[str]]:
    """Environment for the enabled layers, installing them first.

    All layers off: no overrides unless a previous install left a marker
    (then force the builtin DLLs so the old layer stops winning). A layer
    whose version is missing falls back for its own Direct3D versions.
    """
    prefix = Path(prefix)
    effective_dxvk = bool(dxvk)
    effective_vkd3d = vkd3d if vkd3d in ("proton", "wine") else ""
    attempted = effective_dxvk or effective_vkd3d == "proton"
    warnings: list[str] = []
    if effective_dxvk:
        ok, w = install(prefix, "dxvk", prefs)
        warnings += w
        effective_dxvk = ok
    if effective_vkd3d == "proton":
        ok, w = install(prefix, "vkd3d", prefs)
        warnings += w
        if not ok:
            effective_vkd3d = ""
    if effective_vkd3d != "wine" and not attempted and not marker_path(prefix).is_file():
        return {}, warnings
    return {"WINEDLLOVERRIDES": overrides(effective_dxvk, effective_vkd3d)}, warnings
