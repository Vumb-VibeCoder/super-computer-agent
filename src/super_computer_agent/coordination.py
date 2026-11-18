"""Coordination layer: makes every client/model combine the tools the same way.

Five mechanisms (all enforced server-side, none depends on the model "remembering" the docs):
1. TIERS   - every tool description starts with a tier tag, so the tool list itself shows the order of preference.
2. HINTS   - text results get a one-line "NEXT:" suggestion (open the atlas png, wait instead of polling, ...).
             JSON-returning tools (ui_get_tree, ui_list_windows) are never touched.
3. STREAK  - repeated "(không đổi)" fovea steps trigger a "stop polling, use wait_stable" hint.
4. GATE    - the full screenshot needs a `reason` from a closed list, and some reasons are verified against what
             actually happened in this session (a look was tried, a fovea capture error occurred, a 2nd monitor exists).
5. GUIDE   - a `guide` tool and a `computer_use_playbook` prompt return the same playbook on demand.
Set SCA_SCREENSHOT=free to turn the gate off (the tier tags and hints stay).
"""
import os
import re
import threading

TIERS = {
    "1-VIEW (default)": ("fovea_start", "fovea_step", "fovea_status", "fovea_stop"),
    "2-EXACT": ("fovea_look", "crop", "zoom"),
    "3-STRUCTURE": ("ui_list_windows", "ui_get_tree", "ui_fuse", "tree_set", "fused_grid", "describe"),
    "4-WAIT/CHANGE": ("fovea_expect", "live_start", "live_stop", "calibrate_noise", "grid_now", "changes_since",
                      "watch_until_change", "wait_stable", "wait_idle", "verify_action", "film_transients", "film_at",
                      "events_since"),
    "HELPER": ("view_image", "guide"),
    "6-LAST RESORT": ("screenshot",),
}
TIER_OF = {name: tier for tier, names in TIERS.items() for name in names}
REASONS = ("other_monitor", "fovea_contradicts_look", "fovea_capture_error", "user_requested_full_screenshot")
HINTED = {"fovea_start", "fovea_step", "fovea_look", "ui_fuse", "wait_stable", "wait_idle", "watch_until_change",
          "live_start", "grid_now"}

PLAYBOOK = """COMPUTER-USE PLAYBOOK (always in this order, stop at the first step that is enough)
1 VIEW      fovea_start() once, then fovea_step() whenever you need to see. Open each new aN.png / pN.png named on a COPY/LOW line with view_image; apply CANVAS/SCROLL/RECALL/COPY/LOW lines in order. WAIT/DROP = nothing was applied, keep the old canvas.
2 EXACT     fovea_look(x,y,w,h[,zoom 2-3]) for exact text/numbers (the canvas is 960px by default). Keep scale=1.0 for codes. fovea_expect(x,y,w,h) (~2 tokens) tells whether a region changed, call fovea_step only on NO.
3 STRUCTURE ui_list_windows -> ui_fuse(hwnd): element names + rects as text (cheapest). Duplicate/empty names -> look with fovea_look.
4 WAIT      wait_stable / wait_idle(hwnd) / watch_until_change after an action. Never poll with repeated fovea_step.
5 REKEY     the context forgot the images (or a KEYFRAME line asks for it) -> fovea_start() then fovea_step().
6 LAST      screenshot(reason=...) only for: other_monitor | fovea_contradicts_look | fovea_capture_error | user_requested_full_screenshot.
            It is refused unless the reason is true for this session. After it, go back to fovea."""

_ATLAS = re.compile(r"\b([ap]\d+\.png)\b")


class Coordinator:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.fovea_started = False
        self.looks = 0
        self.fovea_errors = 0
        self.unchanged_streak = 0

    # ---- 1. tiers ----
    def describe(self, name, doc):
        tier = TIER_OF.get(name)
        first = " ".join((doc or "").split())
        return f"[{tier}] {first}" if tier else first

    # ---- state ----
    def note(self, name, result):
        text = result if isinstance(result, str) else ""
        with self.lock:
            if name == "fovea_start":
                self.fovea_started = True
                self.unchanged_streak = 0
            elif name == "fovea_step":
                self.fovea_started = True
                self.unchanged_streak = self.unchanged_streak + 1 if "(không đổi)" in text else 0
                if text.startswith("WAIT không chụp được"):   # mss failed: the capture itself is broken
                    self.fovea_errors += 1
            elif name == "fovea_look":
                if text.startswith("LOOK "):
                    self.looks += 1
                elif "không chụp được" in text:
                    self.fovea_errors += 1
            elif name in ("crop", "zoom"):
                self.looks += 1
            elif name == "fovea_stop":
                self.fovea_started = False

    def note_error(self, name):
        with self.lock:
            if name.startswith("fovea_"):
                self.fovea_errors += 1

    # ---- 2/3. hints ----
    def hint(self, name, result, fovea_dir):
        if not isinstance(result, str) or name not in HINTED:
            return None
        if name == "fovea_start":
            return "NEXT: fovea_step() for the first frame."
        if name == "fovea_step":
            if result.startswith(("WAIT", "DROP")):
                return "NEXT: nothing was applied (canvas unchanged). Wait (wait_stable / wait_idle) and call fovea_step() again; do not poll."
            if self.unchanged_streak >= 2:
                return (f"NOTE: screen unchanged {self.unchanged_streak} steps in a row. Do not poll: use wait_stable / "
                        "watch_until_change, then fovea_step once.")
            imgs = list(dict.fromkeys(_ATLAS.findall(result)))
            if imgs:
                return (f"NEXT: open the new image(s) {', '.join(imgs)} with view_image (in {fovea_dir}), then apply the lines in order. "
                        "Exact text/numbers -> fovea_look.")
            if "RECALL" in result or "SCROLL" in result:
                return "NEXT: apply the lines in order (no new image needed). Exact text/numbers -> fovea_look."
            return None
        if name == "fovea_look":
            m = re.search(r"LOOK (\S+\.png)", result)
            return f"NEXT: view_image({os.path.join(fovea_dir, m.group(1))})" if m else None
        if name == "ui_fuse":
            return "NEXT: for pixels use fovea_step, for exact text fovea_look. Do not take a full screenshot."
        if name in ("wait_stable", "wait_idle", "watch_until_change"):
            return "NEXT: fovea_expect(x,y,w,h) on the region you care about (~2 tokens), or fovea_step() once to see what changed."
        if name == "live_start":
            return "NEXT: act, then wait_stable / changes_since; use fovea_step for pictures."
        if name == "grid_now":
            return "NOTE: this grid is coarse and has no text. For a picture use fovea_step."
        return None

    # ---- 4. gate ----
    def screenshot_gate(self, reason, detail, monitor_count):
        """None = allowed, otherwise the refusal text (which tells the model what to do instead)."""
        if os.environ.get("SCA_SCREENSHOT", "").lower() == "free":
            return None
        how = ("Refused: full screenshot is the LAST RESORT. Use fovea_step (view), fovea_look (exact text), "
               "ui_fuse (structure). ")
        if reason not in REASONS:
            return how + f"reason must be one of {', '.join(REASONS)}."
        if reason == "other_monitor":
            if monitor_count is not None and monitor_count <= 1:
                return how + "Only one monitor is attached, so fovea already sees everything."
            return None
        if reason == "fovea_contradicts_look":
            if not (self.fovea_started and self.looks):
                return how + "First run fovea_start + fovea_step, then fovea_look at the disputed area; call again only if they still disagree."
            return None
        if reason == "fovea_capture_error":
            if not self.fovea_errors:
                return how + "No fovea_* tool has failed in this session; retry fovea_start/fovea_step first."
            return None
        if len((detail or "").strip()) < 5:
            return how + "For user_requested_full_screenshot put the user's request in `detail`."
        return None
