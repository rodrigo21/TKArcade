def test_is_steam_id(xdg_env):
    from tkarcade import steam as S

    assert S.is_steam_id("213") is True
    assert S.is_steam_id("  213  ") is True
    assert S.is_steam_id("local-doom") is False
    assert S.is_steam_id("") is False


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


def test_libraryfolders_modern_fallback(xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S

    monkeypatch.setattr(S, "loads_kv1", lambda text: None)  # stdlib-only path
    lib = _write_lib(tmp_path, "mnt/second")
    lf = tmp_path / "libraryfolders.vdf"
    lf.write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path" "' + str(lib) + '"\n\t}\n}\n',
        encoding="utf-8",
    )
    assert S._parse_libraryfolders_vdf(lf) == [lib]


def test_libraryfolders_legacy_layout(xdg_env, tmp_path, monkeypatch):
    from tkarcade import steam as S

    lib = _write_lib(tmp_path, "mnt/legacy")
    lf = tmp_path / "libraryfolders.vdf"
    lf.write_text(
        '"LibraryFolders"\n{\n\t"1"\t\t"' + str(lib) + '"\n}\n',
        encoding="utf-8",
    )
    # With vdf available the legacy root key and bare-string values resolve.
    assert S._parse_libraryfolders_vdf(lf) == [lib]
    # Without vdf the numeric-key regex fallback covers the same file.
    monkeypatch.setattr(S, "loads_kv1", lambda text: None)
    assert S._parse_libraryfolders_vdf(lf) == [lib]
