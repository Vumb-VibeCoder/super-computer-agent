"""Public-side loader for the proprietary `pixel_grid` binary.

Unlike canvas_live.py (where only the delta-compression core is
proprietary), the entire pixel_grid implementation — live screen grid,
accessibility-tree fusion, OS event hooks, and every tool it exposes
(live_start/live_stop/grid_now/fused_grid/tree_set/ui_fuse/describe/
changes_since/watch_until_change/wait_stable/zoom/crop/verify_action/
film_transients/film_at/events_since/wait_idle/calibrate_noise) — is
proprietary and ships only as a compiled extension module. See NOTICE
and PROPRIETARY_EULA.md.

This file is the AGPL-3.0 public entry point: it holds no algorithm of
its own, only (1) a license check against the embedded public key in
`licensing/verify.py`, and (2) a path shim so Python can find the
compiled module in `_compiled/` next to this file.
"""
from ..licensing import LicenseError, license_slot

NAME = "pixel_grid"
DESC = (
    "Màn hình live thành lưới màu thô ghép cây trợ năng: live_start/stop, grid_now, fused_grid, "
    "tree_set, describe, changes_since, watch_until_change, zoom, crop, calibrate_noise, wait_stable "
    "(proprietary core — cần license key hợp lệ, xem PROPRIETARY_EULA.md)"
)

_core = None


def _load():
    global _core
    if _core is None:
        cm = license_slot()
        cm.__enter__()
        import atexit
        atexit.register(cm.__exit__, None, None, None)
        try:
            from ._compiled import pixel_grid as _pg  # the compiled .pyd/.so
        except Exception as e:
            raise RuntimeError(f"không nạp được pixel_grid ({e})") from e
        _core = _pg
    return _core


def apply(ctx):
    """Forwards straight to the compiled module's own apply(ctx); all tool
    definitions (live_start, grid_now, fused_grid, ...) live there, not here."""
    try:
        core = _load()
    except LicenseError as e:
        ctx.instructions(lambda: f"pixel_grid: tắt, chưa có license hợp lệ ({e}); xem PROPRIETARY_EULA.md")
        return
    core.apply(ctx)
