"""Full-desktop screenshot (all monitors) without any dialog or GUI."""
from __future__ import annotations

import os
import sys
import time

from PIL import Image

KEEP = 40  # screenshots kept on disk; older ones are deleted


def _dpi_aware() -> None:
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()  # otherwise a >100% scaled display is captured at the wrong size
    except Exception:
        pass


def grab() -> Image.Image:
    """Capture every monitor as one RGB image. PIL.ImageGrab first, mss as fallback."""
    if sys.platform == "win32":
        _dpi_aware()
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True) if sys.platform == "win32" else ImageGrab.grab()
        return img.convert("RGB")
    except Exception:
        import mss
        factory = getattr(mss, "MSS", None) or mss.mss
        with factory() as sct:
            raw = sct.grab(sct.monitors[0])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def out_dir() -> str:
    return os.path.join(os.environ.get("SCA_OUTPUT_DIR", "outputs"), "screenshots")


def save(path: str | None = None, keep: int = KEEP) -> str:
    """Capture and write a PNG. Without `path` the file goes to <SCA_OUTPUT_DIR>/screenshots/ and old ones are pruned."""
    img = grab()
    pruned = path is None
    if path is None:
        os.makedirs(out_dir(), exist_ok=True)
        path = os.path.join(out_dir(), f"screenshot_{int(time.time() * 1000)}.png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path, format="PNG")
    if pruned:
        d = out_dir()
        files = sorted((f for f in os.listdir(d) if f.startswith("screenshot_") and f.endswith(".png")),
                       key=lambda f: os.path.getmtime(os.path.join(d, f)))
        for old in files[:-keep] if keep > 0 else []:
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass
    return os.path.abspath(path)
