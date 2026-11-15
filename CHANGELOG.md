# Changelog

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
