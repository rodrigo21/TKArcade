"""Global log parsing and per-game aggregation."""

from tksteamlaunch import history as H


def test_parse_new_and_old_lines(tmp_path):
    log = tmp_path / "launcher.log"
    log.write_text(
        "2026-09-25T10:00:00 appid=1 exit=0 dur=125 cmd=/bin/true\n"
        "2026-09-25T11:00:00 appid=1 exit=1 cmd=/bin/false\n"
        "garbage line\n"
        "2026-09-25T12:00:00 appid=2 exit=0 dur=3661 cmd=/bin/true\n"
    )
    sessions = H.parse_log(log)
    assert [(s.appid, s.exit, s.duration) for s in sessions] == [
        ("1", 0, 125),
        ("1", 1, None),
        ("2", 0, 3661),
    ]
    stats = H.summarize(sessions)
    assert stats["1"].runs == 2 and stats["1"].fails == 1
    assert stats["1"].total_dur == 125
    assert stats["2"].total_dur == 3661
    assert stats["2"].last == "2026-09-25T12:00:00"


def test_parse_missing_file(tmp_path):
    assert H.parse_log(tmp_path / "nope.log") == []
    assert H.summarize([]) == {}
