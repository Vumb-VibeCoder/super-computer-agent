"""Offline, Ed25519-signed license verification.

Verifies a license key entirely offline against an embedded public key,
enforces expiry, and enforces per-key machine and concurrent-thread/
process limits using small local state files (no network call).

This module is shipped as part of the public package (it only contains
the PUBLIC key). The matching PRIVATE key and the key-issuing tool live
in licensor-tools/, which is NOT part of this repository's public
distribution — see PROPRIETARY_EULA.md Section 3 and the "Implementation
notes" at the end of that file.
"""
from __future__ import annotations

import base64
import contextlib
import dataclasses
import json
import os
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .machine_id import get_machine_id

# -----------------------------------------------------------------------
# EMBEDDED PUBLIC KEY — replace this placeholder with the real public key
# produced by `licensor-tools/keygen.py` BEFORE building the release that
# gets compiled into canvas_core/pixel_grid_core. This value is meant to
# be public; it is what lets anyone *verify* a key, not mint one.
# -----------------------------------------------------------------------
PUBLIC_KEY_B64 = "OQo1NcfdH8paPy+FS9xLRNYmR/U3bkYowRGkag/JPGw="


class LicenseError(RuntimeError):
    """Raised whenever a license fails verification, for any reason."""


@dataclasses.dataclass(frozen=True)
class LicenseInfo:
    key_id: str
    licensee: str
    issued_at: int
    expires_at: int | None
    max_machines: int
    max_threads: int


def _load_public_key() -> Ed25519PublicKey:
    if PUBLIC_KEY_B64.startswith("REPLACE_ME"):
        raise LicenseError(
            "This build has no embedded public key (PUBLIC_KEY_B64 is a "
            "placeholder). Run licensor-tools/keygen.py once, paste the "
            "printed public key into licensing/verify.py, then rebuild."
        )
    raw = base64.b64decode(PUBLIC_KEY_B64)
    return Ed25519PublicKey.from_public_bytes(raw)


def _default_key_path() -> Path:
    env = os.environ.get("SCA_LICENSE_KEY")
    if env:
        return Path(env)
    return Path.home() / ".super-computer-agent" / "license.lickey"


def _state_dir(key_id: str) -> Path:
    base = Path(os.environ.get("SCA_LICENSE_STATE_DIR") or (Path.home() / ".super-computer-agent"))
    d = base / "state" / key_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_key_file(path: Path) -> tuple[dict, bytes, bytes]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise LicenseError(f"Cannot read license key file {path}: {e}") from e

    try:
        payload_b64, sig_b64 = text.split(".", 1)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + "==")
        payload = json.loads(payload_bytes)
    except Exception as e:  # noqa: BLE001 - deliberately broad: any malformed key is just invalid
        raise LicenseError(f"License key file {path} is malformed: {e}") from e

    return payload, payload_bytes, sig_bytes


def _verify_signature(payload_bytes: bytes, sig_bytes: bytes) -> None:
    pubkey = _load_public_key()
    try:
        pubkey.verify(sig_bytes, payload_bytes)
    except InvalidSignature as e:
        raise LicenseError(
            "License key signature is invalid (tampered, corrupted, or "
            "not issued by the real Licensor key)."
        ) from e


def _check_expiry(payload: dict) -> None:
    expires_at = payload.get("expires_at")
    if expires_at is not None and time.time() > float(expires_at):
        raise LicenseError("License key has expired.")


def _check_machine_binding(payload: dict, key_id: str) -> None:
    max_machines = int(payload["max_machines"])
    state_file = _state_dir(key_id) / "bound_machines.json"

    bound: list[str] = []
    if state_file.exists():
        try:
            bound = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bound = []

    mid = get_machine_id()
    if mid in bound:
        return

    if len(bound) >= max_machines:
        raise LicenseError(
            f"License key {key_id} is already bound to its maximum of "
            f"{max_machines} machine(s). This machine is not one of them."
        )

    bound.append(mid)
    state_file.write_text(json.dumps(bound), encoding="utf-8")


@contextlib.contextmanager
def _thread_slot(key_id: str, max_threads: int):
    """Hold one concurrency slot for the lifetime of the `with` block.

    Implemented with plain lock files so it works across both threads
    and separate OS processes without extra dependencies. Stale slots
    from a crashed process are reclaimed after SCA_LICENSE_SLOT_TTL
    seconds (default 1 hour).
    """
    ttl = float(os.environ.get("SCA_LICENSE_SLOT_TTL", "3600"))
    slots_dir = _state_dir(key_id) / "slots"
    slots_dir.mkdir(parents=True, exist_ok=True)

    # Reap stale slot files before counting.
    now = time.time()
    for f in slots_dir.glob("*.slot"):
        try:
            if now - f.stat().st_mtime > ttl:
                f.unlink(missing_ok=True)
        except OSError:
            pass

    existing = list(slots_dir.glob("*.slot"))
    if len(existing) >= max_threads:
        raise LicenseError(
            f"License key {key_id} already has {max_threads} active "
            "thread/process slot(s) in use; refusing to start another."
        )

    slot_path = slots_dir / f"{os.getpid()}-{uuid.uuid4().hex}.slot"
    slot_path.write_text(str(now), encoding="utf-8")
    try:
        yield
    finally:
        slot_path.unlink(missing_ok=True)


def check_license(key_path: str | os.PathLike | None = None) -> LicenseInfo:
    """Verify the license key at `key_path` (or the default location).

    Raises LicenseError on any failure (missing file, bad signature,
    expired, wrong machine, too many bound machines). Does NOT hold a
    concurrency slot by itself — pair this with `license_slot()` around
    the code path that actually uses canvas_core/pixel_grid_core.
    """
    path = Path(key_path) if key_path else _default_key_path()
    if not path.exists():
        raise LicenseError(
            f"No license key found at {path}. Set SCA_LICENSE_KEY to point "
            "at your .lickey file, or request one from the Licensor "
            "(see PROPRIETARY_EULA.md)."
        )

    payload, payload_bytes, sig_bytes = _parse_key_file(path)
    _verify_signature(payload_bytes, sig_bytes)
    _check_expiry(payload)
    key_id = str(payload["key_id"])
    _check_machine_binding(payload, key_id)

    return LicenseInfo(
        key_id=key_id,
        licensee=str(payload.get("licensee", "")),
        issued_at=int(payload.get("issued_at", 0)),
        expires_at=payload.get("expires_at"),
        max_machines=int(payload["max_machines"]),
        max_threads=int(payload["max_threads"]),
    )


@contextlib.contextmanager
def license_slot(key_path: str | os.PathLike | None = None):
    """Convenience wrapper: verify the license, then hold a concurrency
    slot for the duration of the `with` block.

    Usage, at the top of whatever imports the compiled canvas_core /
    pixel_grid_core module::

        from super_computer_agent.licensing import license_slot
        with license_slot():
            from . import canvas_core  # the compiled .pyd/.so
    """
    info = check_license(key_path)
    with _thread_slot(info.key_id, info.max_threads):
        yield info
