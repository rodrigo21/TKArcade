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
