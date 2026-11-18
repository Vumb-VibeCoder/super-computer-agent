"""Thế giới màn hình giả lập (sao từ fovea.py của phiên tối ưu) dùng để kiểm thử fovea_live mà không cần desktop thật."""
import random

import numpy as np

# ----------------------------------------------------------- synthetic world
W_, H_ = 1280, 768
SIDE = 240


def mk_chrome(name, h, w, seed):
    r = np.random.default_rng(seed)
    a = np.zeros((h, w), np.uint8)
    for y in range(6, h - 6, 14):
        for x in range(8, w - 40, 60):
            if r.random() < 0.7:
                a[y:y + 8, x:x + int(r.integers(20, 52))] = r.integers(60, 255, (8, 1))
    return a


class World:
    def __init__(self, seed):
        self.r = random.Random(seed); self.nr = np.random.default_rng(seed)
        self.top_browser = mk_chrome("tb", 96, W_, 1); self.top_editor = mk_chrome("te", 96, W_, 2)
        self.side_a = mk_chrome("sa", 624, SIDE, 3); self.side_b = mk_chrome("sb", 624, SIDE, 4)
        self.task = mk_chrome("tk", 48, W_, 5)
        self.scenes = {}
        specs = {"chat": ("tb", "sa", 11), "reddit": ("tb", "sb", 12), "editor": ("te", "sa", 13), "term": ("te", "sb", 14)}
        for k, (t, s, sd) in specs.items():
            self.scenes[k] = dict(top=t, side=s, seed=sd, ver=0, scroll=0, cur_lines=set())
        self.cur = "chat"; self.tick = 0; self.popup = None

    def line(self, seed, ver):
        r = np.random.default_rng(seed * 7919 + ver)
        row = np.zeros((16, W_ - SIDE), np.uint8)
        x = 12
        while x < W_ - SIDE - 80:
            w = int(r.integers(14, 70)); row[3:12, x:x + w] = r.integers(70, 255, (9, w), dtype=np.uint8) if r.random() < .9 else 0
            x += w + 8
        return row

    def render(self):
        s = self.scenes[self.cur]; a = np.zeros((H_, W_), np.uint8)
        a[:96] = self.top_browser if s["top"] == "tb" else self.top_editor
        a[96:720, :SIDE] = self.side_a if s["side"] == "sa" else self.side_b
        a[720:] = self.task
        a[730:742, 1180:1180 + 40] = (self.tick * 37) % 200 + 40     # clock
        first = s["scroll"] // 16
        for i in range(39):
            ln = first + i
            ver = s["ver"] if ln in s["cur_lines"] else 0
            a[96 + i * 16:96 + (i + 1) * 16, SIDE:] = self.line(s["seed"] * 10000 + ln, ver)
        if self.popup:
            y, x, h, w = self.popup
            a[y:y + h, x:x + w] = self.nr.integers(30, 255, (h, w), dtype=np.uint8) // 2 + 100
        return a

    def action(self):
        r = self.r; s = self.scenes[self.cur]; self.tick += 1
        k = r.choices(["idle", "type", "scroll", "switch", "popup", "live"], [2, 3, 4, 3, 1, 2])[0]
        exp = None
        if k == "type":
            ln = s["scroll"] // 16 + r.randint(2, 30); s["ver"] += 1; s["cur_lines"].add(ln)
            exp = ("changed", (96 + (ln - s["scroll"] // 16) * 16, 96 + (ln - s["scroll"] // 16 + 1) * 16, SIDE, W_))
        elif k == "scroll":
            s["scroll"] = max(0, s["scroll"] + 16 * r.choice([-12, -5, -2, 3, 6, 10, 20]))
        elif k == "switch":
            self.cur = r.choice([n for n in self.scenes if n != self.cur]); self.popup = None
        elif k == "popup":
            self.popup = None if self.popup else (200, 400, 220, 520)
        elif k == "live":                                 # revisit-style drift: new content lands
            s["ver"] += 1
            for _ in range(r.randint(2, 6)): s["cur_lines"].add(s["scroll"] // 16 + r.randint(0, 38))
        return k, exp
