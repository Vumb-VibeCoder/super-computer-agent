"""Derive a stable Machine ID for license binding.

We hash a small set of relatively stable, non-secret identifiers so the
on-disk license store never contains raw hardware identifiers, only a
hash of them. This is "good enough" binding for an offline licensing
scheme, not a tamper-proof hardware fingerprint.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys


def _win_volume_serial() -> str:
    try:
        out = subprocess.check_output(
            ["cmd", "/c", "vol", "C:"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if "Serial Number" in line:
                return line.split()[-1]
    except Exception:
        pass
    return ""


def _win_machine_guid() -> str:
    try:
        out = subprocess.check_output(
            [
                "reg",
                "query",
                r"HKLM\SOFTWARE\Microsoft\Cryptography",
                "/v",
                "MachineGuid",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "MachineGuid" in line:
                return line.strip().split()[-1]
    except Exception:
        pass
    return ""


def _cpu_identifier() -> str:
    return platform.processor() or platform.machine() or ""


def raw_components() -> list[str]:
    """The stable-but-not-secret identifiers we hash together.

    Kept as a separate function so a support script can print them for
    debugging ("why did my machine ID change?") without touching the
    hashing logic.
    """
    parts = [platform.node(), _cpu_identifier()]
    if sys.platform == "win32":
        parts += [_win_machine_guid(), _win_volume_serial()]
    return [p for p in parts if p]


def get_machine_id() -> str:
    """Return a stable hex digest identifying this machine.

    Changing hardware (new disk, reinstalled OS) can change this value;
    that's expected for an offline, hardware-bound license — it is the
    licensee's responsibility to request re-activation from the Licensor
    in that case (see PROPRIETARY_EULA.md, Section 3).
    """
    joined = "|".join(raw_components())
    if not joined:
        # Extremely degraded environment (e.g. heavily sandboxed): fall
        # back to hostname + platform string so the function never
        # raises, at the cost of weaker binding.
        joined = platform.node() + platform.platform()
    return hashlib.sha256(joined.encode("utf-8", "replace")).hexdigest()
