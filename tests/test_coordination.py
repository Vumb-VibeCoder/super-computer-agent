import asyncio

import pytest

from super_computer_agent import coordination as co
from super_computer_agent import server


def test_every_tool_has_a_tier_and_a_tagged_description():
    tools = asyncio.run(server.build_server().list_tools())
    assert {t.name for t in tools} - set(co.TIER_OF) == set()          # no tool left without a tier
    for t in tools:
        assert t.description.startswith("[" + co.TIER_OF[t.name] + "]"), t.name


def test_screenshot_gate_needs_a_true_reason(monkeypatch):
    monkeypatch.delenv("SCA_SCREENSHOT", raising=False)
    c = co.Coordinator()
    assert "must be one of" in c.screenshot_gate("just_curious", "", 1)
    assert "Only one monitor" in c.screenshot_gate("other_monitor", "", 1)
    assert c.screenshot_gate("other_monitor", "", 2) is None
    assert c.screenshot_gate("other_monitor", "", None) is None         # cannot verify: allow
    assert "fovea_start" in c.screenshot_gate("fovea_contradicts_look", "", 1)
    c.note("fovea_start", "ok")
    assert c.screenshot_gate("fovea_contradicts_look", "", 1)          # started but never looked: still refused
    c.note("fovea_look", "LOOK l1.png 10x10px")
    assert c.screenshot_gate("fovea_contradicts_look", "", 1) is None
    assert "retry" in c.screenshot_gate("fovea_capture_error", "", 1)
    c.note_error("fovea_step")
    assert c.screenshot_gate("fovea_capture_error", "", 1) is None
    assert c.screenshot_gate("user_requested_full_screenshot", "", 1)
    assert c.screenshot_gate("user_requested_full_screenshot", "chụp toàn màn hình giúp tôi", 1) is None


def test_gate_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SCA_SCREENSHOT", "free")
    assert co.Coordinator().screenshot_gate("whatever", "", 1) is None


def test_screenshot_tool_refuses_over_mcp_without_capturing(monkeypatch):
    monkeypatch.delenv("SCA_SCREENSHOT", raising=False)
    monkeypatch.setattr(server._shot, "save", lambda *a, **k: pytest.fail("must not capture"))
    srv = server.build_server()
    out = asyncio.run(srv.call_tool("screenshot", {"reason": "fovea_capture_error"}))
    text = str(out)
    assert "Refused" in text and "fovea_step" in text


def test_hints_follow_results_and_never_touch_json_tools():
    c = co.Coordinator()
    d = "C:/out/fovea_live"
    assert "view_image" in c.hint("fovea_step", "#1 ~1311tok S0\nCANVAS a1.png", d)
    assert "a2.png" in c.hint("fovea_step", "x\nCOPY a2.png ...", d)
    assert "do not poll" in c.hint("fovea_step", "WAIT không chụp được", d)
    assert "apply the lines" in c.hint("fovea_step", "x\nSCROLL 0 120", d)
    assert c.hint("fovea_look", "LOOK l3.png 10x10px", d).endswith("l3.png)")
    assert c.hint("fovea_look", "vùng ngoài màn hình", d) is None
    assert c.hint("ui_get_tree", "{}", d) is None and c.hint("ui_list_windows", "{}", d) is None


def test_polling_streak_triggers_wait_hint():
    c = co.Coordinator()
    for _ in range(2):
        c.note("fovea_step", "#2 ~0tok\n(không đổi)")
    assert "Do not poll" in c.hint("fovea_step", "#3\n(không đổi)", "d")
    c.note("fovea_step", "#4\nCOPY a.png")
    assert c.unchanged_streak == 0


def test_playbook_tool_and_prompt():
    srv = server.build_server()
    assert "COMPUTER-USE PLAYBOOK" in str(asyncio.run(srv.call_tool("guide", {})))
    assert [p.name for p in asyncio.run(srv.list_prompts())] == ["computer_use_playbook"]


def test_fovea_capture_failure_counts_as_error_for_the_gate(monkeypatch):
    monkeypatch.delenv("SCA_SCREENSHOT", raising=False)
    c = co.Coordinator()
    c.note("fovea_step", "WAIT không chụp được màn hình")
    assert c.screenshot_gate("fovea_capture_error", "", 1) is None
