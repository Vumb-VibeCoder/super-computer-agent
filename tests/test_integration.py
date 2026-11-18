"""Needs a real desktop session: SCA_INTEGRATION=1 python -m pytest -m integration"""
import os

import pytest

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(os.environ.get("SCA_INTEGRATION") != "1", reason="set SCA_INTEGRATION=1")]


def test_real_screenshot_and_fovea_steps(tmp_path, monkeypatch):
    from super_computer_agent import screenshot
    from _engine import require_engine
    require_engine("super_computer_agent.plugins._compiled.fovea_live", module_level=False)
    from super_computer_agent.plugins._compiled import fovea_live
    monkeypatch.setattr(fovea_live, "OUT", str(tmp_path / "fovea"))   # OUT is read at import time
    w, h = screenshot.grab().size
    assert w > 0 and h > 0
    fovea_live.start(settle_ms=0)
    try:
        out = fovea_live.step_frame(fovea_live._grab())
        assert out and "CANVAS" in str(out)
    finally:
        fovea_live.stop()
