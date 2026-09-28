"""TKSteamLaunch - minimal Steam launch wrapper (GPLv3)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tksteamlaunch")
except PackageNotFoundError:
    # Uninstalled source tree (e.g. PYTHONPATH runs): never confuse with a release.
    __version__ = "0.0.0+src"
