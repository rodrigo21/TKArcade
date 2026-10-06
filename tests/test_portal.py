"""Native portal file picker (fake bus, no desktop needed)."""

from types import SimpleNamespace

from jeepney import MessageType


def _signal(path, response, uris):
    return SimpleNamespace(
        header=SimpleNamespace(message_type=MessageType.signal, fields={1: path, 3: "Response"}),
        body=(response, {"uris": ("as", uris)}),
    )


def _conn(replies, signals):
    """Scripted connection: reply bodies in call order, then signals."""
    state = {"n": 0}

    class Conn:
        def send_and_get_reply(self, msg, timeout=None):
            out = replies[state["n"]]
            state["n"] += 1
            return SimpleNamespace(body=out)

        def receive(self, timeout=None):
            return signals.pop(0) if signals else None

        def close(self):
            pass

    return Conn()


def test_pick_file_success_takes_first_file():
    from tkarcade.backends import portal as P

    req = "/org/freedesktop/portal/desktop/request/1_99/t"
    conn = _conn(
        [(":1.99",), (), (req,)],
        [_signal(req, 0, ["https://example.com/x", "file:///tmp/do%6Fm"])],
    )
    assert P.pick_file(_open=lambda: conn) == "/tmp/doom"


def test_pick_file_cancel_gives_empty():
    from tkarcade.backends import portal as P

    conn = _conn([(":1.7",), (), ("req",)], [_signal("req", 1, ["file:///tmp/doom"])])
    assert P.pick_file(_open=lambda: conn) == ""


def test_pick_file_no_bus_gives_empty():
    from tkarcade.backends import portal as P

    def boom():
        raise OSError("no bus")

    assert P.pick_file(_open=boom) == ""


def test_pick_file_ignores_foreign_signals():
    from tkarcade.backends import portal as P

    conn = _conn(
        [(":1.7",), (), ("req",)],
        [_signal("other-path", 0, ["file:///evil"]), _signal("req", 0, ["file:///good"])],
    )
    assert P.pick_file(_open=lambda: conn) == "/good"


def test_model_browse_delegates_to_portal(qgui_app, monkeypatch):
    from tkarcade.backends import portal as portalmod
    from tkarcade.gui.model import GameListModel

    monkeypatch.setattr(portalmod, "pick_file", lambda *a, **k: "/tmp/doom")
    assert GameListModel().browseExecutable() == "/tmp/doom"


def test_pick_file_reuses_existing_bus_name():
    from tkarcade.backends import portal as P

    members = []

    class Conn:
        unique_name = ":9.9"

        def send_and_get_reply(self, msg, timeout=None):
            members.append(msg.header.fields.get(3, ""))
            if members[-1] == "Hello":
                raise AssertionError("must not re-Hello")
            return SimpleNamespace(body=("req",))

        def receive(self, timeout=None):
            return None

        def close(self):
            pass

    assert P.pick_file(_open=lambda: Conn()) == ""
    assert "Hello" not in members
    assert members[0] == "AddMatch"
