"""Needs a real desktop session: SCA_INTEGRATION=1 python -m pytest -m integration"""
import os

import pytest

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(os.environ.get("SCA_INTEGRATION") != "1", reason="set SCA_INTEGRATION=1")]


def test_real_screenshot_and_canvas_steps(tmp_path, monkeypatch):
    from super_computer_agent import screenshot
    from super_computer_agent.plugins import canvas_live
    monkeypatch.setattr(canvas_live, "OUT", str(tmp_path / "canvas"))   # OUT is read at import time
    w, h = screenshot.grab().size
    assert w > 0 and h > 0
    canvas_live.start(settle_ms=0)
    try:
        first, _, _ = canvas_live.step_frame(canvas_live._grab())
        assert "KEY" in first
    finally:
        canvas_live.stop()
