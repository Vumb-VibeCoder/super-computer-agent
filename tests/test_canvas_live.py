import os

import numpy as np
import pytest

from _engine import require_engine
from super_computer_agent.plugins import canvas_live


@pytest.fixture
def live(tmp_path, monkeypatch):
    require_engine("super_computer_agent.canvas._compiled.canvas_v7",
                   "super_computer_agent.canvas._compiled.canvas_delta2", module_level=False)
    monkeypatch.setattr(canvas_live, "OUT", str(tmp_path / "canvas"))
    canvas_live.start(max_side=512, settle_ms=0)
    yield canvas_live
    canvas_live.stop()


def frame(seed=0):
    r = np.random.default_rng(seed)
    f = np.full((192, 256, 3), 90, np.uint8)
    f[20:80, 30:120] = r.integers(0, 255, 3)
    return f


def test_first_step_is_a_keyframe_then_static_screen_costs_nothing(live):
    text, recs, _ = live.step_frame(frame())
    assert text.startswith("#1 ~") and "KEY k1.png" in text
    assert os.path.isfile(recs[0][1])
    text2, recs2, _ = live.step_frame(frame())
    assert "(không đổi)" in text2 and recs2 == []


def test_small_change_is_a_patch_not_a_keyframe(live):
    live.step_frame(frame())
    f = frame()
    f[100:110, 40:90] = 255
    text, recs, _ = live.step_frame(f)
    assert "KEY" not in text and any(r[0] in ("patch", "dc") for r in recs)


def test_tools_are_registered_with_the_plugin_api():
    from super_computer_agent.host import PluginHost
    h = PluginHost()
    canvas_live.apply(h)
    assert set(h.by_name()) == {"canvas_start", "canvas_step", "canvas_status", "canvas_crop", "canvas_stop"}
    assert "CANVAS LIVE" in h.instruction_text()
