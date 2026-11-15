"""Coordination layer: makes every client/model combine the tools the same way.

Five mechanisms (all enforced server-side, none depends on the model "remembering" the docs):
1. TIERS   - every tool description starts with a tier tag, so the tool list itself shows the order of preference.
2. HINTS   - text results get a one-line "NEXT:" suggestion (open the KEY png, wait instead of polling, ...).
             JSON-returning tools (ui_get_tree, ui_list_windows) are never touched.
3. STREAK  - repeated "(không đổi)" canvas steps trigger a "stop polling, use wait_stable" hint.
4. GATE    - the full screenshot needs a `reason` from a closed list, and some reasons are verified against what
             actually happened in this session (a crop was tried, a canvas error occurred, a 2nd monitor exists).
5. GUIDE   - a `guide` tool and a `computer_use_playbook` prompt return the same playbook on demand.
Set SCA_SCREENSHOT=free to turn the gate off (the tier tags and hints stay).
"""
import os
import re
import threading

TIERS = {
    "1-VIEW (default)": ("canvas_start", "canvas_step", "canvas_status", "canvas_stop"),
    "2-EXACT": ("canvas_crop", "crop", "zoom"),
    "3-STRUCTURE": ("ui_list_windows", "ui_get_tree", "ui_fuse", "tree_set", "fused_grid", "describe"),
    "4-WAIT/CHANGE": ("live_start", "live_stop", "calibrate_noise", "grid_now", "changes_since", "watch_until_change",
                      "wait_stable", "wait_idle", "verify_action", "film_transients", "film_at", "events_since"),
    "HELPER": ("view_image", "guide"),
    "6-LAST RESORT": ("screenshot",),
}
TIER_OF = {name: tier for tier, names in TIERS.items() for name in names}
REASONS = ("other_monitor", "canvas_contradicts_crop", "canvas_capture_error", "user_requested_full_screenshot")
HINTED = {"canvas_start", "canvas_step", "canvas_crop", "ui_fuse", "wait_stable", "wait_idle", "watch_until_change",
          "live_start", "grid_now"}

PLAYBOOK = """COMPUTER-USE PLAYBOOK (always in this order, stop at the first step that is enough)
1 VIEW      canvas_start() once, then canvas_step() whenever you need to see. KEY = open the png with view_image; PATCH/SCROLL/MOVE/DC/RECALL = apply in order.
2 EXACT     canvas_crop(x,y,w,h[,zoom 2-3]) for exact text/numbers (canvas is approximate). Keep scale=1.0 for codes.
3 STRUCTURE ui_list_windows -> ui_fuse(hwnd): element names + rects as text (cheapest). Duplicate/empty names -> look with canvas_crop.
4 WAIT      wait_stable / wait_idle(hwnd) / watch_until_change after an action. Never poll with repeated canvas_step.
5 REKEY     canvas stale / context forgot the keyframe -> canvas_start() then canvas_step().
6 LAST      screenshot(reason=...) only for: other_monitor | canvas_contradicts_crop | canvas_capture_error | user_requested_full_screenshot.
            It is refused unless the reason is true for this session. After it, go back to canvas."""


class Coordinator:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.canvas_started = False
        self.crops = 0
        self.canvas_errors = 0
        self.unchanged_streak = 0

    # ---- 1. tiers ----
    def describe(self, name, doc):
        tier = TIER_OF.get(name)
        first = " ".join((doc or "").split())
        return f"[{tier}] {first}" if tier else first

    # ---- state ----
    def note(self, name, result):
        with self.lock:
            if name == "canvas_start":
                self.canvas_started = True
                self.unchanged_streak = 0
            elif name == "canvas_step":
                self.canvas_started = True
                text = result if isinstance(result, str) else ""
                self.unchanged_streak = self.unchanged_streak + 1 if "(không đổi)" in text else 0
            elif name in ("canvas_crop", "crop", "zoom"):
                self.crops += 1
            elif name == "canvas_stop":
                self.canvas_started = False

    def note_error(self, name):
        with self.lock:
            if name.startswith("canvas_"):
                self.canvas_errors += 1

    # ---- 2/3. hints ----
    def hint(self, name, result, canvas_dir):
        if not isinstance(result, str) or name not in HINTED:
            return None
        if name == "canvas_start":
            return "NEXT: canvas_step() for the first keyframe."
        if name == "canvas_step":
            if self.unchanged_streak >= 2:
                return (f"NOTE: screen unchanged {self.unchanged_streak} steps in a row. Do not poll: use wait_stable / "
                        "watch_until_change, then canvas_step once.")
            if "KEY " in result:
                return f"NEXT: open the KEY png with view_image(path). Images are in {canvas_dir}"
            if "PATCH " in result or "SCROLL" in result or "MOVE" in result or "DC " in result:
                return (f"NEXT: apply the lines in order. Open the PATCH png (in {canvas_dir}) only if you need to see the changed "
                        "area; exact text/numbers -> canvas_crop.")
            return None
        if name == "canvas_crop":
            m = re.search(r"CROP (\S+\.png)", result)
            return f"NEXT: view_image({os.path.join(canvas_dir, m.group(1))})" if m else None
        if name == "ui_fuse":
            return "NEXT: for pixels use canvas_step, for exact text canvas_crop. Do not take a full screenshot."
        if name in ("wait_stable", "wait_idle", "watch_until_change"):
            return "NEXT: canvas_step() once to see what changed."
        if name == "live_start":
            return "NEXT: act, then wait_stable / changes_since; use canvas_step for pictures."
        if name == "grid_now":
            return "NOTE: this grid is coarse and has no text. For a picture use canvas_step."
        return None

    # ---- 4. gate ----
    def screenshot_gate(self, reason, detail, monitor_count):
        """None = allowed, otherwise the refusal text (which tells the model what to do instead)."""
        if os.environ.get("SCA_SCREENSHOT", "").lower() == "free":
            return None
        how = ("Refused: full screenshot is the LAST RESORT. Use canvas_step (view), canvas_crop (exact text), "
               "ui_fuse (structure). ")
        if reason not in REASONS:
            return how + f"reason must be one of {', '.join(REASONS)}."
        if reason == "other_monitor":
            if monitor_count is not None and monitor_count <= 1:
                return how + "Only one monitor is attached, so canvas already sees everything."
            return None
        if reason == "canvas_contradicts_crop":
            if not (self.canvas_started and self.crops):
                return how + "First run canvas_start + canvas_step, then canvas_crop the disputed area; call again only if they still disagree."
            return None
        if reason == "canvas_capture_error":
            if not self.canvas_errors:
                return how + "No canvas_* tool has failed in this session; retry canvas_start/canvas_step first."
            return None
        if len((detail or "").strip()) < 5:
            return how + "For user_requested_full_screenshot put the user's request in `detail`."
        return None
