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
    assert out["icon"].name == "86-icon.png"
    assert out["cover"].name == "86.png"
    assert out["banner"].name == "86-banner.jpg"


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


def test_resolve_falls_back_to_the_source_appid(monkeypatch, xdg_env):
    """A local game borrows the source AppID's downloaded art."""
    donor_cover = art.grid_path("480", "cover")
    donor_cover.parent.mkdir(parents=True)
    donor_cover.write_bytes(b"P")
    assert art.resolve("local-doom", "icon", "480") == (donor_cover, "donor-cache")
    own = art.grid_path("local-doom", "cover")
    own.write_bytes(b"O")
    assert art.resolve("local-doom", "cover", "480") == (own, "cache")
    assert art.resolve("local-doom", "banner", "480") == (None, "")


def test_resolve_manual_slot_beats_everything(xdg_env, tmp_path):
    manual = art.store_manual("81", "icon", str(_image(tmp_path, "m.png")))
    assert manual is not None
    assert art.resolve("81", "icon", "480") == (manual, "manual")


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
    assert result["art"]["icon"].name == "620-icon.png"
    assert result["art"]["icon"].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert result["art"]["cover"].name == "620.jpg"
    assert result["art"]["banner"].name == "620-banner.jpg"
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
    assert out["icon"].name == "620-icon.png"
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
