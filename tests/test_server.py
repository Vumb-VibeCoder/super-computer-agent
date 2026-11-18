import asyncio
import os

import pytest

pytest.importorskip("mcp")

from _engine import engine_status  # noqa: E402
from super_computer_agent import server  # noqa: E402

EXPECTED = {"screenshot", "ui_list_windows", "ui_get_tree", "view_image"}
# registered by the closed-source fovea_live engine, so only present where it can load
FOVEA_TOOLS = {"fovea_start", "fovea_step", "fovea_expect", "fovea_look", "fovea_status", "fovea_stop"}
# registered by the closed-source pixel_grid engine, so only present where it can load
PIXEL_GRID_TOOLS = {"ui_fuse", "live_start", "grid_now"}


def test_tool_surface_is_observation_only():
    tools = asyncio.run(server.build_server().list_tools())
    names = {t.name for t in tools}
    assert EXPECTED <= names
    if engine_status("super_computer_agent.plugins._compiled.pixel_grid") is None:
        assert PIXEL_GRID_TOOLS <= names
    if engine_status("super_computer_agent.plugins._compiled.fovea_live") is None:
        assert FOVEA_TOOLS <= names
    assert not {"ui_click", "ui_type", "ui_key", "ui_scroll", "ui_set_value"} & names
    assert len(names) == len(tools)  # no duplicate names


def test_view_image_is_confined_to_the_output_dir(_out_dir, tmp_path):
    os.makedirs(_out_dir)
    inside = _out_dir / "a.png"
    inside.write_bytes(b"x")
    assert server.safe_image_path(str(inside)) == os.path.realpath(inside)
    outside = tmp_path / "b.png"
    outside.write_bytes(b"x")
    with pytest.raises(PermissionError):
        server.safe_image_path(str(outside))
    (_out_dir / "c.txt").write_text("x")
    with pytest.raises(FileNotFoundError):
        server.safe_image_path(str(_out_dir / "c.txt"))
    with pytest.raises(PermissionError):
        server.safe_image_path(str(_out_dir / ".." / "b.png"))


def test_instructions_carry_the_playbook_and_screenshot_is_tagged_last_resort():
    srv = server.build_server()
    assert "COMPUTER-USE PLAYBOOK" in srv._mcp_server.instructions
    shot = [t for t in asyncio.run(srv.list_tools()) if t.name == "screenshot"][0]
    assert shot.description.startswith("[6-LAST RESORT]") and "REFUSED" in shot.description
