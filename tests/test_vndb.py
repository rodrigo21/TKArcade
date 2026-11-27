"""VNDB adapter: title search, payload mapping and the id resolution."""

import json
import urllib.error

from tkarcade import config as C
from tkarcade import vndb


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _stub(monkeypatch, payload=None, error=None):
    calls = []

    def fake_open(request, timeout=15):
        calls.append(request)
        if error is not None:
            raise error
        return _Resp(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    return calls


def test_search_labels_candidates(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        {
            "results": [
                {"id": "v2002", "title": "STEINS;GATE", "alttitle": None, "released": "2009-10-15"},
                {"id": "v93", "title": "Muv-Luv", "alttitle": "マブラヴ", "released": "2003"},
            ]
        },
    )
    assert vndb.search("Steins;Gate") == [
        {"id": "v2002", "name": "STEINS;GATE (2009)", "title": "STEINS;GATE", "alt": ""},
        {
            "id": "v93",
            "name": "Muv-Luv / マブラヴ (2003)",
            "title": "Muv-Luv",
            "alt": "マブラヴ",
        },
    ]
    request = calls[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "filters": ["search", "=", "Steins;Gate"],
        "fields": "id,title,alttitle,released",
        "results": 10,
        "sort": "searchrank",
    }


def test_search_without_a_title_skips_the_network(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, {"results": []})
    assert vndb.search("  ") == []
    assert calls == []


def test_search_keeps_only_visual_novels(monkeypatch, xdg_env):
    _stub(monkeypatch, {"results": [{"id": "p42", "title": "NITRO PLUS"}, "junk"]})
    assert vndb.search("NITRO") == []


def test_fetch_maps_the_payload(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        {
            "results": [
                {
                    "id": "v2002",
                    "description": "[b]Fate[/b] &amp; time [url=https://example]travel[/url]",
                    "released": "2009-10",
                    "developers": [
                        {"name": "NITRO PLUS"},
                        {"name": "MAGES."},
                        {"name": "NITRO PLUS"},
                    ],
                    "tags": [
                        {"name": "Science Fiction", "rating": 3.0, "spoiler": 0},
                        {"name": "Spoiler Tag", "rating": 3.0, "spoiler": 1},
                        {"name": "Weak Tag", "rating": 1.0, "spoiler": 0},
                        {"name": "Romance", "rating": 2.0, "spoiler": 0},
                    ],
                }
            ]
        },
    )
    assert vndb.fetch("local-sg", "V2002") == {
        "description": "Fate & time travel",
        "developer": "NITRO PLUS, MAGES.",
        "publisher": "",
        "genre": "",
        "series": "",
        "age_ratings": [],
        "date": "2009-10",
        "tags": ["Science Fiction", "Romance"],
    }
    assert json.loads(calls[0].data)["filters"] == ["id", "=", "v2002"]


def test_fetch_drops_unknown_dates_and_fields(monkeypatch, xdg_env):
    _stub(
        monkeypatch,
        {"results": [{"id": "v1", "description": None, "released": "TBA", "developers": None}]},
    )
    data = vndb.fetch("local-x", "v1")
    assert data["date"] == ""
    assert data["description"] == ""
    assert data["developer"] == ""


def test_tags_keep_the_strongest_few_without_spoilers(monkeypatch, xdg_env):
    tags = [
        {"name": f"Tag {index}", "rating": 3.0, "spoiler": 0} for index in range(vndb.TAG_LIMIT + 5)
    ]
    tags.append({"name": "Spoiler", "rating": 3.0, "spoiler": 1})
    tags.append({"name": "Weak", "rating": 1.5, "spoiler": 0})
    _stub(monkeypatch, {"results": [{"id": "v1", "tags": tags}]})
    data = vndb.fetch("local-x", "v1")
    assert len(data["tags"]) == vndb.TAG_LIMIT
    assert "Spoiler" not in data["tags"]
    assert "Weak" not in data["tags"]


def test_resolve_prefers_the_draft_then_the_config(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-sg"
    cfg.metadata.vndb_id = "v2003"
    C.save(cfg)
    assert vndb.resolve("local-sg") == "v2003"
    assert vndb.resolve("local-sg", "v2002") == "v2002"
    assert vndb.resolve("local-none") == ""


def test_network_failure_is_none_and_no_candidates(monkeypatch, xdg_env):
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert vndb.search("Steins;Gate") == []
    assert vndb.fetch("local-sg", "v2002") is None


def _stub_sequence(monkeypatch, payloads):
    calls = []
    queue = list(payloads)

    def fake_open(request, timeout=15):
        calls.append(request)
        return _Resp(queue.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    return calls


def test_releases_list_the_linked_entries(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        {
            "results": [
                {
                    "id": "r1",
                    "title": "STEINS;GATE",
                    "alttitle": "シュタインズ・ゲート",
                    "released": "2009-10-15",
                    "platforms": ["win"],
                    "languages": [{"lang": "ja"}, {"lang": "en"}],
                    "official": True,
                    "vns": [{"id": "v2002", "rtype": "complete"}],
                    "producers": [
                        {"name": "NITRO PLUS", "developer": True, "publisher": False},
                        {"name": "MAGES.", "publisher": True},
                    ],
                },
                {
                    "id": "r2",
                    "title": "STEINS;GATE",
                    "released": "2010",
                    "platforms": ["ps3"],
                    "languages": [{"lang": "ja"}],
                    "official": False,
                    "vns": [{"id": "v2002", "rtype": "complete"}],
                    "producers": [],
                },
                {
                    "id": "r3",
                    "title": "Trial",
                    "released": "2008",
                    "platforms": ["win"],
                    "languages": [{"lang": "ja"}],
                    "official": True,
                    "vns": [{"id": "v2002", "rtype": "trial"}],
                    "producers": [],
                },
                {
                    "id": "r4",
                    "title": "Other game",
                    "released": "2009",
                    "official": True,
                    "vns": [{"id": "v9999", "rtype": "complete"}],
                    "producers": [],
                },
                "junk",
            ]
        },
    )

    rows = vndb.releases("V2002")

    assert [row["id"] for row in rows] == ["r1", "r2", "r3"]
    assert rows[0]["name"] == "STEINS;GATE (2009-10-15 · win · ja, en)"
    assert rows[1]["name"] == "STEINS;GATE (2010 · ps3 · ja) [unofficial]"
    assert rows[2]["name"] == "Trial (2008 · win · ja) [trial]"
    assert rows[0]["langs"] == ["ja", "en"]
    assert "NITRO PLUS (developer)" in rows[0]["detail"]
    assert "MAGES. (publisher)" in rows[0]["detail"]
    assert "シュタインズ・ゲート" in rows[0]["detail"]
    request = calls[0]
    assert request.full_url == vndb.RELEASE_ENDPOINT
    assert json.loads(request.data) == {
        "filters": ["vn", "=", ["id", "=", "v2002"]],
        "fields": vndb.RELEASE_FIELDS,
        "sort": "released",
        "results": vndb.RELEASE_RESULTS,
    }


def test_releases_without_an_id_skip_the_network(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, {"results": []})
    assert vndb.releases("  ") == []
    assert calls == []


def test_fetch_with_a_release_reads_its_date_and_publisher(monkeypatch, xdg_env):
    calls = _stub_sequence(
        monkeypatch,
        [
            {
                "results": [
                    {
                        "id": "v2002",
                        "description": "Syn",
                        "released": "2009-10",
                        "developers": [{"name": "NITRO PLUS"}],
                        "tags": [],
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": "r1234",
                        "released": "2010-06-24",
                        "producers": [
                            {"name": "NITRO PLUS", "developer": True, "publisher": False},
                            {"name": "MAGES.", "publisher": True},
                            {"name": "MAGES.", "publisher": True},
                        ],
                        "vns": [{"id": "v2002", "rtype": "complete"}],
                    }
                ]
            },
        ],
    )

    data = vndb.fetch("local-sg", "v2002", release="R1234")

    assert data["date"] == "2010-06-24"
    assert data["publisher"] == "MAGES."
    assert data["developer"] == "NITRO PLUS"
    assert calls[1].full_url == vndb.RELEASE_ENDPOINT
    assert json.loads(calls[1].data)["filters"] == ["id", "=", "r1234"]


def test_fetch_rejects_a_release_of_another_visual_novel(monkeypatch, xdg_env):
    _stub_sequence(
        monkeypatch,
        [
            {"results": [{"id": "v2002", "description": "Syn", "released": "2009"}]},
            {
                "results": [
                    {
                        "id": "r1234",
                        "released": "2010",
                        "producers": [{"name": "MAGES.", "publisher": True}],
                        "vns": [{"id": "v9999", "rtype": "complete"}],
                    }
                ]
            },
        ],
    )
    assert vndb.fetch("local-sg", "v2002", release="r1234") is None


def test_fetch_with_a_failed_release_returns_none(monkeypatch, xdg_env):
    calls = []

    def fake_open(request, timeout=15):
        calls.append(request)
        if len(calls) == 1:
            return _Resp({"results": [{"id": "v2002", "released": "2009", "tags": []}]})
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", fake_open)

    assert vndb.fetch("local-sg", "v2002", release="r1234") is None


def test_resolve_release_prefers_the_draft_then_the_config(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-sg"
    cfg.metadata.vndb_id = "v2002"
    cfg.metadata.vndb_release = "r9"
    C.save(cfg)
    assert vndb.resolve_release("local-sg") == "r9"
    assert vndb.resolve_release("local-sg", "", "r1") == "r1"
    # An explicit visual novel with no release means no release: clearing
    # the pick must win over the stored value.
    assert vndb.resolve_release("local-sg", "v2002") == ""
    # A release without a stored visual novel is not used.
    cfg.metadata.vndb_id = ""
    C.save(cfg)
    assert vndb.resolve_release("local-sg") == ""


def _art_payload(image=None, screenshots=()):
    return {
        "results": [
            {
                "image": image,
                "screenshots": list(screenshots),
            }
        ]
    }


def test_art_reads_the_cover_and_the_least_flagged_screenshot(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        _art_payload(
            {"url": "https://t.vndb.org/cv/1.jpg", "sexual": 0, "violence": 0},
            [
                {"url": "https://t.vndb.org/sf/2.jpg", "sexual": 2, "violence": 0},
                {"url": "https://t.vndb.org/sf/1.jpg", "sexual": 0.5, "violence": 0},
            ],
        ),
    )
    urls, error = vndb.art("v2002")
    assert error == ""
    assert urls == {
        "cover": "https://t.vndb.org/cv/1.jpg",
        "banner": "https://t.vndb.org/sf/1.jpg",
    }
    body = json.loads(calls[0].data)
    assert body["fields"] == (
        "image{url,dims,sexual,violence},screenshots{url,dims,sexual,violence}"
    )


def test_art_without_an_id_skips_the_network(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, _art_payload())
    assert vndb.art("") == ({}, "no-id")
    assert calls == []


def test_art_safe_drops_explicit_images(monkeypatch, xdg_env):
    """The preference filter drops flagged art and keeps the clean shots."""
    _stub(
        monkeypatch,
        _art_payload(
            {"url": "https://t.vndb.org/cv/1.jpg", "sexual": 2, "violence": 0},
            [
                {"url": "https://t.vndb.org/sf/2.jpg", "sexual": 2, "violence": 0},
                {"url": "https://t.vndb.org/sf/1.jpg", "sexual": 1, "violence": 0},
            ],
        ),
    )
    urls, error = vndb.art("v2002", safe=True)
    assert error == ""
    assert urls == {"banner": "https://t.vndb.org/sf/1.jpg"}


def test_art_safe_without_a_clean_image_is_not_found(monkeypatch, xdg_env):
    _stub(
        monkeypatch,
        _art_payload(
            {"url": "https://t.vndb.org/cv/1.jpg", "sexual": 2, "violence": 0},
            [{"url": "https://t.vndb.org/sf/2.jpg", "sexual": 0, "violence": 2}],
        ),
    )
    assert vndb.art("v2002", safe=True) == ({}, "not-found")


def test_art_accepts_a_missing_entry(monkeypatch, xdg_env):
    _stub(monkeypatch, {"results": []})
    assert vndb.art("v999999") == ({}, "not-found")
