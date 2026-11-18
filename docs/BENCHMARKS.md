# Fovea benchmarks

**Source**: measured on this machine, 2026-11-18 (Windows 10/11, 1920x1080 @ 150% display scale unless noted). Supersedes the old `canvas_*` benchmarks below, which describe the retired canvas engine.

## 1. Token efficiency & focus-switch race handling

| Metric | Baseline | With `RECALL` (64-frame) | With race recapture (`+ HWND lock`) |
| --- | --- | --- | --- |
| Avg tokens / step | 521 | 242 | **138** (~73.5% reduction) |
| `KEYFRAME race` (window-mismatch errors) | 3 | 7 | **0** |
| `RECALL` hits | 0 | 19 | **22** |

- Cost of returning to a previous window (`RECALL #k`): dropped from ~600 tokens to typically under 60 tokens (best case for a hash-matched frame: 3-15 tokens).
- Cost of a new window / large content change: ~700 tokens (essential cost for first-time viewing).
- First real frame on Google Sheets (164 fully-new cells): ~831 tokens.
- Multi-resolution grid average (960px): ~150-170 tokens/step (a ~87-90% reduction vs. traditional full screenshots; `SCROLL` triggers when it saves >= 8 cells).

## 2. Processing latency & two-way UIA <-> canvas sync

### Per-stage latency (`fovea_step`)

- `grab` (`mss` capture): 51 ms
- `png` (compression/packaging): 2 ms
- `step` (grid/diff/hash computation): 47 ms
- Total image-processing cycle: ~100 ms
- Lightweight UIA signature scan per step (first 2 tiers, up to 40 controls): 0-29 ms (full read happens only to confirm when the light signature changes while the canvas is otherwise static).

### 4-scenario sync test matrix (A, B, C, D)

| Scenario | Input state | Result & system behavior |
| --- | --- | --- |
| A (Control) | Screen & UIA both static | 0 keyframes, no false alarms, ~51 ms/step latency |
| B (Structure-blind) | UIA changes, pixels unchanged | Fires `KEYFRAME uia` by step 2 (previously had to wait until step 8; detection latency now 1 step) |
| C (Display-blind) | Canvas changes >=60% of cells (e.g. color-inverted window), UIA unchanged | Fires `KEYFRAME canvas` immediately; a separate "canvas-mismatch" counter is tracked in `fovea_status` |
| D (In-phase) | Both canvas and UIA change significantly | 0 keyframes (treated as a legitimate change, runs through the normal delta path) |

## 3. Data integrity (125s stress test) & DPI-scaling consistency (150%)

- Dynamic spreadsheet stress test (125 seconds):
  - State drift: 0% (0/46 checkpoints)
  - Stale OCR (rows showing stale data): 0% (0/248 rows)

- Physical-coordinate verification at Windows 150% display scale:

| Measured component | Actual measured value |
| --- | --- |
| Windows display scale | 150% |
| Taskbar per UIA (`ui_get_tree`) | `y` from 1008 to 1080, width 1920 (matches physical pixels 1920x1080, not the logical `y ~= 672-720`) |
| Canvas from `fovea_step` | 960x544 (1920x1080 halved, padded to a multiple of 32) |
| Taskbar mapped to canvas | `y` from 504 to 540 - grid rows 15-16 (a `COPY` targets rows 15-16 at the bottom of the first frame) |
| Canvas -> screen scale factor | exactly 2 (1920 / 960), distinct from the 1.5 display scale |

## 4. Edge-case testing (`workspace/fovea_edge_test.py`)

### Minimized / abruptly closed windows (real Tk window, `GetWindowRect` returning `-32000`)

| Scenario | Before the fix | After the fix |
| --- | --- | --- |
| Minimized rect (`-32000...`) or `0x0` | Treated as a normal window | `WAIT`, canvas unchanged |
| `HWND` already closed (`IsWindow=False`, empty rect) | Treated as normal | `WAIT` |
| No focused window (`hwnd=0`) | Cost 524 tokens from a keyframe | `WAIT`, 0 tokens |
| Attached to an `HWND` whose window has closed | `DROP` | `DROP` (already correct before) |
| `ZeroDivisionError` / crash | 0 | 0 |

### Black frame / `mss` failure (simulated)

| Scenario | Before the fix | After the fix |
| --- | --- | --- |
| Black frame | Saved as a valid frame into `RECALL` history, cost 767 tokens, the real frame returning required a keyframe | `WAIT`, history and cell store unchanged, real frame returning costs only 1 token (if black persists for 3+ steps while the window stays valid, it's treated as real content instead of staying stuck on `WAIT`) |
| `mss` throws an error | Raised `RuntimeError` | `WAIT`, no exception raised |
| Empty frame `0x0` | Accepted, created `CANVAS 0x0` | `WAIT` |

## 5. 500-step soak test (continuous scroll + tab switching, 1080p, always-new content)

| Step milestone | Before the fix (RSS / cell count) | After the fix (RSS / cell count) |
| --- | --- | --- |
| Step 100 | +6 MB / 15,900 cells | +5 MB / 15,900 cells |
| Step 300 | +13 MB / 56,160 cells | +10 MB / 25,800 cells |
| Step 500 | +19 MB / 88,110 cells | +9 MB / 28,860 cells |

- Memory limit after the fix: cell store caps at 30,000 cells (oldest cells auto-evicted past the cap), RAM flattens out from ~step 300 onward; frame history caps at 64 and PNG file count caps at 60.

---

## Canvas benchmarks (retired engine, kept for history)

**Source**: ASA. These numbers were **not re-run** when this repo was
packaged; the sample sizes are small and should be read as indicative only.
Token counts are a pixels/750 estimate, not real API usage.

| Measurement | Result |
|---|---|
| 9 steps in a Chromium-based browser, `settle_ms=400` | ~3256 tok vs. ~11,800 tok if sending full images |
| Real task: entering 10 customers into a Google Sheet | ~3263 tok vs. ~7870 tok for full screenshots (one row missing its last 5 columns because the message got truncated) |
| Blind reading test, seed 777003 | canvas 18/18 codes (the in-place code-change step required `canvas_crop`) |
| Blind reading test, seed 777004 | full image 10/12 |
| Blind reading test, seed 777006 (scale for `canvas_crop`) | 1.0: 3/3, 0.75: 3/3, 0.67: 1/3 (only 3 samples per level, not conclusive) |
| Blind reading test, seed 777007 | full image 8/9; canvas 8/9 but the canvas result was contaminated by an earlier crop |
| Tokens, 6 canvas steps vs. 4 full images | ~2203 tok vs. ~6360 tok (~1590 tok/image); the `screenshot` image (1456x819) is larger than the 1280px canvas, so resolutions aren't directly comparable |
| RECALL | successfully triggered by minimizing and restoring a window; costs 3-15 tok |
| `ttl_tok=1500` | an expired scene correctly falls back to a fresh keyframe (1311 tok) |
| `settle_ms` 400 vs. 0 | roughly equal total tokens (2624 vs. 2635); waiting for settling adds ~140 ms per call |
| Latency (development machine) | capture ~62 ms, encoding ~90-114 ms |
| `STALE` flag | never triggered in any test, not yet verified |

Conclusion from the source notes: canvas reads about as well as a plain
screenshot and is cheaper for small incremental changes, but isn't mature
enough to ship as a product feature; fine as an opt-in beta.

Packaging smoke test (this machine, 2026-11-15, 1920x1080 display):
`canvas_step` call 1 = KEY ~1311 tok, call 2 = PATCH ~17 tok; capture ~63 ms,
encoding ~52 ms.
