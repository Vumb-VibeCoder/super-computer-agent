import numpy as np

from _engine import require_engine

require_engine("super_computer_agent.plugins._compiled.pixel_grid")

from super_computer_agent.host import PluginHost  # noqa: E402
from super_computer_agent.plugins import pixel_grid  # noqa: E402
from super_computer_agent.plugins._compiled import pixel_grid as pixel_grid_core  # noqa: E402


def test_quant_gray_and_hue_letters():
    rgb = np.array([[[0, 0, 0], [255, 255, 255], [255, 0, 0], [100, 0, 0], [0, 255, 0], [0, 0, 255]]], float)
    row = "".join(pixel_grid_core.quant(rgb)[0])
    assert row[0] == "#"      # black
    assert row[1] == "."      # white
    assert row[2] == "R"      # bright red = upper case
    assert row[3] == "r"      # dark red = lower case
    assert row[4] == "G" and row[5] == "B"


def test_expected_tools_are_registered():
    h = PluginHost()
    pixel_grid.apply(h)
    names = set(h.by_name())
    assert {"live_start", "live_stop", "grid_now", "ui_fuse", "tree_set", "fused_grid", "changes_since", "wait_stable"} <= names
    assert "ui_click" not in names   # observation only
