"""Local winetricks: verbs run against a Wine/umu prefix (stdlib only)."""

from types import SimpleNamespace

from tkarcade import winetricks as W


def _prefix(base):
    prefix = base / "prefix"
    (prefix / "drive_c").mkdir(parents=True)
    return prefix


def _calls(base):
    return base / "calls.log"


def test_runs_and_skips_repeat(xdg_env, fake_bin, tmp_path):
    calls = _calls(tmp_path)
    fake_bin(
        "winetricks",
        f'#!/bin/sh\necho "$WINEPREFIX|$WINE|$@" >> "{calls}"\nexit 0\n',
    )
    wine = fake_bin("wine")
    prefix = _prefix(tmp_path)
    assert (
        W.run_local("local-doom", prefix, "wine", str(wine), None, ["dotnet48", "vcrun2022"]) == []
    )
    assert f"{prefix}|{wine}|-q dotnet48 vcrun2022" in calls.read_text()
    calls.unlink()
    assert (
        W.run_local("local-doom", prefix, "wine", str(wine), None, ["vcrun2022", "dotnet48"]) == []
    )
    assert not calls.exists()  # recorded prefix + verbs skip the rerun
    other = _prefix(tmp_path / "other")
    assert W.run_local("local-doom", other, "wine", str(wine), None, ["dotnet48"]) == []
    assert calls.exists()  # another prefix reruns


def test_umu_uses_the_proton_wine(xdg_env, fake_bin, tmp_path):
    calls = _calls(tmp_path)
    fake_bin(
        "winetricks",
        f'#!/bin/sh\necho "$WINE" >> "{calls}"\nexit 0\n',
    )
    proton = tmp_path / "GE-Proton10-1"
    wine = proton / "files" / "bin" / "wine"
    wine.parent.mkdir(parents=True)
    wine.write_text("#!/bin/sh\nexit 0\n")
    wine.chmod(0o755)
    prefix = _prefix(tmp_path)
    install = SimpleNamespace(path=proton)
    assert W.run_local("local-doom", prefix, "umu", "", install, ["dotnet48"]) == []
    assert calls.read_text().strip() == str(wine)


def test_skips_without_prefix_binary_or_verbs(xdg_env, fake_bin, tmp_path, monkeypatch):
    fake_bin("winetricks")
    wine = fake_bin("wine")
    assert W.run_local("local-doom", tmp_path / "missing", "wine", str(wine), None, ["dotnet48"])[
        0
    ].endswith("does not exist yet; launch the game once to create the prefix")
    prefix = _prefix(tmp_path)
    assert "wine binary" in W.run_local("local-doom", prefix, "wine", "", None, ["dotnet48"])[0]
    assert (
        "files/bin/wine"
        in W.run_local(
            "local-doom", prefix, "umu", "", SimpleNamespace(path=tmp_path), ["dotnet48"]
        )[0]
    )
    assert W.run_local("local-doom", prefix, "wine", str(wine), None, []) == []
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert (
        "winetricks not found"
        in W.run_local("local-doom", prefix, "wine", str(wine), None, ["dotnet48"])[0]
    )


def test_failure_warns_and_does_not_record(xdg_env, fake_bin, tmp_path):
    fake_bin("winetricks", '#!/bin/sh\necho "no such verb" >&2\nexit 1\n')
    wine = fake_bin("wine")
    prefix = _prefix(tmp_path)
    warnings = W.run_local("local-doom", prefix, "wine", str(wine), None, ["bogus"])
    assert warnings and "winetricks exit 1" in warnings[0]
    assert not W.state_path("local-doom").is_file()


def test_installed_verbs_parse_the_log(tmp_path):
    prefix = _prefix(tmp_path)
    (prefix / "winetricks.log").write_text(
        "corefonts vcrun2022\ncorefonts\n-q dotnet48\nw_workaround_wine_bug-1234\n",
        encoding="utf-8",
    )
    # The whole verb list of a run lands on one line: tokenize, keep the
    # order, drop options and the internal workaround entries.
    assert W.installed_verbs(prefix) == ["corefonts", "vcrun2022", "dotnet48"]


def test_installed_verbs_read_a_compatdata_container(tmp_path):
    container = tmp_path / "compatdata" / "620"
    (container / "pfx").mkdir(parents=True)
    (container / "pfx" / "winetricks.log").write_text("dotnet48\n", encoding="utf-8")
    assert W.installed_verbs(container) == ["dotnet48"]
    assert W.installed_verbs(tmp_path / "missing") == []


def test_catalog_parses_list_all_and_caches(fake_bin, tmp_path):
    calls = _calls(tmp_path)
    fake_bin(
        "winetricks",
        "#!/bin/sh\n"
        f'echo "$@" >> "{calls}"\n'
        "cat <<LIST\n"
        "===== apps =====\n"
        "corefonts                 Microsoft TrueType core fonts [para download]\n"
        "dotnet48                  Microsoft .NET Framework 4.8\n"
        "\n"
        "===== benchmarks =====\n"
        "win7                      Changes the Windows version to Windows 7\n"
        "LIST\n",
    )
    W.clear_catalog_cache()
    rows = W.list_all()
    assert [(r["verb"], r["category"]) for r in rows] == [
        ("corefonts", "apps"),
        ("dotnet48", "apps"),
        ("win7", "benchmarks"),
    ]
    assert rows[0]["description"].startswith("Microsoft TrueType")
    assert calls.read_text().strip() == "list-all"
    assert W.catalog_ready() is True
    assert W.list_all() == rows  # cached: one run only
    assert calls.read_text().strip() == "list-all"
    assert W.parse_catalog("") == []


def test_catalog_without_the_binary_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    W.clear_catalog_cache()
    assert W.list_all() == []
    assert W.catalog_ready() is True  # nothing to spawn, answers at once


def test_local_gui_argv_env_and_refusals(xdg_env, fake_bin, tmp_path, monkeypatch):
    exe = fake_bin("winetricks")
    wine = fake_bin("wine")
    prefix = _prefix(tmp_path)
    argv, env, message = W.local_gui(prefix, "wine", str(wine), None)
    assert message == ""
    assert argv == [str(exe), "--gui"]
    assert env == {"WINEPREFIX": str(prefix), "WINE": str(wine)}
    assert "Does Not Exist Yet" in W.local_gui(tmp_path / "missing", "wine", str(wine), None)[2]
    assert "No Wine Binary" in W.local_gui(prefix, "wine", "", None)[2]
    assert "files/bin/wine" in W.local_gui(prefix, "umu", "", SimpleNamespace(path=tmp_path))[2]
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert "Winetricks Was Not Found" in W.local_gui(prefix, "wine", str(wine), None)[2]
