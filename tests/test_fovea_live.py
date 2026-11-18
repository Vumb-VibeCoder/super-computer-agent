"""fovea_live (compiled core; skipped without the engine and a license key): replay the canvas from the COPY/LOW/SCROLL/RECALL
lines the way a model does and compare it with the real frame, plus edge cases (minimised/closed window, black frame, mss
failure, empty frame) and a bounded-memory soak. No real desktop needed."""
import os
import sys

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("mcp")
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="fovea_live dùng ctypes.windll")

sys.path.insert(0, os.path.dirname(__file__))
from _fovea_world import World  # noqa: E402
from _engine import require_engine  # noqa: E402
require_engine("super_computer_agent.plugins._compiled.fovea_live")
from super_computer_agent.plugins._compiled import fovea_live as FL  # noqa: E402

T, LT = FL.T, FL.LT
WIN = (111, 0, (0, 0, 1920, 1080), 1)
NOWIN = (0, 0, (0, 0, 0, 0), 0)


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(FL, "OUT", str(tmp_path / "fovea_live"))
    monkeypatch.setattr(FL, "KEEP", 10 ** 6)                 # test đọc lại ảnh cũ từ đĩa; model thật giữ ảnh trong ngữ cảnh
    monkeypatch.setattr(FL, "_usig", lambda *a, **k: None)    # không đụng UIA thật với hwnd giả
    FL.start(settle_ms=0)
    yield
    FL.stop()


def replay(recs, canvas, cache, hist):
    for r in recs:
        if r[0] == "recall":
            canvas = hist[r[1]].copy()
        elif r[0] == "canvas":
            canvas = np.zeros((r[2], r[1], 3), np.uint8)
        elif r[0] == "scroll":
            (y0, y1, x0, x1), s = r[1], r[2]
            seg = canvas[y0:y1, x0:x1].copy(); n = y1 - y0; out = np.full_like(seg, 255)
            if s > 0: out[:n - s] = seg[s:]
            else: out[-s:] = seg[:n + s]
            canvas[y0:y1, x0:x1] = out
        elif r[0] in ("copy", "low"):
            kind, path, y, x, n, rr, c = r
            im = cache.setdefault(path, np.asarray(Image.open(os.path.join(FL.OUT, os.path.basename(path))).convert("RGB")))
            for i in range(n):
                if kind == "copy":
                    canvas[y * T:(y + 1) * T, (x + i) * T:(x + i + 1) * T] = im[rr * T:(rr + 1) * T, (c + i) * T:(c + i + 1) * T]
                else:
                    t = im[rr * LT:(rr + 1) * LT, (c + i) * LT:(c + i + 1) * LT]
                    canvas[y * T:(y + 1) * T, (x + i) * T:(x + i + 1) * T] = np.repeat(np.repeat(t, T // LT, 0), T // LT, 1)
    return canvas


def run(seed, steps, budget):
    FL.start(budget_tok=budget, settle_ms=0)
    w = World(seed); canvas = None; cache = {}; hist = {}; maxd = 0; blurry = 0; toks = []
    for _ in range(steps):
        w.action(); g = w.render(); frame = np.stack([g, g, g], 2)
        _txt, recs, cost = FL.step_frame(frame); toks.append(cost)
        canvas = replay(recs, canvas, cache, hist); hist[FL._S["n"]] = canvas.copy()
        d = np.abs(canvas.astype(int) - FL._S["prev"].astype(int)).max(2)
        if budget == 0: maxd = max(maxd, int(d.max()))
        else: blurry = max(blurry, int((d > 3).sum() // (T * T)))
    return sum(toks), maxd, blurry


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_replayed_canvas_matches_real_frame_lossless(seed):
    total, maxd, _ = run(seed, 40, 0)
    assert maxd <= 3, f"canvas dựng lại lệch khung thật tối đa {maxd}"     # Q=2: ngưỡng so/băm bỏ 2 bit thấp
    assert total / 40 < 1500                                              # tiết kiệm so với gửi nguyên khung (~1.3k tok/khung)


@pytest.mark.parametrize("seed", [1, 2])
def test_budgeted_mode_only_blurs_does_not_corrupt(seed):
    total, _, blurry = run(seed, 30, 300)
    assert total > 0 and blurry < 400                                     # có ô mờ (LOW) nhưng không hỏng cả canvas


def test_black_frame_is_wait_not_history():
    rs = np.random.RandomState(0); real = rs.randint(0, 255, (1080, 1920, 3)).astype(np.uint8); blk = np.zeros_like(real)
    FL.step_frame(real, WIN, WIN); FL.step_frame(real, WIN, WIN)
    n, hist, store = FL._S["n"], len(FL._S["hist"]), len(FL._S["store"])
    for w in (WIN, NOWIN):
        txt, recs, _ = FL.step_frame(blk, w, w)
        assert txt.startswith("WAIT") and recs[0][0] == "wait"
    assert (FL._S["n"], len(FL._S["hist"]), len(FL._S["store"])) == (n, hist, store)   # khung đen không lọt vào lịch sử/kho
    txt, _, _ = FL.step_frame(real, WIN, WIN)
    assert not txt.startswith(("WAIT", "DROP"))                                         # khung thật quay lại: chạy bình thường


@pytest.mark.parametrize("rect,hwnd", [((-32000, -32000, -31840, -31976), 5),       # thu nhỏ
                                       ((0, 0, 0, 0), 5),                           # rect 0x0 (cửa sổ đã đóng)
                                       ((0, 0, 0, 0), 0)])                          # không có foreground
def test_unusable_window_waits_instead_of_crashing(rect, hwnd):
    rs = np.random.RandomState(1); real = rs.randint(0, 255, (1080, 1920, 3)).astype(np.uint8)
    FL.step_frame(real, WIN, WIN)
    w = (hwnd, 0, rect, 1)
    txt, recs, cost = FL.step_frame(real, w, w)
    assert txt.startswith("WAIT") and cost == 0.0 and FL._S["waits"] >= 1


def test_capture_failure_and_empty_frame_wait(monkeypatch):
    def boom():
        raise RuntimeError("mss: screen grab failed")
    monkeypatch.setattr(FL, "_grab", boom)
    fr, w0, w1 = FL.grab_stable()
    assert fr is None
    assert FL.step_frame(fr, w0, w1)[0].startswith("WAIT")
    assert FL.step_frame(np.zeros((0, 0, 3), np.uint8), WIN, WIN)[0].startswith("WAIT")


def test_bound_window_mismatch_drops_without_applying():
    rs = np.random.RandomState(2); real = rs.randint(0, 255, (1080, 1920, 3)).astype(np.uint8)
    FL.start(bind_hwnd=111, settle_ms=0); FL.step_frame(real, WIN, WIN)
    other = (222, 0, (0, 0, 1920, 1080), 2)
    txt, recs, _ = FL.step_frame(real, other, other)
    assert txt.startswith("DROP") and recs[0][0] == "drop"


def test_soak_keeps_store_history_and_pngs_bounded(monkeypatch):
    monkeypatch.setattr(FL, "STORE_MAX", 800); monkeypatch.setattr(FL, "KEEP", 20)
    rs = np.random.RandomState(0)
    docs = [rs.randint(0, 256, (1600, 640, 3)).astype(np.uint8) for _ in range(3)]
    w = (111, 0, (0, 0, 640, 480), 1); cur = 0; off = [0, 0, 0]
    FL.start(settle_ms=0)
    for i in range(150):
        if rs.rand() < 0.3: cur = int(rs.randint(3))
        else: off[cur] = int(np.clip(off[cur] + rs.choice([-1, 1]) * rs.randint(60, 400), 0, 1600 - 480))
        FL.step_frame(docs[cur][off[cur]:off[cur] + 480], w, w)
        assert len(FL._S["store"]) <= FL.STORE_MAX + 400                       # trần ô nhớ (cắt 80% khi vượt) không để RAM phình
    assert len(FL._S["hist"]) <= FL.HIST
    assert len(FL._S["hh"]) <= 128
    assert len([f for f in os.listdir(FL.OUT) if f.endswith(".png")]) <= FL.KEEP


def test_expect_does_not_crash_and_tracks_changes(monkeypatch):
    """Hồi quy: fovea_expect từng luôn văng TypeError vì ghi đè tham số chiều rộng w bằng kết quả _fg()."""
    rs = np.random.RandomState(3); a = rs.randint(0, 255, (480, 640, 3)).astype(np.uint8)
    cur = {"f": a}
    monkeypatch.setattr(FL, "_grab", lambda: cur["f"])
    monkeypatch.setattr(FL, "_fg", lambda: (111, 0, (0, 0, 640, 480), 1))
    FL.step_frame(a, (111, 0, (0, 0, 640, 480), 1), (111, 0, (0, 0, 640, 480), 1))
    assert FL.expect(0, 0, 200, 100, "same").startswith("OK")
    assert FL.expect(0, 0, 200, 100, "changed").startswith("NO")
    b = a.copy(); b[10:40, 10:40] = 255 - b[10:40, 10:40]
    cur["f"] = b
    assert FL.expect(0, 0, 200, 100, "changed").startswith("OK")
    assert FL.expect(300, 300, 100, 100, "changed").startswith("NO")                  # vùng khác không đổi
    assert "ngoài màn hình" in FL.expect(5000, 5000, 10, 10)
