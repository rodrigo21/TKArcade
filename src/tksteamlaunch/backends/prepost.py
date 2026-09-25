"""pre/post hook execution (option B: executable + args, optional shell)."""
from __future__ import annotations

import logging
import os
import shlex
import subprocess

log = logging.getLogger("tksteamlaunch.prepost")


def build_cmd(command: str, args: list[str], run_in_shell: bool) -> list[str] | str:
    if not command:
        return [] if not run_in_shell else ""
    if run_in_shell:
        extra = " ".join(shlex.quote(a) for a in (args or []))
        return f"{command} {extra}".strip()
    return [command, *(args or [])]


def run_hook(
    name: str,
    command: str,
    args: list[str],
    timeout: int = 60,
    run_in_shell: bool = False,
    extra_env: dict | None = None,
) -> int:
    """Run a hook blocking. Returns exit code, -1 if skipped, -2 on timeout/error."""
    if not (command or "").strip():
        return -1
    cmd = build_cmd(command, args or [], run_in_shell)
    log.info("%s hook: %r", name, cmd)
    env = dict(os.environ)
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, timeout=timeout, env=env)
        else:
            r = subprocess.run(cmd, shell=False, timeout=timeout, env=env)
        log.info("%s hook exit=%s", name, r.returncode)
        return r.returncode
    except subprocess.TimeoutExpired:
        log.error("%s hook timed out after %ss", name, timeout)
        return -2
    except FileNotFoundError:
        log.error("%s hook not found: %r", name, cmd)
        return -2
    except Exception as e:  # noqa: BLE001
        log.error("%s hook failed: %s", name, e)
        return -2
