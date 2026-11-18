# Changelog

## 1.0.0 - 2026-11-18
- **Three-tier observation architecture**: `ui_fuse`/`ui_get_tree` (UI
  Automation tree, text-only) → **Pixel Grid** (`live_start`/`grid_now`,
  raw color grid + change log) → **FOVEA** (`fovea_start`/`fovea_step`,
  keyframe + delta commands). Each tier is tried in order before falling
  back to a full `screenshot`; see [docs/WORKFLOW.md](docs/WORKFLOW.md).
- **Measured benchmark suite** (see [docs/BENCHMARKS.md](docs/BENCHMARKS.md)):
  ~138 tokens/step average with RECALL + HWND lock (down from a 521-token
  baseline), ~51-100 ms/step processing latency (`grab`+`png`+`step`
  combined), 0 `KEYFRAME race` (window-mismatch) errors across the
  focus-switch race test, and a hard cap of 30,000 cells on the cell store.

## 0.2.0 - 2026-11-15
- Coordination layer (`coordination.py`): priority tags on tool
  descriptions, NEXT hints, anti-polling warnings, `screenshot(reason=...)`
  with a session-checked guard-rail, a `guide` tool + `computer_use_playbook`
  prompt.
- Breaking: `screenshot` now requires a `reason` parameter (or
  `SCA_SCREENSHOT=free`).

## 0.1.1 - 2026-11-15
- Added the coordination guide (docs/WORKFLOW.md), folded into the server's
  `instructions`; the `screenshot` tool description now states clearly that
  it's a last resort.

## 0.1.0 - 2026-11-15
- First packaging: screenshot, read-only UI tree, pixel grid, canvas v7, MCP
  server (27 tools), CLI, 15 tests.
