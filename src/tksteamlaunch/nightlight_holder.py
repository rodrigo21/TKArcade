"""Persistent KDE NightLight inhibit holder.

Holds org.kde.KWin.NightLight.inhibit() for the whole game session.
Requires `jeepney` (MIT). Prints "cookie=N" on stdout when inhibited,
then waits for SIGTERM/SIGINT and calls uninhibit(cookie).

Usage: python -m tksteamlaunch.nightlight_holder
"""

from __future__ import annotations

import signal
import sys
import threading


def main() -> int:
    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        print("ERROR: jeepney not installed, cannot hold NightLight inhibit", flush=True)
        return 2

    addr = DBusAddress(
        object_path="/org/kde/KWin/NightLight",
        bus_name="org.kde.KWin",
        interface="org.kde.KWin.NightLight",
    )
    stop = threading.Event()

    def _handler(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception as e:
        print(f"ERROR: cannot connect to session bus: {e}", flush=True)
        return 3

    try:
        reply = conn.send_and_get_reply(new_method_call(addr, "inhibit"))
        cookie = int(reply.body[0])
    except Exception as e:
        print(f"ERROR: inhibit call failed: {e}", flush=True)
        return 4

    print(f"cookie={cookie}", flush=True)
    # Block until signal. stdin close also stops (launcher killed pipe).
    try:
        while not stop.is_set():
            if stop.wait(0.5):
                break
    finally:
        try:
            conn.send_and_get_reply(
                new_method_call(addr, "uninhibit", signature="u", body=(cookie,))
            )
            print(f"uninhibited cookie={cookie}", flush=True)
            rc = 0
        except Exception as e:
            print(f"ERROR: uninhibit failed: {e}", flush=True)
            rc = 5
    return rc


if __name__ == "__main__":
    sys.exit(main())
