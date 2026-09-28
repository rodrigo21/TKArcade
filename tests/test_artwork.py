"""Artwork resolution and SteamGridDB fetching (network stubbed)."""

import json

from tksteamlaunch import artwork as art


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
    from tksteamlaunch import steam as S

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
            ("grids/game", {"data": [{"thumb": "https://cdn/x.png"}]}),
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
