"""Graphics layer install/remove (DXVK, vkd3d-proton) in a wine prefix."""

import json

from tkarcade import config as C
from tkarcade import graphics as G


def _prefs(tmp_path, kind="dxvk", extra=None):
    prefs = C.load_preferences()
    if kind == "dxvk":
        prefs.dxvk_dirs = str(extra or tmp_path / "dxvk")
    elif kind == "vkd3d":
        prefs.vkd3d_dirs = str(extra or tmp_path / "vkd3d")
    return prefs


def _version(base, name, dll, files=()):
    root = base / name
    for sub in ("x64", "x32"):
        (root / sub).mkdir(parents=True)
        (root / sub / dll).write_bytes(f"{name}-{sub}".encode())
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rel.encode())
    return root


def test_install_copies_and_records(xdg_env, tmp_path):
    base = tmp_path / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll", ("x64/dxgi.dll", "x32/dxgi.dll"))
    prefix = tmp_path / "prefix"
    prefs = _prefs(tmp_path, "dxvk", base)
    ok, warnings = G.install(prefix, "dxvk", prefs)
    assert ok and warnings == []
    system32 = prefix / "drive_c/windows/system32"
    assert (system32 / "d3d11.dll").read_bytes() == b"v2.6.2-x64"
    assert (system32 / "dxgi.dll").is_file()
    assert (prefix / "drive_c/windows/syswow64/d3d11.dll").is_file()
    marker = G.read_marker(prefix)
    assert marker["layers"]["dxvk"]["version"] == "v2.6.2"
    recorded = marker["layers"]["dxvk"]["files"]
    assert "drive_c/windows/system32/d3d11.dll" in recorded
    assert G.installed(prefix) == {"dxvk": "v2.6.2"}


def test_install_is_idempotent_and_keeps_old_files(xdg_env, tmp_path):
    base = tmp_path / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll", ("x64/dxgi.dll",))
    prefix = tmp_path / "prefix"
    prefs = _prefs(tmp_path, "dxvk", base)
    assert G.install(prefix, "dxvk", prefs)[0]
    first = G.read_marker(prefix)["layers"]["dxvk"]["files"]
    assert G.install(prefix, "dxvk", prefs)[0]
    assert G.read_marker(prefix)["layers"]["dxvk"]["files"] == first
    # A newer version with fewer DLLs keeps the old ones recorded.
    _version(base, "v2.7", "d3d11.dll")
    assert G.install(prefix, "dxvk", prefs)[0]
    entry = G.read_marker(prefix)["layers"]["dxvk"]
    assert entry["version"] == "v2.7"
    assert "drive_c/windows/system32/dxgi.dll" in entry["files"]


def test_switch_layers_then_uninstall_all(xdg_env, tmp_path):
    dxvk = tmp_path / "dxvk"
    vkd3d = tmp_path / "vkd3d"
    _version(dxvk, "v2.6.2", "d3d11.dll")
    _version(vkd3d, "v2.13", "d3d12.dll")
    prefs = _prefs(tmp_path, "dxvk", dxvk)
    prefs.vkd3d_dirs = str(vkd3d)
    prefix = tmp_path / "prefix"
    assert G.install(prefix, "dxvk", prefs)[0]
    assert G.install(prefix, "vkd3d", prefs)[0]
    assert G.installed(prefix) == {"dxvk": "v2.6.2", "vkd3d": "v2.13"}
    removed, warnings = G.uninstall(prefix)
    assert warnings == []
    assert removed == 4
    assert not G.read_marker(prefix).get("layers")
    assert not G.marker_path(prefix).is_file()
    assert not (prefix / "drive_c/windows/system32/d3d11.dll").exists()
    assert not (prefix / "drive_c/windows/system32/d3d12.dll").exists()


def test_uninstall_only_touches_recorded_files(xdg_env, tmp_path):
    base = tmp_path / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll")
    prefix = tmp_path / "prefix"
    manual = prefix / "drive_c/windows/system32/manual.dll"
    manual.parent.mkdir(parents=True)
    manual.write_bytes(b"mine")
    prefs = _prefs(tmp_path, "dxvk", base)
    assert G.install(prefix, "dxvk", prefs)[0]
    removed, _warnings = G.uninstall(prefix, "dxvk")
    assert removed == 2
    assert manual.is_file()
    assert G.uninstall(prefix)[0] == 0  # marker gone, nothing left to remove


def test_uninstall_ignores_unsafe_marker_paths(xdg_env, tmp_path):
    prefix = tmp_path / "prefix"
    outside = tmp_path / "outside.dll"
    outside.write_bytes(b"keep")
    marker = {
        "version": 1,
        "layers": {
            "dxvk": {
                "version": "v1",
                "files": [
                    "../outside.dll",
                    "drive_c/windows/system32/../../../../outside.dll",
                    "drive_c/other/thing.dll",
                    "drive_c/windows/system32/ok.dll",
                ],
            }
        },
    }
    prefix.mkdir(parents=True)
    G.marker_path(prefix).write_text(json.dumps(marker), encoding="utf-8")
    ok = prefix / "drive_c/windows/system32/ok.dll"
    ok.parent.mkdir(parents=True)
    ok.write_bytes(b"ok")
    removed, warnings = G.uninstall(prefix, "dxvk")
    assert removed == 1
    assert outside.is_file()
    assert len(warnings) == 3
    assert not ok.exists()


def test_overrides_per_layer():
    assert G.overrides("") == "d3d9,d3d10core,d3d11,d3d12,dxgi=b"
    assert G.overrides("dxvk").startswith("d3d9,d3d10core,d3d11,dxgi=n,b")
    assert G.overrides("dxvk").endswith("d3d12=b")
    assert G.overrides("vkd3d").startswith("d3d12=n,b")
    assert G.overrides("vkd3d-wine") == G.overrides("")


def test_launch_env_off_and_installed(xdg_env, tmp_path):
    prefix = tmp_path / "prefix"
    prefs = _prefs(tmp_path)
    assert G.launch_env(prefix, "", prefs) == ({}, [])
    base = tmp_path / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll")
    prefs = _prefs(tmp_path, "dxvk", base)
    env, warnings = G.launch_env(prefix, "dxvk", prefs)
    assert warnings == []
    assert env["WINEDLLOVERRIDES"].startswith("d3d9,d3d10core,d3d11,dxgi=n,b")
    # Turning the layer off after an install forces the builtin DLLs.
    env, warnings = G.launch_env(prefix, "", prefs)
    assert warnings == []
    assert env["WINEDLLOVERRIDES"] == G.overrides("")
    assert G.installed(prefix) == {"dxvk": "v2.6.2"}


def test_launch_env_without_versions_warns_and_falls_back(xdg_env, tmp_path):
    prefix = tmp_path / "prefix"
    prefs = _prefs(tmp_path, "vkd3d", tmp_path / "nowhere")
    env, warnings = G.launch_env(prefix, "vkd3d", prefs)
    assert any("vkd3d" in w for w in warnings)
    assert env["WINEDLLOVERRIDES"] == G.overrides("")
    assert not G.marker_path(prefix).is_file()


def test_vkd3d_wine_layer_installs_nothing(xdg_env, tmp_path):
    prefix = tmp_path / "prefix"
    prefs = _prefs(tmp_path)
    env, warnings = G.launch_env(prefix, "vkd3d-wine", prefs)
    assert warnings == []
    assert env["WINEDLLOVERRIDES"] == G.overrides("")
    assert not G.marker_path(prefix).is_file()


def test_launcher_installs_the_layer(xdg_env, fake_bin):
    from tkarcade.launcher import build_final_command

    fake_bin("wine")
    base = xdg_env["data"] / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll")
    prefs = C.load_preferences()
    prefs.dxvk_dirs = str(base)
    C.save_preferences(prefs)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.game_type = "wine"
    cfg.general.custom_executable = "/games/doom.exe"
    cfg.graphics.layer = "dxvk"
    _cmd, env, warnings = build_final_command(cfg, [])
    prefix = xdg_env["data"] / "tkarcade/prefixes/local-doom"
    assert (prefix / "drive_c/windows/system32/d3d11.dll").is_file()
    assert env["WINEDLLOVERRIDES"].startswith("d3d9")
    assert warnings == []


def test_launcher_respects_a_game_override(xdg_env, fake_bin):
    from tkarcade.launcher import build_final_command

    fake_bin("wine")
    base = xdg_env["data"] / "dxvk"
    _version(base, "v2.6.2", "d3d11.dll")
    prefs = C.load_preferences()
    prefs.dxvk_dirs = str(base)
    C.save_preferences(prefs)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.game_type = "wine"
    cfg.general.custom_executable = "/games/doom.exe"
    cfg.graphics.layer = "dxvk"
    cfg.env.vars = {"WINEDLLOVERRIDES": "d3d11=n"}
    _cmd, env, warnings = build_final_command(cfg, [])
    assert env["WINEDLLOVERRIDES"] == "d3d11=n"
    assert any("WINEDLLOVERRIDES" in w for w in warnings)


def test_validate_flags_missing_graphics_version(xdg_env):
    from tkarcade import launcher as L

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.game_type = "wine"
    cfg.general.custom_executable = "/bin/true"
    cfg.graphics.layer = "dxvk"
    C.save(cfg)
    issues = L.validate_game("local-doom")
    assert any("no installed version" in i for i in issues)
