"""Public-side loader for the proprietary `fovea_live` binary.

The entire FOVEA implementation (content-addressed tile memory, scroll/recall
detection, UIA<->canvas cross-checks, and the tools fovea_start / fovea_step /
fovea_expect / fovea_look / fovea_status / fovea_stop) is proprietary and ships
only as a compiled extension module. See NOTICE and PROPRIETARY_EULA.md.

This file is the AGPL-3.0 public entry point: it holds no algorithm of its own,
only (1) a license check against the embedded public key in `licensing/verify.py`,
and (2) a path shim so Python can find the compiled module in `_compiled/`.
"""
import os

from ..licensing import LicenseError, license_slot

NAME = "fovea_live"
DESC = (
    "FOVEA live: fovea_start/fovea_step/fovea_expect/fovea_look/fovea_status/fovea_stop - content-addressed 32px tiles, "
    "atlas of unseen tiles, per-step token budget (proprietary core - needs a valid license key, see PROPRIETARY_EULA.md)"
)
# Same expression as the compiled core, so the server can name the image directory in NEXT hints
# without loading the binary (and so hints still work when the engine is disabled).
OUT = os.path.join(os.environ.get("SCA_OUTPUT_DIR", "outputs"), "fovea_live")

_core = None


def _load():
    global _core
    if _core is None:
        cm = license_slot()
        cm.__enter__()
        import atexit
        atexit.register(cm.__exit__, None, None, None)
        try:
            from ._compiled import fovea_live as _fl  # the compiled .pyd/.so
        except Exception as e:
            raise RuntimeError(f"cannot load fovea_live ({e})") from e
        _core = _fl
    return _core


def apply(ctx):
    """Forwards straight to the compiled module's own apply(ctx); all tool definitions live there, not here."""
    try:
        core = _load()
    except LicenseError as e:
        reason = str(e)  # `e` is deleted when the except block ends, so the lambda can't use it
        ctx.instructions(lambda: f"fovea_live: disabled, no valid license ({reason}); see PROPRIETARY_EULA.md")
        return
    core.apply(ctx)
