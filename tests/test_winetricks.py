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
