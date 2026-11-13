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

    def read(self):
        return self._payload


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
            ("cdn/x.png", b"imagedata"),
        ],
    )
    path = art.fetch_missing("82", "KEY")
    assert path is not None and path.read_bytes() == b"imagedata"
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
    _stub(monkeypatch, [("games/steam", games), ("grids/game", grids), ("cdn.test", b"PNG")])
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
            ("cdn/tall.png", b"T"),
            ("cdn/hero.jpg", b"W"),
            ("cdn/square.png", b"S"),
        ],
    )
    out, error = art.fetch_sgdb("86", "KEY")
    assert error == ""
    assert out["icon"].read_bytes() == b"S"
    assert out["cover"].read_bytes() == b"T"
    assert out["banner"].read_bytes() == b"W"
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
            ("cdn/valve.png", b"V"),
        ],
    )
    out, _error = art.fetch_sgdb("88", "KEY", ("cover",))
    assert out["cover"].read_bytes() == b"V"
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
            ("cdn/any.png", b"ANY"),
        ],
    )
    out, _error = art.fetch_sgdb("87", "KEY", ("icon", "cover"))
    assert "cover" not in out
    assert out["icon"].read_bytes() == b"ANY"
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
            ("cdn/i.png", b"P"),
        ],
    )
    out, _error = art.fetch_sgdb("89", "KEY", ("icon",))
    assert out["icon"].read_bytes() == b"P"


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
    shared.write_bytes(b"S")
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
            ("library_600x900_2x.jpg", b"COVER"),
            ("library_hero.jpg", b"HERO"),
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
            ("def.jpg", b"SMALL"),
        ],
    )
    out = art.fetch_official("2399420", ("icon",))
    assert out["icon"].read_bytes() == b"SMALL"


def test_steam_client_icon_wins_over_the_sgdb_promo(monkeypatch, xdg_env):
    """The real 32x32 client icon beats a SteamGridDB 'official' promo."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Le Mans Ultimate", "def")),
            ("def.ico", urllib_error_404()),
            ("def.jpg", b"SMALL"),
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
            ("cdn/big.png", b"BIG"),
        ],
    )
    result = art.fetch_best("2399420", "steam", "KEY", ("icon",))
    assert result["art"]["icon"].read_bytes() == b"SMALL"
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
            ("cdn/big.png", b"BIG"),
        ],
    )
    result = art.fetch_best("2399420", "steam", "KEY", ("icon",))
    assert result["art"]["icon"].read_bytes() == b"BIG"
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
            ("def.jpg", b"SMALL"),
        ],
    )
    result = art.fetch_best("2399420", "steam", "", ("icon",))
    assert result["art"]["icon"].read_bytes() == b"SMALL"
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
            ("def.jpg", b"SMALL"),
        ],
    )
    result = art.fetch_best("2399420", "steam", "", ("icon",))
    assert result["art"]["icon"].read_bytes() == b"SMALL"
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
            ("cdn/cover.png", b"COVER"),
        ],
    )
    result = art.fetch_best("local-doom", "steam", "KEY", ("cover",), names=("Doom",))
    assert result["game_id"] == "7"
    assert result["art"]["cover"].read_bytes() == b"COVER"
    assert result["provider"] == "sgdb"
    assert art.stored_sgdb_id("local-doom") == "7"
    # A later fetch reuses the stored id and never searches again.
    _stub(
        monkeypatch,
        [
            ("games/steam", {"data": []}),
            ("grids/game", {"data": [_grid_entry("https://cdn/cover2.png", 600, 900)]}),
            ("cdn/cover2.png", b"NEW"),
        ],
    )
    again = art.fetch_best("local-doom", "steam", "KEY", ("cover",), force=True)
    assert again["game_id"] == "7"
    assert again["art"]["cover"].read_bytes() == b"NEW"


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
    assert result["candidates"] == [{"id": "5", "name": "Doom 3"}]
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
            ("cdn/cover.png", b"COVER"),
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
            ("cdn/community.png", b"COMMUNITY"),
            ("library_600x900_2x.jpg", b"OFFICIAL"),
            ("library_hero.jpg", b"HERO"),
            ("abc.ico", b"ICO"),
        ],
    )
    result = art.fetch_best("620", "sgdb", "KEY", ("cover", "banner"))
    assert result["provider"] == "sgdb"
    assert result["art"]["cover"].read_bytes() == b"COMMUNITY"
    assert result["art"]["banner"].read_bytes() == b"HERO"
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
            ("library_hero.jpg", b"NEW"),
            ("library_600x900_2x.jpg", b"COVER"),
            ("abc.ico", b"ICO"),
        ],
    )
    result = art.fetch_best("620", "steam", "", ("banner", "cover"), force=True)
    assert result["art"]["banner"].read_bytes() == b"NEW"
    assert result["art"]["cover"].read_bytes() == b"COVER"


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
            ("old.jpg", b"SMALL"),
        ],
    )
    out = art.fetch_official("621", ("icon",))
    assert out["icon"].read_bytes() == b"SMALL"


def test_clear_fetched_removes_files_and_marks(monkeypatch, xdg_env):
    """Clear deletes the AppID's art and records why it must not come back."""
    _stub(
        monkeypatch,
        [
            (APP_INFO, _steam_apps("Portal 2", "abc")),
            ("abc.ico", _ico_with_png_frame()),
            ("library_600x900_2x.jpg", b"COVER"),
            ("library_hero.jpg", b"HERO"),
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
            ("library_600x900_2x.jpg", b"COVER"),
            ("library_hero.jpg", b"HERO"),
        ],
    )
    result = art.fetch_best("620", "steam", "", force=True)
    assert result["art"]["cover"].read_bytes() == b"COVER"
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
            ("library_600x900_2x.jpg", b"COVER"),
            ("library_hero.jpg", b"HERO"),
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
            ("library_600x900_2x.jpg", b"COVER"),
            ("library_hero.jpg", b"HERO"),
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
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: b"ICO")
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
        return b"ICO"

    monkeypatch.setattr(art.exeiconmod, "icon_bytes", fake_icon)
    exe = _local_exe(tmp_path)
    path, source = art.resolve("local-doom", "icon", "", str(exe))
    assert source == "exe"
    assert path == art.exe_icon_path("local-doom")
    assert path.read_bytes() == b"ICO"
    # Cached: the next refresh only stats the executable.
    assert art.resolve("local-doom", "icon", "", str(exe)) == (path, "exe")
    assert calls == [exe]


def test_exe_icon_is_reextracted_when_the_executable_changes(monkeypatch, xdg_env, tmp_path):
    versions = [b"OLD", b"NEW"]
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: versions.pop(0))
    exe = _local_exe(tmp_path)
    first = art.exe_icon("local-doom", str(exe))
    assert first is not None and first.read_bytes() == b"OLD"
    exe.write_bytes(b"MZ!")
    second = art.exe_icon("local-doom", str(exe))
    assert second is not None and second.read_bytes() == b"NEW"


def test_exe_icon_never_beats_real_art(monkeypatch, xdg_env, tmp_path):
    """Manual slots, downloaded art and Steam art all win over the exe icon."""
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: b"EXE")
    exe = _local_exe(tmp_path)
    manual = art.store_manual("local-doom", "icon", str(_image(tmp_path, "m.png")))
    assert art.resolve("local-doom", "icon", "", str(exe)) == (manual, "manual")
    art.clear_manual("local-doom", "icon")
    cached = art.grid_path("local-doom", "icon")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"PNG")
    assert art.resolve("local-doom", "icon", "", str(exe)) == (cached, "cache")


def test_exe_icon_is_ignored_for_a_steam_game(monkeypatch, xdg_env, tmp_path):
    monkeypatch.setattr(art.exeiconmod, "icon_bytes", lambda path: b"EXE")
    exe = _local_exe(tmp_path)
    assert art.resolve("steam-480", "icon", "", str(exe)) == (None, "")


def test_fetch_image_accepts_png_and_rejects_junk(monkeypatch, xdg_env):
    """A pasted URL is downloaded and sniffed, not trusted by extension."""
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    _stub(monkeypatch, [("cdn/a.png", payload)])
    body, error = art.fetch_image("https://cdn/a.png")
    assert error == "" and body == payload
    _stub(monkeypatch, [("cdn/a.txt", b"not an image")])
    assert art.fetch_image("https://cdn/a.txt") == (None, "not-image")
    _stub(monkeypatch, [("cdn/big.png", payload)])
    assert art.fetch_image("https://cdn/big.png", limit=4) == (None, "too-large")


def test_store_manual_bytes_writes_the_slot(xdg_env):
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 4
    dest = art.store_manual_bytes("local-doom", "icon", png)
    assert dest is not None and dest.read_bytes() == png
    assert art.resolve("local-doom", "icon") == (dest, "manual")
    assert art.store_manual_bytes("local-doom", "icon", b"junk") is None
    assert art.store_manual_bytes("local-doom", "nope", png) is None


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
    ("co1.jpg", b"COVER"),
    ("ar1.jpg", b"BANNER"),
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
    assert result["art"]["cover"].read_bytes() == b"COVER"
    assert result["art"]["banner"].read_bytes() == b"BANNER"
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


def test_provider_order_puts_the_choice_first(xdg_env, monkeypatch):
    """Three providers: the choice runs first, the rest keep PROVIDERS order."""
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

    monkeypatch.setattr(art, "steam_app", lambda _appid: {"name": "Game"})
    monkeypatch.setattr(art, "fetch_official", fake_steam)
    monkeypatch.setattr(art, "fetch_sgdb", fake_sgdb)
    monkeypatch.setattr(art, "fetch_igdb", fake_igdb)
    art.fetch_best("620", "igdb", "", ("cover",))
    assert calls == ["igdb", "steam", "sgdb"]
    calls.clear()
    art.fetch_best("620", "sgdb", "", ("banner",))
    assert calls == ["sgdb", "steam", "igdb"]
