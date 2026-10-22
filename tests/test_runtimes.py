"""Runtime discovery: Proton installs, Wine binaries and graphics layers."""

from tkarcade import runtimes as R


def _install(base, name, marker="version"):
    path = base / name
    path.mkdir(parents=True)
    (path / marker).write_text("x\n")
    return path


def _graphics(base, name, dll, arch=None):
    root = base / name
    for sub in arch or ("x64", "x32"):
        (root / sub).mkdir(parents=True)
        (root / sub / dll).write_text("dll")
    return root


def test_proton_installs_from_steam_root(xdg_env):
    root = xdg_env["home"] / ".local/share/Steam"
    tools = root / "compatibilitytools.d"
    _install(tools, "GE-Proton9-1")
    _install(tools, "DW-Proton Latest")
    (tools / "not-a-tool").mkdir()  # no marker, no proton in the name
    installs = R.proton_installs()
    assert [i.name for i in installs] == ["DW-Proton Latest", "GE-Proton9-1"]


def test_proton_installs_extra_dirs(xdg_env, tmp_path):
    extra = tmp_path / "extra"
    _install(extra, "GE-Proton10-1")
    installs = R.proton_installs(str(extra))
    assert [i.name for i in installs] == ["GE-Proton10-1"]
    # A single install directory (not a parent) also counts.
    direct = _install(tmp_path / "direct", "Proton-CachyOS")
    assert [i.name for i in R.proton_installs(str(direct))] == ["Proton-CachyOS"]


def test_find_proton_by_name_and_path(xdg_env, tmp_path):
    tools = xdg_env["home"] / ".local/share/Steam/compatibilitytools.d"
    path = _install(tools, "GE-Proton9-1")
    assert R.find_proton("ge-proton9-1").path == path.resolve()
    assert R.find_proton(path).name == "GE-Proton9-1"
    assert R.find_proton("nope") is None
    assert R.find_proton("") is None


def test_wine_binary_override_and_path(fake_bin, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert R.wine_binary("") == ""
    path = fake_bin("wine")
    assert R.wine_binary("") == str(path)
    assert R.wine_binary("wine") == str(path)
    by_path = fake_bin("custom-wine")
    assert R.wine_binary(str(by_path)) == str(by_path)
    assert R.wine_binary(str(by_path)) == str(by_path)
    assert R.wine_binary("/does/not/exist") == ""


def test_graphics_versions_newest_first(xdg_env):
    base = xdg_env["data"] / "lutris/runtime/dxvk"
    _graphics(base, "v2.6.2", "d3d11.dll")
    _graphics(base, "v2.14", "d3d11.dll")
    (base / "empty").mkdir()
    versions = R.graphics_versions("dxvk")
    assert [v.name for v in versions] == ["v2.14", "v2.6.2"]
    assert versions[0].complete()
    assert R.pick_graphics("dxvk") is not None
    assert R.pick_graphics("vkd3d") is None


def test_graphics_version_files_and_extra_dirs(xdg_env, tmp_path):
    base = tmp_path / "vkd3d"
    root = _graphics(base, "v2.13", "d3d12.dll")
    (root / "x64" / "d3d12core.dll").write_text("dll")
    (root / "x64" / "notes.txt").write_text("ignore me")
    versions = R.graphics_versions("vkd3d", str(base))
    assert [v.name for v in versions] == ["v2.13"]
    files = versions[0].files()
    assert {(src.name, target) for src, target in files} == {
        ("d3d12.dll", "system32"),
        ("d3d12core.dll", "system32"),
        ("d3d12.dll", "syswow64"),
    }


def test_graphics_direct_version_dir(xdg_env, tmp_path):
    root = _graphics(tmp_path / "single", "v2.6.2", "d3d11.dll")
    versions = R.graphics_versions("dxvk", str(root))
    assert [v.name for v in versions] == ["v2.6.2"]
    assert versions[0].complete()
