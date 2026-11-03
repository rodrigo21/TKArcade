def test_is_steam_id(xdg_env):
    from tkarcade import steam as S

    assert S.is_steam_id("213") is True
    assert S.is_steam_id("  213  ") is True
    assert S.is_steam_id("steam-213") is True
    assert S.is_steam_id("local-doom") is False
    assert S.is_steam_id("steam-doom") is False
    assert S.is_steam_id("") is False


def test_origin_and_steam_appid():
    from tkarcade import steam as S

    assert S.origin("steam-213") == "steam"
    assert S.origin("213") == "steam"  # legacy bare digits
    assert S.origin("local-doom") == "local"
    assert S.origin("") == "local"
    assert S.steam_appid("steam-213") == "213"
    assert S.steam_appid("213") == "213"
    assert S.steam_appid("local-doom") == ""
    assert S.steam_appid("steam-doom") == ""


def test_canonical_ids(xdg_env):
    from tkarcade import steam as S

    assert S.canonical_id("213") == "steam-213"
    assert S.canonical_id("steam-213") == "steam-213"
    assert S.canonical_id("local-doom") == "local-doom"
    assert S.canonical_new_id("213") == "steam-213"
    assert S.canonical_new_id("steam-213") == "steam-213"
    assert S.canonical_new_id("local-doom") == "local-doom"
    assert S.canonical_new_id("steam-foo") == "steam-foo"
    assert S.canonical_new_id("Doom - Ep. 1") == "local-doom-ep-1"


def test_local_names(xdg_env):
    from tkarcade import config as C
    from tkarcade import steam as S

    named = C.GameConfig()
    named.general.appid = "local-doom"
    named.general.name = "Doom"
    C.save(named)
    anon = C.GameConfig()
    anon.general.appid = "local-x"
    C.save(anon)
    steam_cfg = C.GameConfig()
    steam_cfg.general.appid = "213"
    C.save(steam_cfg)
    assert S.local_names() == {"local-doom": "Doom", "local-x": "local-x"}


def _write_lib(root, rel, legacy=False):
    lib = root / rel
    (lib / "steamapps").mkdir(parents=True)
    return lib


def test_libraryfolders_unparseable_returns_empty(xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S

    monkeypatch.setattr(S, "loads_kv1", lambda text: None)
    lib = _write_lib(tmp_path, "mnt/second")
    lf = tmp_path / "libraryfolders.vdf"
    lf.write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path" "' + str(lib) + '"\n\t}\n}\n',
        encoding="utf-8",
    )
    assert S._parse_libraryfolders_vdf(lf) == []


def test_libraryfolders_legacy_layout(xdg_env, tmp_path):
    from tkarcade import steam as S

    lib = _write_lib(tmp_path, "mnt/legacy")
    lf = tmp_path / "libraryfolders.vdf"
    lf.write_text(
        '"LibraryFolders"\n{\n\t"1"\t\t"' + str(lib) + '"\n}\n',
        encoding="utf-8",
    )
    assert S._parse_libraryfolders_vdf(lf) == [lib]


def _write_shortcuts(root, uid, appid, exe):
    import vdf

    confdir = root / "userdata" / uid / "config"
    confdir.mkdir(parents=True)
    signed = appid - 2**32 if appid >= 2**31 else appid
    entry = {"appid": signed, "AppName": "Shortcut", "Exe": f'"{exe}"'}
    with (confdir / "shortcuts.vdf").open("wb") as handle:
        vdf.binary_dump({"shortcuts": {"0": entry}}, handle)


def test_shortcut_exe_maps_unsigned_id(xdg_env, monkeypatch, tmp_path):
    from tkarcade import steam as S

    root = tmp_path / "steam"
    _write_shortcuts(root, "u1", 3_000_000_000, "/games/My Game/run.sh")
    monkeypatch.setenv("STEAM_ROOT", str(root))
    assert S.shortcut_exe("3000000000") == "/games/My Game/run.sh"
    assert S.shortcut_exe("steam-3000000000") == "/games/My Game/run.sh"
    assert S.shortcut_exe("3000000001") == ""
    assert S.shortcut_exe("local-doom") == ""


def test_shortcut_exe_without_userdata(xdg_env, monkeypatch, tmp_path):
    from tkarcade import steam as S

    monkeypatch.setenv("STEAM_ROOT", str(tmp_path / "empty"))
    assert S.shortcut_exe("42") == ""
