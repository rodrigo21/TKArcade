"""Runtime discovery: Proton installs, Wine binaries and graphics layers."""

from tkarcade import runtimes as R


def _install(base, name, marker="proton"):
    path = base / name
    path.mkdir(parents=True)
    (path / marker).write_text("x\n")
    return path


def _register(kind, base):
    from tkarcade import config as C

    assert C.add_external_dir(kind, str(base)) == ""
    return base


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


def test_proton_installs_require_the_launcher(xdg_env):
    tools = xdg_env["home"] / ".local/share/Steam/compatibilitytools.d"
    _install(tools, "GE-Proton9-1")
    _install(tools, "Proton EasyAntiCheat Runtime", marker="version")
    assert [i.name for i in R.proton_installs()] == ["GE-Proton9-1"]


def test_proton_installs_system_first_then_libraries(xdg_env, tmp_path, monkeypatch):
    system = tmp_path / "usr-share-steam"
    _install(system / "compatibilitytools.d", "proton-cachyos-slr")
    monkeypatch.setattr(R, "SYSTEM_STEAM_ROOT", system)
    library = tmp_path / "library2"
    tools = library / "steamapps" / "common"
    _install(tools, "Proton - Experimental")
    _install(library / "steamapps" / "compatibilitytools.d", "GE-Proton10-1")
    root = xdg_env["home"] / ".local/share/Steam"
    (root / "steamapps").mkdir(parents=True, exist_ok=True)
    (root / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{library}"\n\t}}\n}}\n'
    )
    assert [i.name for i in R.proton_installs()] == [
        "proton-cachyos-slr",
        "GE-Proton10-1",
        "Proton - Experimental",
    ]


def test_pick_proton_prefers_the_name_else_the_first(xdg_env):
    tools = xdg_env["home"] / ".local/share/Steam/compatibilitytools.d"
    _install(tools, "GE-Proton9-1")
    _install(tools, "DW-Proton Latest")
    installs = R.proton_installs()
    assert R.pick_proton(installs, "ge-proton9-1").name == "GE-Proton9-1"
    assert R.pick_proton(installs, "gone").name == installs[0].name
    assert R.pick_proton(installs, "").name == installs[0].name
    assert R.pick_proton([], "x") is None


def test_find_proton_by_name_and_path(xdg_env, tmp_path):
    tools = xdg_env["home"] / ".local/share/Steam/compatibilitytools.d"
    path = _install(tools, "GE-Proton9-1")
    assert R.find_proton("ge-proton9-1").path == path.resolve()
    assert R.find_proton(path).name == "GE-Proton9-1"
    assert R.find_proton("nope") is None
    assert R.find_proton("") is None
    assert R.find_proton(tmp_path) is None  # a directory without the launcher


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
    base = xdg_env["data"] / "dxvk"
    _graphics(base, "v2.6.2", "d3d11.dll")
    _graphics(base, "v2.14", "d3d11.dll")
    (base / "empty").mkdir()
    _register("dxvk", base)
    versions = R.graphics_versions("dxvk")
    assert [v.name for v in versions] == ["v2.14", "v2.6.2"]
    assert versions[0].complete()
    assert R.pick_graphics("dxvk").name == "v2.14"
    assert R.pick_graphics("dxvk", "v2.6.2").name == "v2.6.2"
    assert R.pick_graphics("dxvk", "v9.9") is None
    assert R.pick_graphics("vkd3d") is None


def test_graphics_versions_include_managed_dir(xdg_env):
    managed = xdg_env["data"] / "tkarcade" / "runtimes" / "dxvk"
    _graphics(managed, "dxvk-2.7.1", "d3d11.dll")
    extra = xdg_env["data"] / "dxvk"
    _graphics(extra, "dxvk-2.14.0", "d3d11.dll")
    assert [v.name for v in R.graphics_versions("dxvk")] == ["dxvk-2.7.1"]
    _register("dxvk", extra)
    assert [v.name for v in R.graphics_versions("dxvk")] == ["dxvk-2.14.0", "dxvk-2.7.1"]


def test_graphics_versions_managed_wins_on_equal_names(xdg_env, tmp_path):
    managed = xdg_env["data"] / "tkarcade" / "runtimes" / "dxvk"
    configured = tmp_path / "dxvk"
    _graphics(managed, "dxvk-2.7.1", "d3d11.dll")
    _graphics(configured, "dxvk-2.7.1", "d3d11.dll")
    _register("dxvk", configured)
    versions = [v for v in R.graphics_versions("dxvk") if v.name == "dxvk-2.7.1"]
    assert [v.root for v in versions] == [managed / "dxvk-2.7.1", configured / "dxvk-2.7.1"]


def test_graphics_versions_ignore_unconfigured_lutris_dir(xdg_env):
    base = xdg_env["data"] / "lutris/runtime/dxvk"
    _graphics(base, "v2.6.2", "d3d11.dll")
    assert R.graphics_versions("dxvk") == []


def test_graphics_version_files_and_extra_dirs(xdg_env, tmp_path):
    base = tmp_path / "vkd3d"
    root = _graphics(base, "v2.13", "d3d12.dll")
    (root / "x64" / "d3d12core.dll").write_text("dll")
    (root / "x64" / "notes.txt").write_text("ignore me")
    _register("vkd3d", base)
    versions = R.graphics_versions("vkd3d")
    assert [v.name for v in versions] == ["v2.13"]
    files = versions[0].files()
    assert {(src.name, target) for src, target in files} == {
        ("d3d12.dll", "system32"),
        ("d3d12core.dll", "system32"),
        ("d3d12.dll", "syswow64"),
    }


def test_graphics_direct_version_dir(xdg_env, tmp_path):
    root = _graphics(tmp_path / "single", "v2.6.2", "d3d11.dll")
    _register("dxvk", root)
    versions = R.graphics_versions("dxvk")
    assert [v.name for v in versions] == ["v2.6.2"]
    assert versions[0].complete()


def test_wine_binary_resolves_managed_names(fake_bin):
    from tkarcade import config as C

    first = fake_bin("wine")
    second = fake_bin("wine-cachyos")
    versions = C.format_wine_versions([("wine", str(first)), ("cachy", str(second))])
    assert R.wine_binary("cachy", versions) == str(second)
    assert R.wine_binary("CACHY", versions) == str(second)
    assert R.wine_binary("wine", versions) == str(first)
    assert R.wine_binary("", versions) == str(first)
    # Unknown names and legacy paths keep the old behaviour.
    assert R.wine_binary("gone", versions) == ""
    assert R.wine_binary(str(second), versions) == str(second)


def test_wine_versions_report_missing_paths():
    from tkarcade import config as C

    versions = C.format_wine_versions([("gone", "/does/not/exist")])
    rows = R.wine_versions(versions)
    assert [(r.name, r.path, r.ok) for r in rows] == [("gone", "/does/not/exist", False)]
    assert R.wine_binary("gone", versions) == ""


def test_graphics_repo_presets():
    assert R.graphics_repo("") == ""
    assert R.graphics_repo("official") == ""
    assert R.graphics_repo("sarek") == "zeyadadev/DXVK-Sarek"
    assert R.graphics_repo("gplasync").startswith("Waim908/")
    assert R.graphics_repo("custom:Owner/Repo") == "Owner/Repo"
