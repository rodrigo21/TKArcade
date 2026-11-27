"""Artwork resolution and SteamGridDB fetching (network stubbed)."""

import json

from tkarcade import artwork as art


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size: int = -1):
        return self._payload if size < 0 else self._payload[:size]


def _stub(monkeypatch, routes):
    def fake_open(url_or_request, timeout=15):
        url = url_or_request.full_url if hasattr(url_or_request, "full_url") else url_or_request
        for marker, payload in routes:
            if marker in url:
                if isinstance(payload, Exception):
                    raise payload
                body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                return _Resp(body)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_open)


def _img(tag: str = "") -> bytes:
    """A minimal PNG body: the download path checks the magic bytes."""
    return b"\x89PNG\r\n\x1a\n" + tag.encode()


def test_steam_canonical_id_uses_numeric_cache_and_api(monkeypatch, xdg_env):
    seen = []

    def fake_open(url_or_request, timeout=15):
        url = url_or_request.full_url if hasattr(url_or_request, "full_url") else url_or_request
        seen.append(url)
        body = {"response": {"apps": [{"appid": 480, "name": "Canon", "icon": ""}]}}
        return _Resp(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert art.steam_app("steam-480")["name"] == "Canon"
    assert "appids[0]=480" in seen[0]
    assert art.steam_app("local-doom") is None
    # The cache belongs to the numeric AppID, so both ID forms share it.
    assert art.grid_path("steam-480") == art.grid_path("480")
    assert art.manual_dir("steam-480") == art.manual_dir("480")
    assert art.grid_path("steam-480") != art.grid_path("local-doom")


def test_resolve_prefers_grid(xdg_env, tmp_path):
    from tkarcade import steam as S

    grid = art.grid_path("81")
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"png")
    assert art.resolve_icon("81") == grid
    assert S.find_game_icon("81") is None


def test_fetch_missing_full_chain(monkeypatch, xdg_env):
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": [{"id": 123}]}),
            ("grids/game", {"data": [_grid_entry("https://cdn/x.png", 600, 900)]}),
            ("cdn/x.png", _img("imagedata")),
        ],
    )
    path = art.fetch_missing("82", "KEY")
    assert path is not None and path.read_bytes() == _img("imagedata")
    # second call hits the on-disk grid, no network needed
    _stub(monkeypatch, [])
    assert art.fetch_missing("82", "KEY") == path


def test_fetch_failures_are_none(monkeypatch, xdg_env):
    import urllib.error

    assert art.fetch_missing("83", "") is None
    assert art.fetch_missing("abc", "KEY") is None
    _stub(monkeypatch, [("games/steam", {"data": []})])
    assert art.fetch_missing("84", "KEY") is None
    _stub(monkeypatch, [("games/steam", urllib.error.URLError("down"))])
    assert art.fetch_missing("85", "KEY") is None


def test_thumb_requires_https(monkeypatch, xdg_env):
    games = {"data": [{"id": 7}]}
    grids = {"data": [{"thumb": "file:///etc/passwd"}]}
    _stub(monkeypatch, [("games/steam", games), ("grids/game", grids)])
    assert art.fetch_missing("82", "key") is None
    assert not art.grid_path("82").exists()


def test_fetch_dict_shaped_data(monkeypatch, xdg_env):
    games = {"data": {"id": 9, "name": "Dict Game"}}
    grids = {"data": [{"thumb": "https://cdn.test/g.png", "width": 600, "height": 900}]}
    _stub(monkeypatch, [("games/steam", games), ("grids/game", grids), ("cdn.test", _img("PNG"))])
    path = art.fetch_missing("83", "key")
    assert path is not None and path.is_file()


def _grid_entry(thumb, width, height):
    return {"thumb": thumb, "width": width, "height": height, "mime": "image/png"}


def test_fetch_sgdb_picks_the_shape_per_kind(monkeypatch, xdg_env):
    """Square goes to icon, portrait to cover, wide to banner."""
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": [{"id": 55}]}),
            (
                "grids/game",
                {
                    "data": [
                        _grid_entry("https://cdn/tall.png", 600, 900),
                        _grid_entry("https://cdn/wide.jpg", 920, 430),
                    ]
                },
            ),
            ("heroes/game", {"data": [_grid_entry("https://cdn/hero.jpg", 3840, 1240)]}),
            ("icons/game", {"data": [_grid_entry("https://cdn/square.png", 512, 512)]}),
            ("cdn/tall.png", _img("T")),
            ("cdn/hero.jpg", _img("W")),
            ("cdn/square.png", _img("S")),
        ],
    )
    out, error = art.fetch_sgdb("86", "KEY")
    assert error == ""
    assert out["icon"].read_bytes() == _img("S")
    assert out["cover"].read_bytes() == _img("T")
    assert out["banner"].read_bytes() == _img("W")
    assert out["icon"].name == "steam-86-icon.png"
    assert out["cover"].name == "steam-86.png"
    assert out["banner"].name == "steam-86-banner.jpg"
    # The backdrop has no provider asset of its own: no second download.
    assert "background" not in out


def test_fetch_sgdb_prefers_official_style(monkeypatch, xdg_env):
    """Valve's own entries (style official) beat the score order."""
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": [{"id": 57}]}),
            (
                "grids/game",
                {
                    "data": [
                        {**_grid_entry("https://cdn/pop.png", 600, 900), "score": 90},
                        {
                            **_grid_entry("https://cdn/valve.png", 600, 900),
                            "score": 1,
                            "style": "official",
                        },
                    ]
                },
            ),
            ("cdn/valve.png", _img("V")),
        ],
    )
    out, _error = art.fetch_sgdb("88", "KEY", ("cover",))
    assert out["cover"].read_bytes() == _img("V")
    assert art.provider_for("88", "cover") == "sgdb"


def test_fetch_sgdb_skips_cached_and_reshapes_without_dimensions(monkeypatch, xdg_env):
    """A cached kind costs no network; a shapeless answer still serves."""
    cached = art.grid_path("87", "cover")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"C")
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": [{"id": 56}]}),
            ("icons/game", {"data": [{"thumb": "https://cdn/any.png", "mime": "image/png"}]}),
            ("cdn/any.png", _img("ANY")),
        ],
    )
    out, _error = art.fetch_sgdb("87", "KEY", ("icon", "cover"))
    assert "cover" not in out
    assert out["icon"].read_bytes() == _img("ANY")
    assert art.fetch_sgdb("87", "", ("banner",)) == ({}, "no-key")


def test_sgdb_icons_skip_the_ico_submissions(monkeypatch, xdg_env):
    """Qt cannot read the .ico entries: they must not be picked."""
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": [{"id": 58}]}),
            (
                "icons/game",
                {
                    "data": [
                        {
                            "thumb": "https://cdn/i.ico",
                            "mime": "image/vnd.microsoft.icon",
                            "style": "official",
                        },
                        {**_grid_entry("https://cdn/i.png", 256, 256), "style": "custom"},
                    ]
                },
            ),
            ("cdn/i.png", _img("P")),
        ],
    )
    out, _error = art.fetch_sgdb("89", "KEY", ("icon",))
    assert out["icon"].read_bytes() == _img("P")


def test_cached_icon_beats_the_cached_cover(xdg_env):
    """A fetched square icon must win over the cover sitting next to it."""
    icon = art.grid_path("480", "icon")
    cover = art.grid_path("480", "cover")
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"I")
    cover.write_bytes(b"C")
    assert art.resolve("480", "icon") == (icon, "cache")
    assert art.resolve("480", "cover") == (cover, "cache")


def test_source_appid_wins_over_the_game_own_art(xdg_env, tmp_path):
    """The typed Artwork Source AppID overrides the game's own download."""
    own = art.grid_path("local-doom", "cover")
    own.parent.mkdir(parents=True)
    own.write_bytes(b"O")
    shared = art.grid_path("480", "cover")
    shared.write_bytes(_img("S"))
    assert art.resolve("local-doom", "cover", "480") == (shared, "appid-cache")
    assert art.resolve("local-doom", "cover") == (own, "cache")
    # The game's own manual slot still wins: it is the most specific
    # choice the user can make.
    manual = art.store_manual("local-doom", "icon", str(_image(tmp_path, "m.png")))
    assert art.resolve("local-doom", "icon", "480") == (manual, "manual")


def test_resolve_manual_slot_beats_everything(xdg_env, tmp_path):
    manual = art.store_manual("81", "icon", str(_image(tmp_path, "m.png")))
    assert manual is not None
    assert art.resolve("81", "icon") == (manual, "manual")


def test_background_defaults_to_the_banner(xdg_env):
    """No provider serves a separate wide asset: the banner answers."""
    banner = art.grid_path("480", "banner")
    banner.parent.mkdir(parents=True)
    banner.write_bytes(b"B")
    assert art.resolve("480", "background") == (banner, "cache")
    # Its own slot is a separate cache file and wins once filled.
    own = art.grid_path("480", "background")
    assert own.name == "steam-480-background.png"
    assert own not in (banner, art.grid_path("480", "cover"))
    own.write_bytes(b"G")
    assert art.resolve("480", "background") == (own, "cache")
    assert own in art.cache_files("480")


def test_background_manual_slot_is_cleared_alone(xdg_env, tmp_path):
    manual = art.store_manual("81", "background", str(_image(tmp_path, "b.png")))
    assert manual is not None and manual.name == "background.png"
    assert art.resolve("81", "background") == (manual, "manual")
    assert art.clear_manual("81", "background")
    assert art.manual_path("81", "background") is None


def _image(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"IMG")
    return path


APP_INFO = "https://api.steampowered.com/ICommunityService/GetApps/v1/"


def _steam_apps(name, icon="h"):
    return {"response": {"apps": [{"appid": 1, "name": name, "icon": icon}]}}


def test_fetch_official_needs_no_key(monkeypatch, xdg_env):
    """Official Steam art downloads with no API key at all."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("library_hero.jpg", _img("HERO")),
        ],
    )
    result = art.fetch_best("620", "steam", "")
    assert result["valid"] is True
    assert result["name"] == "Portal 2"
    assert result["provider"] == "steam"
    assert result["error"] == ""
    # The client .ico is unwrapped to its 256x256 PNG frame: Qt would
    # otherwise read the 16x16 one, and the file keeps the right suffix.
    assert result["art"]["icon"].name == "steam-620-icon.png"
    assert result["art"]["icon"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert result["art"]["cover"].name == "steam-620.jpg"
    assert result["art"]["banner"].name == "steam-620-banner.jpg"
    assert art.provider_for("620", "cover") == "steam"
    assert art.resolve("620", "cover")[1] == "cache"


def test_official_icon_falls_back_to_the_small_jpg(monkeypatch, xdg_env):
    """Some apps ship no client .ico: the 32x32 jpg is the official icon."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Le Mans Ultimate", "def")),
            ("def.ico", urllib_error_404()),
            ("def.jpg", _img("SMALL")),
        ],
    )
    out = art.fetch_official("2399420", ("icon",))
    assert out["icon"].read_bytes() == _img("SMALL")


def test_steam_client_icon_wins_over_the_sgdb_promo(monkeypatch, xdg_env):
    """The real 32x32 client icon beats a SteamGridDB 'official' promo."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Le Mans Ultimate", "def")),
            ("def.ico", urllib_error_404()),
            ("def.jpg", _img("SMALL")),
            ("games/steam", {"data": [{"id": 5406300}]}),
            (
                "icons/game",
                {
                    "data": [
                        {
                            **_grid_entry("https://cdn/big.png", 256, 256),
                            "style": "official",
                        }
                    ]
                },
            ),
            ("cdn/big.png", _img("BIG")),
        ],
    )
    result = art.fetch_best("2399420", "steam", "KEY", ("icon",))
    assert result["art"]["icon"].read_bytes() == _img("SMALL")
    assert result["provider"] == "steam"


def test_sgdb_icon_fills_when_steam_has_none(monkeypatch, xdg_env):
    """Only a real absence of Steam art opens the door to SGDB icons."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("No Icon App", "")),
            ("header.jpg", urllib_error_404()),
            ("games/steam", {"data": [{"id": 78}]}),
            (
                "icons/game",
                {
                    "data": [
                        {
                            **_grid_entry("https://cdn/big.png", 256, 256),
                            "style": "official",
                        }
                    ]
                },
            ),
            ("cdn/big.png", _img("BIG")),
        ],
    )
    result = art.fetch_best("2399420", "steam", "KEY", ("icon",))
    assert result["art"]["icon"].read_bytes() == _img("BIG")
    assert result["provider"] == "sgdb"


def test_old_sgdb_icon_is_dropped_once(monkeypatch, xdg_env):
    """An icon from the old SGDB-first chain is replaced by the Steam one."""
    icon = art.grid_path("2399420", "icon")
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"PROMO")
    art.manifest_path("2399420").write_text(
        '{"icon": {"provider": "sgdb", "appid": "2399420"}}', encoding="utf-8"
    )
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Le Mans Ultimate", "def")),
            ("def.ico", urllib_error_404()),
            ("def.jpg", _img("SMALL")),
        ],
    )
    result = art.fetch_best("2399420", "steam", "", ("icon",))
    assert result["art"]["icon"].read_bytes() == _img("SMALL")
    assert art.read_manifest("2399420").get("icon_chain") == art.ICON_CHAIN
    # A post-fix SGDB fallback carries the marker and is left alone.
    art.clear_fetched("2399420")
    art.manifest_path("2399420").write_text(
        '{"icon": {"provider": "sgdb", "appid": "2399420"}, "icon_chain": 2}',
        encoding="utf-8",
    )
    icon.write_bytes(b"KEPT")
    art._drop_stale_sgdb_icon("2399420")
    assert icon.read_bytes() == b"KEPT"


def test_icon_chain_falls_back_to_the_small_jpg_without_a_key(monkeypatch, xdg_env):
    """No SteamGridDB key: the official 32x32 is the last resort."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Le Mans Ultimate", "def")),
            ("def.ico", urllib_error_404()),
            ("def.jpg", _img("SMALL")),
        ],
    )
    result = art.fetch_best("2399420", "steam", "", ("icon",))
    assert result["art"]["icon"].read_bytes() == _img("SMALL")
    assert result["provider"] == "steam"


def test_name_search_matches_exactly_and_stores_the_id(monkeypatch, xdg_env):
    """A local game resolves its name to one SteamGridDB entry, once."""
    _stub(
        monkeypatch,
        [
            (
                "search/autocomplete",
                {
                    "data": [
                        {"id": 99, "name": "Doom Eternal", "types": ["steam"]},
                        {"id": 7, "name": "Doom", "types": ["steam"]},
                    ]
                },
            ),
            ("games/steam", {"data": []}),
            ("grids/game", {"data": [_grid_entry("https://cdn/cover.png", 600, 900)]}),
            ("cdn/cover.png", _img("COVER")),
        ],
    )
    result = art.fetch_best("local-doom", "steam", "KEY", ("cover",), names=("Doom",))
    assert result["game_id"] == "7"
    assert result["art"]["cover"].read_bytes() == _img("COVER")
    assert result["provider"] == "sgdb"
    assert art.stored_sgdb_id("local-doom") == "7"
    # A later fetch reuses the stored id and never searches again.
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": []}),
            ("grids/game", {"data": [_grid_entry("https://cdn/cover2.png", 600, 900)]}),
            ("cdn/cover2.png", _img("NEW")),
        ],
    )
    again = art.fetch_best("local-doom", "steam", "KEY", ("cover",), force=True)
    assert again["game_id"] == "7"
    assert again["art"]["cover"].read_bytes() == _img("NEW")


def test_name_search_returns_candidates_when_nothing_matches(monkeypatch, xdg_env):
    """No exact name: the rows come back so the dialog can ask."""
    _stub(
        monkeypatch,
        [
            (
                "search/autocomplete",
                {"data": [{"id": 5, "name": "Doom 3", "types": ["steam"]}]},
            )
        ],
    )
    result = art.fetch_best("local-doom", "steam", "KEY", ("cover",), names=("Doom",))
    assert result["art"] == {}
    assert result["error"] == "no-match"
    assert result["candidates"] == [{"id": "5", "name": "Doom 3", "provider": "sgdb"}]
    assert art.stored_sgdb_id("local-doom") == ""


def test_name_search_needs_a_key(monkeypatch, xdg_env):
    assert (
        art.fetch_best("local-doom", "steam", "", ("cover",), names=("Doom",))["error"] == "no-key"
    )


def test_clear_keeps_the_sgdb_choice(monkeypatch, xdg_env):
    """Clear removes the files but remembers which game the name resolved to."""
    _stub(
        monkeypatch,
        [
            ("search/autocomplete", {"data": [{"id": 7, "name": "Doom"}]}),
            ("games/steam", {"data": []}),
            ("grids/game", {"data": [_grid_entry("https://cdn/cover.png", 600, 900)]}),
            ("cdn/cover.png", _img("COVER")),
        ],
    )
    art.fetch_best("local-doom", "steam", "KEY", ("cover",), names=("Doom",))
    art.clear_fetched("local-doom")
    assert art.is_cleared("local-doom") is True
    assert art.stored_sgdb_id("local-doom") == "7"


def test_normalize_name_ignores_case_and_accents():
    assert art.normalize_name("  Pokémon  [v1.2] ") == "pokemon v1 2"
    assert art.normalize_name("Doom") == art.normalize_name("doom")


def urllib_error_404():
    import urllib.error

    return urllib.error.HTTPError("u", 404, "nf", None, None)


def test_invalid_appid_is_reported_not_silent(monkeypatch, xdg_env):
    """A SteamGridDB id pasted as AppID has no Steam name: say so."""
    _stub(monkeypatch, [(APP_INFO, {"response": {"apps": [{"appid": 5406300}]}})])
    result = art.fetch_best("5406300", "steam", "KEY")
    assert result["valid"] is False
    assert result["name"] == ""
    assert result["art"] == {}
    assert result["error"] == "not-found"


def test_cloudflare_block_is_reported(monkeypatch, xdg_env):
    """403 (no browser signature) must surface, not vanish into debug."""
    import urllib.error

    def fake_open(url_or_request, timeout=15):
        raise urllib.error.HTTPError("u", 403, "Forbidden", None, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert art._get("https://www.steamgriddb.com/api/v2/x", "KEY") == (None, "blocked")


def test_sgdb_provider_first_when_asked(monkeypatch, xdg_env):
    """Preference sgdb: community art wins, official only fills the gaps."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("games/steam", {"data": [{"id": 9}]}),
            ("grids/game", {"data": [_grid_entry("https://cdn/community.png", 600, 900)]}),
            ("cdn/community.png", _img("COMMUNITY")),
            ("library_600x900_2x.jpg", _img("OFFICIAL")),
            ("library_hero.jpg", _img("HERO")),
            ("abc.ico", _img("ICO")),
        ],
    )
    result = art.fetch_best("620", "sgdb", "KEY", ("cover", "banner"))
    assert result["provider"] == "sgdb"
    assert result["art"]["cover"].read_bytes() == _img("COMMUNITY")
    assert result["art"]["banner"].read_bytes() == _img("HERO")
    assert art.provider_for("620", "cover") == "sgdb"
    assert art.provider_for("620", "banner") == "steam"


def test_force_redownloads_the_cached_kind(monkeypatch, xdg_env):
    """Fetch Artwork is explicit: it refreshes even a cached kind."""
    cached = art.grid_path("620", "banner")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"OLD")
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("library_hero.jpg", _img("NEW")),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("abc.ico", _img("ICO")),
        ],
    )
    result = art.fetch_best("620", "steam", "", ("banner", "cover"), force=True)
    assert result["art"]["banner"].read_bytes() == _img("NEW")
    assert result["art"]["cover"].read_bytes() == _img("COVER")


def _ico_with_png_frame(size=256, small=16):
    """A minimal multi-size ICO: one BMP frame plus a PNG one."""
    import struct

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    header = struct.pack("<HHH", 0, 1, 2)
    entries = b""
    data = b""
    for dim, blob in ((small, b"BMPDATA"), (size, png)):
        offset = 6 + 2 * 16 + len(data)
        entries += struct.pack(
            "<BBBBHHII",
            dim if dim < 256 else 0,
            dim if dim < 256 else 0,
            0,
            0,
            1,
            32,
            len(blob),
            offset,
        )
        data += blob
    return header + entries + data


def test_ico_client_icon_is_unwrapped_to_its_png_frame(monkeypatch, xdg_env):
    """Qt reads the 16x16 frame of an ICO; the 256x256 PNG is kept instead."""
    assert art.ico_png_frame(_ico_with_png_frame())[:8] == b"\x89PNG\r\n\x1a\n"
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
        ],
    )
    out = art.fetch_official("620", ("icon",))
    assert out["icon"].name == "steam-620-icon.png"
    assert out["icon"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_ico_without_png_frame_falls_back_to_the_jpg(monkeypatch, xdg_env):
    """An ICO with only BMP frames is skipped, not stored half-broken."""
    import struct

    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, 7, 22)
    bmp_only = header + entry + b"BMPDATA"
    assert art.ico_png_frame(bmp_only) is None
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Old Game", "old")),
            ("old.ico", bmp_only),
            ("old.jpg", _img("SMALL")),
        ],
    )
    out = art.fetch_official("621", ("icon",))
    assert out["icon"].read_bytes() == _img("SMALL")


def test_clear_fetched_removes_files_and_marks(monkeypatch, xdg_env):
    """Clear deletes the AppID's art and records why it must not come back."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("library_hero.jpg", _img("HERO")),
        ],
    )
    art.fetch_best("620", "steam", "")
    assert art.cached_path("620", "cover") is not None
    assert art.provider_for("620", "cover") == "steam"
    removed = art.clear_fetched("620")
    assert removed == 3
    assert art.cached_path("620", "cover") is None
    assert art.cached_path("620", "icon") is None
    assert art.provider_for("620", "cover") == ""
    assert art.is_cleared("620") is True
    # Nothing to delete the second time, and the mark stays.
    assert art.clear_fetched("620") == 0
    assert art.is_cleared("620") is True


def test_cache_paths_keep_dots_in_the_game_id(xdg_env):
    """An AppID with a dot must not borrow another game's cache slot."""
    own = art.grid_path("local-a.b", "cover")
    other = art.grid_path("local-a", "cover")
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_bytes(b"own")
    other.write_bytes(b"other")
    assert art.cached_path("local-a.b", "cover") == own
    assert art.clear_fetched("local-a.b") == 1
    assert not own.exists()
    assert other.is_file()


def test_cleared_appid_is_not_refetched_in_the_background(monkeypatch, xdg_env):
    """The background fetch must not undo an explicit Clear."""
    _stub(monkeypatch, [(APP_INFO, _steam_apps("Portal 2", "abc"))])
    art.clear_fetched("620")
    assert art.fetch_best("620", "steam", "")["art"] == {}
    assert art.cached_path("620", "cover") is None
    # Fetch Artwork (forced) is the way back: the mark goes and art lands.
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("library_hero.jpg", _img("HERO")),
        ],
    )
    result = art.fetch_best("620", "steam", "", force=True)
    assert result["art"]["cover"].read_bytes() == _img("COVER")
    assert art.is_cleared("620") is False


def test_manual_slot_survives_clear(xdg_env, tmp_path):
    """Clear only touches downloaded art, never the picked files."""
    manual = art.store_manual("620", "icon", str(_image(tmp_path, "m.png")))
    art.clear_fetched("620")
    assert manual is not None and manual.is_file()


def test_clear_hides_the_manual_slot_but_keeps_the_file(xdg_env, tmp_path):
    """A cleared game shows nothing; the picked file is still on disk."""
    manual = art.store_manual("620", "icon", str(_image(tmp_path, "m.png")))
    art.clear_fetched("620")
    assert manual.is_file()
    assert art.resolve("620", "icon") == (None, "")
    # Fetch Artwork drops the mark and the manual slot is back at once.
    art.unmark_cleared("620")
    assert art.resolve("620", "icon")[0] == manual


def test_cleared_kind_hides_the_cover_and_steam_art(monkeypatch, xdg_env):
    """The tile's clear drops one file and keeps every fallback away."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("library_hero.jpg", _img("HERO")),
        ],
    )
    art.fetch_best("620", "steam", "")
    assert art.cached_path("620", "icon") is not None
    assert art.clear_kind("620", "icon") is True
    assert art.cached_path("620", "icon") is None
    assert art.is_kind_cleared("620", "icon") is True
    # The cover sitting next to it does not answer for the icon anymore.
    assert art.resolve("620", "icon") == (None, "")
    # The other kinds stay, and the backdrop still derives from the banner.
    assert art.resolve("620", "cover")[0] is not None
    assert art.resolve("620", "background")[0] is not None
    # A background pass leaves the cleared kind alone.
    art.fetch_best("620", "steam", "")
    assert art.cached_path("620", "icon") is None
    # Fetch Artwork (forced) restores it.
    art.fetch_best("620", "steam", "", force=True)
    assert art.cached_path("620", "icon") is not None
    assert art.is_kind_cleared("620", "icon") is False


def test_forced_fetch_restores_the_cleared_background(monkeypatch, xdg_env):
    """The backdrop has no download of its own: Fetch drops its mark too."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", _img("COVER")),
            ("library_hero.jpg", _img("HERO")),
        ],
    )
    art.fetch_best("620", "steam", "")
    assert art.resolve("620", "background")[0] is not None
    art.clear_kind("620", "background")
    assert art.is_kind_cleared("620", "background") is True
    assert art.resolve("620", "background") == (None, "")
    art.fetch_best("620", "steam", "", force=True)
    assert art.is_kind_cleared("620", "background") is False
    assert art.resolve("620", "background")[0] is not None


def test_clear_hides_the_exe_icon_until_a_fetch(monkeypatch, xdg_env, tmp_path):
    """A cleared local game shows no executable icon either."""
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    exe = _local_exe(tmp_path)
    path, source = art.resolve("local-doom", "icon", "", str(exe))
    assert source == "exe"
    art.clear_fetched("local-doom")
    assert art.resolve("local-doom", "icon", "", str(exe)) == (None, "")
    # Fetch Artwork drops the mark; the icon the game ships stays on disk.
    art.fetch_best("local-doom", "steam", "", names=("Doom",), force=True)
    assert art.resolve("local-doom", "icon", "", str(exe)) == (path, "exe")


def _local_exe(tmp_path, name="game.exe"):
    exe = tmp_path / name
    exe.write_bytes(b"MZ")
    return exe


def test_exe_icon_fills_a_local_games_empty_icon(monkeypatch, xdg_env, tmp_path):
    """A local game with no art shows the icon embedded in its executable."""
    calls = []

    def fake_icon(path):
        calls.append(path)
        return _img("ICO")

    monkeypatch.setattr(art.exeiconmod, "icon_bytes", fake_icon)
    exe = _local_exe(tmp_path)
    path, source = art.resolve("local-doom", "icon", "", str(exe))
    assert source == "exe"
    assert path == art.exe_icon_path("local-doom")
    assert path.read_bytes() == _img("ICO")
    # Cached: the next refresh only stats the executable.
    assert art.resolve("local-doom", "icon", "", str(exe)) == (path, "exe")
    assert calls == [exe]


def test_exe_icon_is_reextracted_when_the_executable_changes(monkeypatch, xdg_env, tmp_path):
    versions = [b"OLD", _img("NEW")]
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: versions.pop(0))
    exe = _local_exe(tmp_path)
    first = art.exe_icon("local-doom", str(exe))
    assert first is not None and first.read_bytes() == b"OLD"
    exe.write_bytes(b"MZ!")
    second = art.exe_icon("local-doom", str(exe))
    assert second is not None and second.read_bytes() == _img("NEW")


def test_exe_icon_never_beats_real_art(monkeypatch, xdg_env, tmp_path):
    """Manual slots, downloaded art and Steam art all win over the exe icon."""
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: b"EXE")
    exe = _local_exe(tmp_path)
    manual = art.store_manual("local-doom", "icon", str(_image(tmp_path, "m.png")))
    assert art.resolve("local-doom", "icon", "", str(exe)) == (manual, "manual")
    art.clear_manual("local-doom", "icon")
    cached = art.grid_path("local-doom", "icon")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(_img("PNG"))
    assert art.resolve("local-doom", "icon", "", str(exe)) == (cached, "cache")


def test_exe_icon_is_ignored_for_a_steam_game(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: b"EXE")
    exe = _local_exe(tmp_path)
    assert art.resolve("steam-480", "icon", "", str(exe)) == (None, "")


def _steam_icon(gid, provider):
    path = art.grid_path(gid, "icon")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_img("PNG"))
    art._write_manifest(gid, "icon", provider)
    return path


def test_local_exe_icon_beats_the_sources_steam_icon(monkeypatch, xdg_env, tmp_path):
    """A 32x32 official client icon must not hide the game's own icon."""
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    _steam_icon("480", "steam")
    exe = _local_exe(tmp_path)
    path, source = art.resolve("local-doom", "icon", "480", str(exe))
    assert source == "exe" and path == art.exe_icon_path("local-doom")


def test_local_exe_icon_keeps_a_community_source_icon(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    source_icon = _steam_icon("480", "sgdb")
    exe = _local_exe(tmp_path)
    assert art.resolve("local-doom", "icon", "480", str(exe)) == (source_icon, "appid-cache")


def test_local_exe_icon_keeps_a_manual_source_icon(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    manual = art.store_manual("480", "icon", str(_image(tmp_path, "source.png")))
    exe = _local_exe(tmp_path)
    assert art.resolve("local-doom", "icon", "480", str(exe)) == (manual, "appid-manual")


def test_local_exe_icon_beats_its_own_steam_icon(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    _steam_icon("local-doom", "steam")
    exe = _local_exe(tmp_path)
    assert art.resolve("local-doom", "icon", "", str(exe))[1] == "exe"


def test_exe_icon_uses_the_sibling_exe_of_a_native_launcher(monkeypatch, xdg_env, tmp_path):
    """A Ren'Py port launches a .sh but ships the .exe beside it."""
    calls = []
    monkeypatch.setattr(
        art.exeiconmod, "icon_bytes", lambda path: calls.append(path) or _img("ICO")
    )
    launcher = tmp_path / "game.sh"
    launcher.write_bytes(b"#!/bin/sh")
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    path = art.exe_icon("local-doom", str(launcher))
    assert path is not None and path.read_bytes() == _img("ICO")
    assert calls == [exe]


def test_exe_icon_uses_the_only_exe_in_the_directory(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    launcher = tmp_path / "renpy.sh"
    launcher.write_bytes(b"#!/bin/sh")
    (tmp_path / "Game.exe").write_bytes(b"MZ")
    assert art.exe_icon("local-doom", str(launcher)) is not None


def test_exe_icon_refuses_an_ambiguous_directory(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: _img("ICO"))
    launcher = tmp_path / "run.sh"
    launcher.write_bytes(b"#!/bin/sh")
    (tmp_path / "one.exe").write_bytes(b"MZ")
    (tmp_path / "two.exe").write_bytes(b"MZ")
    assert art.exe_icon("local-doom", str(launcher)) is None
    # A same-stem .exe still wins over the ambiguity.
    (tmp_path / "run.exe").write_bytes(b"MZ")
    assert art.exe_icon("local-doom", str(launcher)) is not None


def _ico_blob(frames):
    """An ICO from [(size, payload), ...], entries in the given order."""
    import struct

    head = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries = b""
    blobs = b""
    for size, data in frames:
        side = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    return head + entries + blobs


def test_best_ico_frame_takes_the_largest_png_frame(xdg_env):
    small = b"\x89PNG\r\n\x1a\n" + b"a" * 4
    large = b"\x89PNG\r\n\x1a\n" + b"b" * 4
    body, suffix = art.best_ico_frame(_ico_blob([(16, small), (64, large)]))
    assert (body, suffix) == (large, ".png")


def test_best_ico_frame_sorts_a_bmp_only_icon_largest_first(xdg_env):
    blob = _ico_blob([(16, b"SMALL"), (256, b"BIG")])
    body, suffix = art.best_ico_frame(blob)
    assert suffix == ".ico" and len(body) == len(blob)
    # ICO width/height 0 means 256: the largest entry is now first.
    assert body[6] == 0 and body[7] == 0


def test_best_ico_frame_keeps_an_unreadable_blob(xdg_env):
    assert art.best_ico_frame(_img("ICO")) == (_img("ICO"), ".ico")


def test_exe_icon_stores_the_best_frame(monkeypatch, xdg_env, tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 8
    icon = _ico_blob([(16, b"SMALL"), (64, png)])
    calls = []
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: calls.append(path) or icon)
    exe = _local_exe(tmp_path)
    path = art.exe_icon("local-doom", str(exe))
    assert path is not None and path.suffix == ".png" and path.read_bytes() == png
    assert path in art.cache_files("local-doom")
    # Cached with the version marker: the next refresh only stats.
    assert art.exe_icon("local-doom", str(exe)) == path
    assert calls == [exe]
    record = art.read_manifest("local-doom")[art.EXE_ICON_KEY]
    assert record["icon_version"] == art.EXE_ICON_VERSION
    assert record["suffix"] == ".png"


def test_exe_icon_reextracts_a_cache_from_before_the_frame_fix(monkeypatch, xdg_env, tmp_path):
    icon = _ico_blob([(64, b"\x89PNG\r\n\x1a\n" + b"x")])
    calls = []
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: calls.append(path) or icon)
    exe = _local_exe(tmp_path)
    assert art.exe_icon("local-doom", str(exe)) is not None
    data = art.read_manifest("local-doom")
    data[art.EXE_ICON_KEY].pop("icon_version")
    art.manifest_path("local-doom").write_text(json.dumps(data))
    assert art.exe_icon("local-doom", str(exe)) is not None
    assert len(calls) == 2


def test_fetch_image_returns_the_body_and_enforces_the_cap(monkeypatch, xdg_env):
    """A pasted URL is downloaded; the GUI decodes the payload with Qt."""
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    _stub(monkeypatch, [("cdn/a.png", payload)])
    body, error = art.fetch_image("https://cdn/a.png")
    assert error == "" and body == payload
    _stub(monkeypatch, [("cdn/a.txt", b"not an image")])
    assert art.fetch_image("https://cdn/a.txt") == (b"not an image", "")
    _stub(monkeypatch, [("cdn/big.png", payload)])
    assert art.fetch_image("https://cdn/big.png", limit=4) == (None, "too-large")


def test_get_never_reads_past_the_limit(monkeypatch, xdg_env):
    """A huge body is cut at the cap instead of being buffered."""
    _stub(monkeypatch, [("cdn/huge.png", b"x" * 64)])
    assert art._get("https://cdn/huge.png", limit=8) == (None, "too-large")
    assert art._get("https://cdn/huge.png", limit=64) == (b"x" * 64, "")


def test_image_suffix_detects_avif(xdg_env):
    """AVIF is an ISO-BMFF file whose brand list names it."""
    avif = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1" + b"0" * 8
    assert art.image_suffix(avif) == ".avif"
    assert art.image_suffix(b"\x00\x00\x00\x1cftypmif1\x00\x00\x00\x00mif1avif") == ".avif"
    assert art.image_suffix(b"\x00\x00\x00\x1cftypheic\x00\x00\x00\x00heicmif1") == ""


def test_image_size_token_warns_above_4k_and_refuses_above_8k(xdg_env):
    assert art.image_size_token(3840, 2160) == ""
    assert art.image_size_token(4096, 2160) == ""
    assert art.image_size_token(4097, 1080) == "large"
    assert art.image_size_token(8000, 4000) == "large"
    assert art.image_size_token(8192, 1080) == "large"
    assert art.image_size_token(8193, 1080) == "huge"
    assert art.image_size_token(8192, 8192) == "huge"


def test_store_manual_bytes_writes_the_slot(xdg_env):
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 4
    dest = art.store_manual_bytes("local-doom", "icon", png)
    assert dest is not None and dest.read_bytes() == png
    assert art.resolve("local-doom", "icon") == (dest, "manual")


def test_store_manual_bytes_keeps_an_avif_slot(xdg_env):
    avif = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1" + b"0" * 8
    dest = art.store_manual_bytes("local-doom", "cover", avif)
    assert dest is not None and dest.suffix == ".avif"
    assert art.resolve("local-doom", "cover") == (dest, "manual")
    assert art.store_manual_bytes("local-doom", "nope", dest.read_bytes()) is None


def test_steam_cache_uses_the_canonical_key(xdg_env):
    assert art.grid_path("steam-480").name == "steam-480.png"
    assert art.grid_path("480").name == "steam-480.png"
    assert art.manifest_path("480").name == "steam-480.json"
    assert art.manual_dir("480").name == "steam-480"
    assert art.grid_path("local-doom").name == "local-doom.png"


def test_migrate_cache_keys_renames_numeric_names(xdg_env):
    from tkarcade import xdg as X

    grids = X.app_cache_dir() / "grids"
    grids.mkdir(parents=True)
    for name in ("620.png", "620-icon.png", "620.json"):
        (grids / name).write_bytes(b"x")
    (grids / "local-doom.png").write_bytes(b"x")
    manual = X.app_cache_dir() / "artwork" / "620"
    manual.mkdir(parents=True)
    protondb = X.app_cache_dir() / "protondb"
    protondb.mkdir()
    (protondb / "620.json").write_text("{}")

    renamed = art.migrate_cache_keys()
    assert len(renamed) == 5
    assert (grids / "steam-620.png").is_file()
    assert (grids / "steam-620-icon.png").is_file()
    assert (grids / "steam-620.json").is_file()
    assert (protondb / "steam-620.json").is_file()
    assert (X.app_cache_dir() / "artwork" / "steam-620").is_dir()
    assert art.cached_path("620", "cover") is not None
    assert art.migrate_cache_keys() == []


def test_migrate_cache_keys_never_overwrites(xdg_env):
    from tkarcade import xdg as X

    grids = X.app_cache_dir() / "grids"
    grids.mkdir(parents=True)
    (grids / "620.png").write_bytes(b"old")
    (grids / "steam-620.png").write_bytes(b"new")
    assert art.migrate_cache_keys() == []
    assert (grids / "620.png").read_bytes() == b"old"
    assert (grids / "steam-620.png").read_bytes() == b"new"


def test_cache_files_and_clear_cover_every_artifact(xdg_env):
    grid = art.grid_path("620", "cover")
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"x")
    art.grid_path("620", "banner").write_bytes(b"x")
    art.manifest_path("620").write_text("{}")
    manual = art.manual_dir("620")
    manual.mkdir(parents=True)
    (manual / "cover.png").write_bytes(b"x")

    assert len(art.cache_files("620")) == 4
    assert art.clear_cache("620") is True
    assert art.cache_files("620") == []
    assert not manual.exists()


def test_cache_keys_lists_games_with_art(xdg_env):
    grid = art.grid_path("620", "cover")
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"x")
    art.grid_path("local-doom", "icon").write_bytes(b"x")
    assert art.cache_keys() == {"steam-620", "local-doom"}


def _igdb_game(igdb_id: str = "1145360") -> None:
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-hades"
    cfg.general.name = "Hades"
    cfg.metadata.igdb_id = igdb_id
    C.save(cfg)


def _igdb_creds() -> None:
    from tkarcade import config as C

    prefs = C.Preferences()
    prefs.igdb_client_id = "cid"
    prefs.igdb_client_secret = "sec"
    C.save_preferences(prefs)


IGDB_ROUTES = [
    ("id.twitch.tv", {"access_token": "tok", "expires_in": 3600}),
    (
        "api.igdb.com",
        [
            {
                "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1.jpg"},
                "artworks": [{"url": "//images.igdb.com/igdb/image/upload/t_thumb/ar1.jpg"}],
            }
        ],
    ),
    ("co1.jpg", _img("COVER")),
    ("ar1.jpg", _img("BANNER")),
]


def test_igdb_fills_cover_and_banner(monkeypatch, xdg_env):
    """The chosen IGDB provider stores its cover and banner in the cache."""
    _igdb_game()
    _igdb_creds()
    _stub(monkeypatch, IGDB_ROUTES)
    result = art.fetch_best(
        "local-hades", "igdb", "", ("cover", "banner"), force=True, names=("Hades",)
    )
    assert result["provider"] == "igdb"
    assert result["art"]["cover"].read_bytes() == _img("COVER")
    assert result["art"]["banner"].read_bytes() == _img("BANNER")
    assert art.provider_for("local-hades", "cover") == "igdb"
    assert art.provider_for("local-hades", "banner") == "igdb"


def test_igdb_reports_the_missing_id(monkeypatch, xdg_env):
    """IGDB has no name search: without [metadata] igdb_id it says so."""
    _igdb_game("")
    _igdb_creds()
    assert art.fetch_igdb("local-hades") == ({}, "no-id")


def test_igdb_reports_the_missing_key(monkeypatch, xdg_env):
    _igdb_game()
    assert art.fetch_igdb("local-hades") == ({}, "no-igdb-key")


def test_igdb_fetches_a_draft_id_before_save(monkeypatch, xdg_env):
    """The dialog's just-picked id works without a stored igdb_id."""
    _igdb_game("")
    _igdb_creds()
    _stub(monkeypatch, IGDB_ROUTES)
    result = art.fetch_best(
        "local-hades",
        "igdb",
        "",
        ("cover", "banner"),
        force=True,
        names=("Hades",),
        igdb_id="1145360",
    )
    assert result["provider"] == "igdb"
    assert result["igdb_id"] == "1145360"
    assert result["art"]["cover"].read_bytes() == _img("COVER")
    assert result["art"]["banner"].read_bytes() == _img("BANNER")


def test_igdb_search_resolves_an_exact_title(monkeypatch, xdg_env):
    """Fetch Artwork searches IGDB when no id was stored first."""
    _igdb_game("")
    _igdb_creds()
    _stub(monkeypatch, IGDB_ROUTES)
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda _query: [{"id": "1145360", "name": "Hades (2020)"}],
    )
    result = art.fetch_best(
        "local-hades",
        "igdb",
        "",
        ("cover", "banner"),
        force=True,
        names=("Hades",),
    )
    assert result["provider"] == "igdb"
    assert result["igdb_id"] == "1145360"
    assert result["art"]["cover"].read_bytes() == _img("COVER")
    assert art.stored_igdb_id("local-hades") == "1145360"


def test_igdb_search_returns_candidates(monkeypatch, xdg_env):
    """No exact title: the provider-tagged rows reach the picker."""
    _igdb_game("")
    _igdb_creds()
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda _query: [{"id": "1", "name": "Hades II (2024)"}],
    )
    result = art.fetch_best("local-hades", "igdb", "", ("cover",), force=True, names=("Hades",))
    assert result["art"] == {}
    assert result["error"] == "no-match"
    assert result["candidates"] == [{"id": "1", "name": "Hades II (2024)", "provider": "igdb"}]


def test_igdb_search_reports_the_missing_key(monkeypatch, xdg_env):
    _igdb_game("")
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda _query: (_ for _ in ()).throw(AssertionError("searched without a key")),
    )
    result = art.fetch_best("local-hades", "igdb", "", ("cover",), force=True, names=("Hades",))
    assert result["error"] == "no-igdb-key"
    assert result["candidates"] == []


def test_igdb_search_uses_the_steam_name(monkeypatch, xdg_env):
    """A Steam game without an IGDB id searches its official name."""
    _igdb_creds()
    _stub(monkeypatch, IGDB_ROUTES)
    monkeypatch.setattr(art, "steam_app", lambda _appid: {"name": "Hades"})
    seen = []
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda query: seen.append(query) or [{"id": "1", "name": "Hades (2020)"}],
    )
    result = art.fetch_best("620", "igdb", "", ("cover",), force=True)
    assert seen == ["Hades"]
    assert result["provider"] == "igdb"
    assert result["igdb_id"] == "1"
    assert art.stored_igdb_id("620") == "1"


def test_clear_keeps_the_igdb_choice(monkeypatch, xdg_env):
    """Clear removes the files but remembers the resolved IGDB game."""
    _igdb_game("")
    _igdb_creds()
    _stub(monkeypatch, IGDB_ROUTES)
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda _query: [{"id": "1145360", "name": "Hades (2020)"}],
    )
    art.fetch_best("local-hades", "igdb", "", ("cover",), force=True, names=("Hades",))
    assert art.stored_igdb_id("local-hades") == "1145360"
    art.clear_fetched("local-hades")
    assert art.stored_igdb_id("local-hades") == "1145360"
    monkeypatch.setattr(
        art.igdbmod,
        "search",
        lambda _query: (_ for _ in ()).throw(AssertionError("searched again")),
    )
    _stub(monkeypatch, IGDB_ROUTES)
    result = art.fetch_best("local-hades", "igdb", "", ("cover",), force=True, names=("Hades",))
    assert result["art"]["cover"].read_bytes() == _img("COVER")


def _vndb_game(vndb_id: str = "v2002") -> None:
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-sg"
    cfg.general.name = "Steins;Gate"
    cfg.metadata.vndb_id = vndb_id
    C.save(cfg)


VNDB_LINKS = {"cover": "https://t.vndb.org/cv/1.jpg", "banner": "https://t.vndb.org/sf/1.jpg"}
VNDB_ROUTES = [
    ("t.vndb.org/cv/1.jpg", _img("VCOVER")),
    ("t.vndb.org/sf/1.jpg", _img("VSHOT")),
]


def test_vndb_fills_cover_and_banner(monkeypatch, xdg_env):
    """The chosen VNDB provider stores the cover and a screenshot banner."""
    _vndb_game()
    monkeypatch.setattr(art.vndbmod, "art", lambda _vn, timeout=15, safe=False: (VNDB_LINKS, ""))
    _stub(monkeypatch, VNDB_ROUTES)
    result = art.fetch_best(
        "local-sg", "vndb", "", ("cover", "banner"), force=True, names=("Steins;Gate",)
    )
    assert result["provider"] == "vndb"
    assert result["vndb_id"] == "v2002"
    assert result["art"]["cover"].read_bytes() == _img("VCOVER")
    assert result["art"]["banner"].read_bytes() == _img("VSHOT")
    assert art.provider_for("local-sg", "cover") == "vndb"
    assert art.provider_for("local-sg", "banner") == "vndb"


def test_vndb_reports_the_missing_id(monkeypatch, xdg_env):
    _vndb_game("")
    monkeypatch.setattr(
        art.vndbmod,
        "search",
        lambda _query: (_ for _ in ()).throw(AssertionError("searched without a name")),
    )
    assert art.fetch_vndb("local-sg") == ({}, "no-vndb-id")


def test_vndb_fetches_a_draft_id_before_save(monkeypatch, xdg_env):
    """The dialog's just-picked id works without a stored vndb_id."""
    _vndb_game("")
    monkeypatch.setattr(art.vndbmod, "art", lambda _vn, timeout=15, safe=False: (VNDB_LINKS, ""))
    _stub(monkeypatch, VNDB_ROUTES)
    result = art.fetch_best(
        "local-sg",
        "vndb",
        "",
        ("cover", "banner"),
        force=True,
        names=("Steins;Gate",),
        vndb_id="v2002",
    )
    assert result["provider"] == "vndb"
    assert result["vndb_id"] == "v2002"
    assert result["art"]["cover"].read_bytes() == _img("VCOVER")


def test_vndb_search_resolves_an_exact_title(monkeypatch, xdg_env):
    """Fetch Artwork searches VNDB when no id was stored first."""
    _vndb_game("")
    monkeypatch.setattr(
        art.vndbmod,
        "search",
        lambda _query: [
            {"id": "v2002", "name": "STEINS;GATE (2009)", "title": "STEINS;GATE", "alt": ""}
        ],
    )
    monkeypatch.setattr(art.vndbmod, "art", lambda _vn, timeout=15, safe=False: (VNDB_LINKS, ""))
    _stub(monkeypatch, VNDB_ROUTES)
    result = art.fetch_best("local-sg", "vndb", "", ("cover",), force=True, names=("Steins;Gate",))
    assert result["provider"] == "vndb"
    assert result["vndb_id"] == "v2002"
    assert art.stored_vndb_id("local-sg") == "v2002"


def test_vndb_search_returns_candidates(monkeypatch, xdg_env):
    """No exact title: the provider-tagged rows reach the picker."""
    _vndb_game("")
    row = {"id": "v9", "name": "STEINS;GATE 0 (2015)", "title": "STEINS;GATE 0", "alt": ""}
    monkeypatch.setattr(art.vndbmod, "search", lambda _query: [row])
    result = art.fetch_best("local-sg", "vndb", "", ("cover",), force=True, names=("Steins;Gate",))
    assert result["art"] == {}
    assert result["error"] == "no-match"
    assert result["candidates"] == [dict(row, provider="vndb")]


def test_vndb_search_uses_the_steam_name(monkeypatch, xdg_env):
    """A Steam game without a VNDB id searches its official name."""
    monkeypatch.setattr(art, "steam_app", lambda _appid: {"name": "Steins;Gate"})
    monkeypatch.setattr(
        art.vndbmod,
        "search",
        lambda _query: [
            {"id": "v2002", "name": "STEINS;GATE (2009)", "title": "STEINS;GATE", "alt": ""}
        ],
    )
    monkeypatch.setattr(art.vndbmod, "art", lambda _vn, timeout=15, safe=False: (VNDB_LINKS, ""))
    _stub(monkeypatch, VNDB_ROUTES)
    result = art.fetch_best("620", "vndb", "", ("cover",), force=True)
    assert result["provider"] == "vndb"
    assert result["vndb_id"] == "v2002"
    assert art.stored_vndb_id("620") == "v2002"


def test_clear_keeps_the_vndb_choice(monkeypatch, xdg_env):
    """Clear removes the files but remembers the resolved visual novel."""
    _vndb_game("")
    monkeypatch.setattr(art.vndbmod, "art", lambda _vn, timeout=15, safe=False: (VNDB_LINKS, ""))
    monkeypatch.setattr(
        art.vndbmod,
        "search",
        lambda _query: [
            {"id": "v2002", "name": "STEINS;GATE (2009)", "title": "STEINS;GATE", "alt": ""}
        ],
    )
    _stub(monkeypatch, VNDB_ROUTES)
    art.fetch_best("local-sg", "vndb", "", ("cover",), force=True, names=("Steins;Gate",))
    assert art.stored_vndb_id("local-sg") == "v2002"
    art.clear_fetched("local-sg")
    assert art.stored_vndb_id("local-sg") == "v2002"
    monkeypatch.setattr(
        art.vndbmod,
        "search",
        lambda _query: (_ for _ in ()).throw(AssertionError("searched again")),
    )
    _stub(monkeypatch, VNDB_ROUTES)
    result = art.fetch_best("local-sg", "vndb", "", ("cover",), force=True, names=("Steins;Gate",))
    assert result["art"]["cover"].read_bytes() == _img("VCOVER")


def test_safe_artwork_hides_flagged_sgdb_entries(monkeypatch, xdg_env):
    """The preference drops SteamGridDB entries the site marks nsfw."""
    from tkarcade import config as C

    prefs = C.Preferences()
    prefs.hide_explicit_artwork = True
    C.save_preferences(prefs)
    _stub(
        monkeypatch,
        [
            (
                "grids/game",
                {
                    "data": [
                        dict(_grid_entry("https://cdn/nsfw.png", 600, 900), nsfw=True),
                        _grid_entry("https://cdn/safe.png", 600, 900),
                    ]
                },
            ),
            ("cdn/safe.png", _img("SAFE")),
        ],
    )
    art.fetch_sgdb_game("local-sg", "9", "KEY", ("cover",))
    assert art.provider_for("local-sg", "cover") == "sgdb"
    assert art.grid_path("local-sg", "cover").read_bytes() == _img("SAFE")


def test_provider_order_puts_the_choice_first(xdg_env, monkeypatch):
    """Four providers: the choice runs first, the rest keep PROVIDERS order."""
    calls = []

    def fake_steam(*_args, **_kwargs):
        calls.append("steam")
        return {}

    def fake_sgdb(*_args, **_kwargs):
        calls.append("sgdb")
        return {}, "no-key"

    def fake_igdb(*_args, **_kwargs):
        calls.append("igdb")
        return {}, "no-id"

    def fake_vndb(*_args, **_kwargs):
        calls.append("vndb")
        return {}, "no-vndb-id"

    monkeypatch.setattr(art, "steam_app", lambda _appid: {"name": "Game"})
    monkeypatch.setattr(art, "fetch_official", fake_steam)
    monkeypatch.setattr(art, "fetch_sgdb", fake_sgdb)
    monkeypatch.setattr(art, "fetch_igdb", fake_igdb)
    monkeypatch.setattr(art, "fetch_vndb", fake_vndb)
    monkeypatch.setattr(art.vndbmod, "search", lambda _query: [])
    art.fetch_best("620", "igdb", "", ("cover",))
    assert calls == ["igdb", "steam", "sgdb", "vndb"]
    calls.clear()
    art.fetch_best("620", "vndb", "", ("banner",))
    assert calls == ["vndb", "steam", "sgdb", "igdb"]


def test_manifest_write_survives_a_failed_rename(monkeypatch, xdg_env):
    """A crash mid-write must leave the previous providers and ids intact."""
    path = art.manifest_path("local-x")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"icon": {"provider": "steam"}}', encoding="utf-8")
    art.store_sgdb_id("local-x", "123", "X")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(art.cfgmod.os, "replace", boom)
    art.store_igdb_id("local-x", "99", "X")
    data = art.read_manifest("local-x")
    assert data["icon"] == {"provider": "steam"}
    assert data["sgdb"] == {"game_id": "123", "name": "X"}
    assert "igdb" not in data


def test_store_rejects_a_page_served_as_an_image(monkeypatch, xdg_env):
    """A 200 page must not fill the slot, or the kind is never retried."""
    html = b"<!DOCTYPE html><html><body>challenge</body></html>"
    monkeypatch.setattr(art, "_get", lambda url, *_a, **_k: (html, ""))
    assert art._store("local-x", "cover", "https://cdn/x.jpg") is None
    assert art.cached_path("local-x", "cover") is None
    assert art.provider_for("local-x", "cover") == ""
    assert art._missing_kinds("local-x", ("cover",), False) == ["cover"]
    # A real image still lands.
    monkeypatch.setattr(art, "_get", lambda url, *_a, **_k: (_img("A"), ""))
    assert art._store("local-x", "cover", "https://cdn/x.png") is not None


def test_steam_options_mark_the_first_existing_asset(monkeypatch, xdg_env):
    """Steam candidates keep the official order; 404 rows are hidden."""
    monkeypatch.setattr(art, "steam_app", lambda appid: {"name": "Canon", "icon": "abc"})
    monkeypatch.setattr(art, "_url_exists", lambda url: "library_600x900_2x" not in url)

    groups = art.steam_options("480")

    assert [row["label"] for row in groups["cover"]] == ["Library Cover", "Header"]
    assert [row["auto"] for row in groups["cover"]] == [True, False]
    assert [row["label"] for row in groups["banner"]] == ["Library Hero", "Header"]
    assert groups["banner"][0]["auto"] is True
    assert [row["label"] for row in groups["icon"]] == [
        "Client Icon",
        "Client Icon (32 px)",
        "Header",
    ]
    assert groups["icon"][0]["url"].endswith(".ico")
    assert groups["icon"][0]["thumb"].endswith(".jpg")
    # A non-numeric target has no official art.
    assert art.steam_options("local-x") == {}


def test_sgdb_game_options_sort_cap_and_mark(monkeypatch, xdg_env):
    """The chooser keeps the sort of the automatic pick and caps the list."""
    seen = []
    rows = [
        {
            "thumb": f"https://cdn/{index}.png",
            "width": 600,
            "height": 900,
            "style": "official" if index == 0 else "custom",
        }
        for index in range(art.GALLERY_LIMIT + 5)
    ]

    def fake_thumbs(game_id, kind, api_key, safe=False):
        seen.append((game_id, kind, api_key, safe))
        return rows

    monkeypatch.setattr(art, "_sgdb_thumbs", fake_thumbs)
    groups = art.sgdb_game_options("7", "KEY", ("cover",), safe=True)
    assert seen == [("7", "cover", "KEY", True)]
    assert len(groups["cover"]) == art.GALLERY_LIMIT
    assert groups["cover"][0]["auto"] is True
    assert groups["cover"][1]["auto"] is False
    assert "600x900" in groups["cover"][0]["note"]
    assert "official" in groups["cover"][0]["note"]


def test_store_choice_writes_the_slot_and_manifest(monkeypatch, xdg_env):
    """A chosen candidate lands in the provider slot with its provider tag."""
    _stub(monkeypatch, [("cdn/c.png", _img("C"))])
    path = art.store_choice("480", "cover", "https://cdn/c.png", "steam")
    assert path is not None and path.read_bytes() == _img("C")
    assert art.provider_for("480", "cover") == "steam"
    # Only a provider https URL reaches the downloader.
    assert art.store_choice("480", "banner", "file:///tmp/x.png", "steam") is None
    assert art.store_choice("480", "background", "https://cdn/c.png", "steam") is None
    assert art.store_choice("480", "cover", "https://cdn/c.png", "nope") is None


def test_art_gallery_falls_back_to_sgdb_for_a_local_game(monkeypatch, xdg_env):
    """A local game with Steam selected is queried on SteamGridDB by name."""
    monkeypatch.setattr(art, "steam_options", lambda *_a, **_k: {})
    monkeypatch.setattr(art, "stored_sgdb_id", lambda appid: "")
    monkeypatch.setattr(art, "_resolve_sgdb_game", lambda key, names: ("7", "Doom", []))
    monkeypatch.setattr(
        art,
        "sgdb_game_options",
        lambda game_id, key, kinds, safe=None: {
            "cover": [{"url": "https://cdn/c.png", "thumb": "https://cdn/c.png", "auto": True}]
        },
    )
    result = art.art_gallery("local-doom", "steam", "KEY", names=("Doom",))
    assert result["provider"] == "sgdb"
    assert result["game_id"] == "7"
    assert result["groups"]["cover"][0]["auto"] is True


def test_art_gallery_reads_igdb_without_downloading(monkeypatch, xdg_env):
    """The IGDB path returns the candidate rows and the resolved identity."""
    monkeypatch.setattr(art, "_resolved_igdb_id", lambda gid, draft="": "1")
    monkeypatch.setattr(
        art.igdbmod,
        "art_options",
        lambda gid, target="": (
            {"cover": [{"url": "https://cdn/c.png", "thumb": "https://cdn/c.png", "auto": True}]},
            "",
        ),
    )
    result = art.art_gallery("local-hades", "igdb", names=("Hades",))
    assert result["provider"] == "igdb"
    assert result["igdb_id"] == "1"
    assert result["groups"]["cover"][0]["url"] == "https://cdn/c.png"
    assert result["error"] == ""
