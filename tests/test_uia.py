from types import SimpleNamespace

import pytest

from super_computer_agent import uia


def test_sensitive_detection():
    assert uia.is_sensitive("Bitwarden - Vault", "browser.exe")
    assert uia.is_sensitive("anything", "C:\\Windows\\System32\\consent.exe")
    assert not uia.is_sensitive("Untitled - Notepad", "notepad.exe")


class Info:
    def __init__(self, name="", ctype="Button", aid="", pw=False):
        self.name, self.control_type, self.automation_id, self.is_password = name, ctype, aid, pw
        self.rectangle = SimpleNamespace(left=0, top=0, right=10, bottom=10)


class El:
    def __init__(self, name="", kids=(), **kw):
        self.element_info = Info(name, **kw)
        self._kids = list(kids)

    def children(self):
        return self._kids


class Win(El):
    handle = 42

    def exists(self, timeout=0):
        return True


class Desktop:
    def __init__(self, win):
        self.win = win

    def windows(self):
        return [self.win]

    def window(self, handle):
        return self.win


SAFE = {"hwnd": 42, "pid": 1, "title": "t", "process_name": "app.exe", "process_path": "c:\\app.exe", "sensitive": False, "elevated": False}


@pytest.fixture
def desktop(monkeypatch):
    def install(win, meta=SAFE):
        uia.set_backend_factory(lambda: Desktop(win))
        monkeypatch.setattr(uia, "window_meta", lambda w: dict(meta))
    yield install
    uia.set_backend_factory(None)


def test_tree_shape_and_password_redaction(desktop):
    desktop(Win("main", [El("OK"), El("OK"), El("secret", pw=True)]))
    t = uia.get_tree(42, 2)
    assert t["count"] == 4 and t["elements"][0]["parent"] == -1
    pw = [e for e in t["elements"] if e["is_password"]][0]
    assert pw["name"] == uia.REDACTED
    assert 1 in t["visual_disambiguation_needed"] and 2 in t["visual_disambiguation_needed"]  # duplicate names
    assert pw["index"] not in t["visual_disambiguation_needed"]


def test_depth_and_size_limits(desktop):
    deep = El("leaf")
    for i in range(8):
        deep = El(f"n{i}", [deep])
    desktop(Win("root", [deep]))
    assert max(e["depth"] for e in uia.get_tree(42, 2)["elements"]) == 2
    desktop(Win("root", [El(f"c{i}") for i in range(900)]))
    assert uia.get_tree(42, 1)["count"] <= uia.MAX_ELEMENTS


def test_sensitive_and_unlisted_windows_are_refused(desktop, monkeypatch):
    desktop(Win("x"), dict(SAFE, sensitive=True))
    with pytest.raises(PermissionError):
        uia.get_tree(42)
    assert uia.list_windows()["count"] == 0
    desktop(Win("x"))
    monkeypatch.setenv("SCA_ALLOWED_PROCESSES", "other.exe")
    with pytest.raises(PermissionError):
        uia.get_tree(42)
    monkeypatch.setenv("SCA_ALLOWED_PROCESSES", "APP.exe")
    assert uia.get_tree(42)["count"] == 1
