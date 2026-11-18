"""UIA guard của fovea_live: phải fail-closed giống uia.py. Phần chạy cửa sổ thật cần SCA_INTEGRATION=1."""
import asyncio
import ctypes
import os
import subprocess
import sys
import threading
import time

import pytest

pytest.importorskip("mcp")
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="UIA chỉ có trên Windows")

from super_computer_agent import uia  # noqa: E402
from _engine import require_engine  # noqa: E402
require_engine("super_computer_agent.plugins._compiled.fovea_live")
from super_computer_agent.plugins._compiled import fovea_live as F  # noqa: E402


@pytest.fixture
def allow_all(monkeypatch):
    monkeypatch.delenv("SCA_ALLOWED_PROCESSES", raising=False)
    monkeypatch.setattr(uia, "process_path", lambda pid: r"C:\\apps\\demo.exe")
    monkeypatch.setattr(uia, "elevated_process", lambda pid: False)
    monkeypatch.setattr(uia, "is_sensitive", lambda title, name: False)
    monkeypatch.setattr(uia, "allowed_processes", lambda: set())
    monkeypatch.setattr(F, "_title", lambda hwnd: "demo")


def test_uia_ok_allows_a_normal_window(allow_all):
    assert F._uia_ok(10, 20) is True


def test_uia_ok_fails_closed(allow_all, monkeypatch):
    assert F._uia_ok(0, 20) is False and F._uia_ok(10, 0) is False
    monkeypatch.setattr(uia, "is_sensitive", lambda title, name: True)
    assert F._uia_ok(10, 20) is False                                  # cửa sổ nhạy cảm
    monkeypatch.setattr(uia, "is_sensitive", lambda title, name: False)
    monkeypatch.setattr(uia, "elevated_process", lambda pid: True)
    assert F._uia_ok(10, 20) is False                                  # chạy quyền admin
    monkeypatch.setattr(uia, "elevated_process", lambda pid: False)
    monkeypatch.setattr(uia, "allowed_processes", lambda: {"other.exe"})
    assert F._uia_ok(10, 20) is False                                  # ngoài SCA_ALLOWED_PROCESSES
    monkeypatch.setattr(uia, "allowed_processes", lambda: {"demo.exe"})
    assert F._uia_ok(10, 20) is True
    monkeypatch.setattr(uia, "process_path", lambda pid: (_ for _ in ()).throw(OSError("x")))
    assert F._uia_ok(10, 20) is False                                  # lỗi bất kỳ -> chặn


def test_usig_returns_none_when_guard_blocks(allow_all, monkeypatch):
    monkeypatch.setattr(uia, "elevated_process", lambda pid: True)
    assert F._usig(10, pid=20) is None


@pytest.mark.skipif(os.environ.get("SCA_INTEGRATION") != "1", reason="set SCA_INTEGRATION=1")
def test_real_window_signature_and_threads():
    from ctypes import wintypes
    tk = ("import tkinter as t;r=t.Tk();r.title('sca_uia_probe');r.geometry('300x200+50+50');"
          "t.Button(r,text='ok').pack();t.Entry(r).pack();r.mainloop()")
    proc = subprocess.Popen([sys.executable, "-c", tk])
    user32 = ctypes.windll.user32
    hwnd = 0
    try:
        for _ in range(50):
            time.sleep(0.2)
            found = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def cb(h, _l):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == proc.pid and user32.IsWindowVisible(h):
                    found.append(int(h))
                return True
            user32.EnumWindows(cb, 0)
            if found:
                hwnd = found[0]
                break
        assert hwnd
        sig = F._usig(hwnd, pid=proc.pid)
        assert sig and sig[1] > 1 and F._usig(hwnd, pid=proc.pid) == sig   # ổn định giữa các lần đọc
        assert F._usig(hwnd, pid=1) is None                                # pid không đạt guard

        async def mixed():                                                 # như server: to_thread, chồng nhau
            async def one(fn):
                return await asyncio.wait_for(asyncio.to_thread(fn), 30)
            jobs = [one(lambda: uia.get_tree(hwnd)), one(lambda: F._usig(hwnd, pid=proc.pid)),
                    one(lambda: uia.get_tree(hwnd)), one(uia.list_windows), one(lambda: F._usig(hwnd, True, proc.pid))]
            return await asyncio.gather(*jobs)
        out = asyncio.run(mixed())
        assert all(o is not None for o in out)
    finally:
        proc.kill()
