"""Command line: serve | screenshot | windows | tree | doctor."""
import argparse
import json
import sys

from . import __version__


def _doctor() -> int:
    import importlib
    ok = True
    print(f"super-computer-agent {__version__} | python {sys.version.split()[0]} | {sys.platform}")
    for mod, why in (("numpy", "grid + canvas"), ("PIL", "images"), ("cv2", "canvas (opencv-python)"),
                     ("mss", "fast capture"), ("mcp", "MCP server"), ("pywinauto", "UI tree (Windows only)")):
        try:
            m = importlib.import_module(mod)
            print(f"  ok       {mod:10s} {getattr(m, '__version__', '')}  ({why})")
        except Exception as exc:
            required = not (mod == "pywinauto" and sys.platform != "win32")
            ok &= not required
            print(f"  {'MISSING ' if required else 'skipped '} {mod:10s} ({why}): {exc}")
    try:
        from . import screenshot
        w, h = screenshot.grab().size
        print(f"  ok       screenshot {w}x{h}")
    except Exception as exc:
        ok = False
        print(f"  FAILED   screenshot: {type(exc).__name__}: {exc}")
    try:
        from .server import build_server
        import asyncio
        n = len(asyncio.run(build_server().list_tools()))
        print(f"  ok       server builds, {n} tools")
    except Exception as exc:
        ok = False
        print(f"  FAILED   server: {type(exc).__name__}: {exc}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="super-computer-agent", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the MCP server (stdio by default)")
    s.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    sh = sub.add_parser("screenshot", help="save a screenshot of all monitors")
    sh.add_argument("-o", "--output", help="PNG path (default: <SCA_OUTPUT_DIR>/screenshots/...)")
    sub.add_parser("windows", help="list inspectable windows as JSON")
    t = sub.add_parser("tree", help="dump the UIA tree of a window as JSON")
    t.add_argument("hwnd", type=int)
    t.add_argument("--depth", type=int, default=4)
    sub.add_parser("doctor", help="check dependencies, screen capture and server start-up")
    a = ap.parse_args(argv)

    if a.cmd == "serve":
        from .server import run
        print(f"super-computer-agent {__version__}: serving on {a.transport}", file=sys.stderr)  # never stdout: stdio is the protocol
        run(a.transport, a.host, a.port)
        return 0
    if a.cmd == "screenshot":
        from . import screenshot
        print(screenshot.save(a.output))
        return 0
    if a.cmd == "windows":
        from . import uia
        print(json.dumps(uia.list_windows(), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "tree":
        from . import uia
        print(json.dumps(uia.get_tree(a.hwnd, a.depth), ensure_ascii=False, indent=2))
        return 0
    return _doctor()
