"""TKSteamLaunch - minimal Steam launch wrapper (GPLv3)."""

from __future__ import annotations


def __getattr__(name: str) -> str:
    # Lazy version lookup (PEP 562): importing the package must stay cheap
    # because the launcher resolves it on every game start.
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("tksteamlaunch")
        except PackageNotFoundError:
            # Uninstalled source tree (e.g. PYTHONPATH runs): never confuse with a release.
            return "0.0.0+src"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
