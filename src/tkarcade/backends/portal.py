"""Native file picker via xdg-desktop-portal (one per desktop, no QtWidgets).

Uses the desktop's own file dialog (portal-kde, portal-gtk, ...) over
D-Bus with jeepney blocking I/O. Anything failing (no bus, no portal,
cancel) yields "" so callers fall back to typed paths.
"""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import unquote, urlparse

log = logging.getLogger("tkarcade.portal")

_DESKTOP = ("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
_REQUEST_IFACE = "org.freedesktop.portal.Request"


def _unwrap(value):
    """Unwrap a jeepney variant (sig, value) pair, else pass through."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        return value[1]
    return value


def _file_from_uris(uris) -> str:
    for uri in uris or []:
        parsed = urlparse(str(uri))
        if parsed.scheme == "file" and parsed.path:
            return unquote(parsed.path)
    return ""


def pick_file(
    title: str = "Pick a file",
    accept_label: str = "Open",
    timeout: float = 600.0,
    _open=None,
) -> str:
    """Show the desktop-native file dialog. Returns a path, or ''."""
    from jeepney.io.blocking import open_dbus_connection

    opener = _open or open_dbus_connection
    try:
        conn = opener()
    except Exception as e:
        log.debug("portal: no bus: %s", e)
        return ""
    try:
        return _pick_via(conn, title, accept_label, timeout)
    except Exception as e:
        log.debug("portal: pick failed: %s", e)
        return ""
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _pick_via(conn, title: str, accept_label: str, timeout: float) -> str:
    from jeepney import DBusAddress, MessageType, new_method_call

    bus = DBusAddress("/org/freedesktop/DBus", "org.freedesktop.DBus", "org.freedesktop.DBus")
    # open_dbus_connection already said Hello: the name is on the conn.
    unique = (getattr(conn, "unique_name", "") or "").lstrip(":").replace(".", "_")
    if not unique:
        log.debug("portal: saying Hello")
        hello = conn.send_and_get_reply(new_method_call(bus, "Hello"), timeout=10)
        unique = (hello.body[0] if hello.body else "").lstrip(":").replace(".", "_")
    if not unique:
        return ""
    token = f"tkarcade{random.randrange(1 << 30)}"
    req_path = f"/org/freedesktop/portal/desktop/request/{unique}/{token}"
    match = f"type='signal',interface='{_REQUEST_IFACE}',member='Response',path='{req_path}'"
    log.debug("portal: AddMatch %s", req_path)
    conn.send_and_get_reply(new_method_call(bus, "AddMatch", "s", (match,)), timeout=10)

    portal = DBusAddress(_DESKTOP[1], _DESKTOP[0], _DESKTOP[0])
    options = {
        "handle_token": ("s", token),
        "accept_label": ("s", accept_label),
        "modal": ("b", True),
    }
    log.debug("portal: OpenFile %r", title)
    reply = conn.send_and_get_reply(
        new_method_call(portal, "OpenFile", "ssa{sv}", ("", title, options)),
        timeout=30,
    )
    handle = reply.body[0] if reply.body else ""
    # The reply handle is the request path (spec); trust it over our guess.
    req_path = handle or req_path
    log.debug("portal: waiting for Response on %s", req_path)
    deadline = time.monotonic() + max(timeout, 1.0)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ""
        msg = conn.receive(timeout=remaining)
        if msg is None:
            return ""
        fields = msg.header.fields
        if (
            msg.header.message_type == MessageType.signal
            and fields.get(1, "") == req_path
            and fields.get(3, "") == "Response"
            and msg.body
        ):
            response, results = msg.body[0], msg.body[1] if len(msg.body) > 1 else {}
            if int(response) != 0:
                return ""  # user cancelled (or portal gave up)
            return _file_from_uris(_unwrap(results.get("uris")))
