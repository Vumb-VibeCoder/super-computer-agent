# super-computer-agent

A **read-only, observation-only** MCP server for Windows that bundles four
screen-observation capabilities into one package — it never clicks or types
anything.

| Capability | What it does | Main tools |
|---|---|---|
| **Screenshot** | Captures the whole desktop (all monitors) to PNG | `screenshot`, `view_image` |
| **UI tree** | Windows UI Automation tree of a window (JSON: index, parent, type, name, rect) | `ui_list_windows`, `ui_get_tree` |
| **Live pixel grid** | Raw color grid of the screen plus a log of changed regions, fused with the UI tree to label what changed | `live_start`, `grid_now`, `ui_fuse`, `changes_since`, `wait_stable`, `crop`, `zoom`, ... |
| **Fovea** | Sends one keyframe, then only the changed parts (patch, scroll, recall an earlier scene, precise zoomed reads) to use far fewer image tokens | `fovea_start`, `fovea_step`, `fovea_look`, `fovea_expect`, `fovea_status`, `fovea_stop` |

28 tools total, no input injection of any kind.

## Installation

Requires Windows 10/11 and Python >= 3.10.

```bat
git clone <repo> super-computer-agent
cd super-computer-agent
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
super-computer-agent doctor
```

`doctor` checks dependencies, takes a trial screenshot, and spins up the
server as a smoke test (verified on the development machine: 28 tools).

**Fovea and pixel-grid need a license key — everything else works right away.**
Their core is closed-source and license-gated (see [License](#license)); without a
key, `fovea_start`/`live_start` fail with a clear error, but `screenshot` and the
UI tree still work.

- **Free 1-day trial key:** Email `hoanggiabao40478@gmail.com` with the subject
  `SCA 1-day trial` (or open a quick GitHub issue / DM me on Reddit) and I will
  send back a `.lickey` file valid for 24 hours so you can test fovea and the
  pixel grid locally.
- **Longer / commercial keys:** Email `hoanggiabao40478@gmail.com` with how many
  machines/concurrent threads you need.

Once you have the file, either set the environment variable:
```bat
set SCA_LICENSE_KEY=C:\path\to\your.lickey
```

or drop the file at the default path `%USERPROFILE%\.super-computer-agent\license.lickey`.

## Running

```bat
super-computer-agent serve                      :: stdio (default, for an MCP client)
super-computer-agent serve --transport streamable-http --port 8000

super-computer-agent screenshot -o shot.png     :: usable without MCP
super-computer-agent windows                    :: JSON list of visible windows
super-computer-agent tree 66438 --depth 3       :: UIA tree for a given hwnd
```

MCP client configuration (e.g. Claude Desktop):

```json
{
  "mcpServers": {
    "super-computer-agent": {
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["-m", "super_computer_agent", "serve"],
      "env": { "SCA_OUTPUT_DIR": "C:\\Users\\you\\sca-output" }
    }
  }
}
```

Environment variables:

| Variable | Meaning |
|---|---|
| `SCA_OUTPUT_DIR` | Where images are written (`screenshots/`, `fovea_live/`, `pixel_grid/`). Defaults to `./outputs` relative to the working directory, so **set an absolute path** when running from an MCP client. `view_image` only opens files inside this directory. |
| `SCA_SCREENSHOT` | `free` disables `screenshot`'s guard-rail (the tiering tags and hints still apply). |
| `SCA_ALLOWED_PROCESSES` | Optional. `;`-separated list of executables (name or full path) allowed to be listed/read by the UI tree. Empty = every non-sensitive window. |

## Coordinating the tools

**Fovea is the default; a full-screen `screenshot` is the last resort, for
when things are genuinely hard to read any other way.** Priority order:
`fovea_step` -> `fovea_look` (precise reading) -> `ui_fuse` (element
names/positions, as text) -> `wait_stable` (wait) -> a new keyframe
(`fovea_start`) -> only then `screenshot`. Details and the exact conditions
for using `screenshot`: [docs/WORKFLOW.md](docs/WORKFLOW.md). The server
enforces this ordering through tiering tags on tool descriptions, `NEXT:`
hints after results, warnings on repeated probing, and a guard-rail on
`screenshot` (it requires a valid `reason`, checked against the current
session; set `SCA_SCREENSHOT=free` to disable it). See the last section of
[docs/WORKFLOW.md](docs/WORKFLOW.md).

## Using fovea (summary)

1. Call `fovea_start()` once, then `fovea_step()` whenever you need to look
   at the screen.
2. The first call, and every scene change, is a `KEY` (a full image, opened
   with `view_image`). Subsequent calls are just delta commands (`COPY`,
   `LOW`, `SCROLL`, `RECALL`) applied to the canvas in order.
3. Fovea is an **approximate** image. To read small text/numbers precisely,
   use `fovea_look(x, y, w, h)`. To check "did this region change" without
   spending image tokens, use `fovea_expect` first.

Full spec: [docs/FOVEA_PROTOCOL.md](docs/FOVEA_PROTOCOL.md). Measurements:
[docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## How it works

**Fovea** (`fovea_start` -> `fovea_step`): instead of sending a full
screenshot every time (expensive — models are billed by pixel count), it
sends only what changed. Fovea is not a rewrite from scratch — it is an
upgrade layer wrapped directly around the older grid-compression core
(`canvas_v6`/`v7`/`delta2`/`delta3`), adding a 64-frame scene memory
(`RECALL #k`), precise 1:1 zoomed reads (`fovea_look`), an `HWND` lock plus a
lightweight UIA signature check to catch focus-switch races, and a hard cap
on the cell store.

- First call, and every time the scene changes: a **KEY** — a full image
  (the keyframe).
- Every call after that is just the delta needed to update the previous
  canvas: `COPY` (real pixels copied tile-by-tile from a named image),
  `LOW` (a blurred low-resolution preview that sharpens on later steps),
  `SCROLL` (a region shifted up/down by N px), and `RECALL` — the
  centerpiece of fovea: it remembers a handful of recently-seen scenes, so
  alt-tabbing between two familiar windows costs a few tokens ("go back to
  scene #k") instead of a fresh keyframe.
- A lightweight UIA signature scan runs on the first two tree tiers (up to
  40 controls) every step; if it changes while pixels are static, fovea
  fires a `KEYFRAME uia` within one step instead of waiting on a pixel
  threshold. If the canvas itself changes drastically (>=60% of cells) while
  UIA stays quiet, it fires a separate `KEYFRAME canvas` — the two failure
  modes are tracked as distinct counters in `fovea_status`.
- Minimized/closed windows, `hwnd=0`, black frames, and `mss` capture errors
  all resolve to `WAIT` (0 extra tokens, canvas and history untouched)
  instead of being treated as valid content or crashing.

The frame-diffing algorithm itself is closed-source, shipped only as a
compiled `.pyd`.

**Pixel grid** (`live_start`/`grid_now`/`ui_fuse`/...): a different trade-off
— instead of a real image, the screen becomes a **grid of colored
characters** (one character per tile, encoding hue + brightness), which is
far cheaper for a model to read as a general layout overview than a picture.

- `tree_set`/`ui_fuse` takes the Windows UI Automation tree (element names,
  types, coordinates) and overlays index numbers onto the matching grid
  tiles, so the model sees shape+color *and* "this tile is the Submit
  button, index 42" at once.
- A background thread watches for pixel changes plus Windows'
  `SetWinEventHook` (focus, window open/close); `changes_since` /
  `watch_until_change` / `wait_idle` report what changed and where without
  re-capturing the whole screen on every poll.
- `verify_action` compares the real event (pixel + OS event) against what
  was expected (`change`/`none`/`new_window`/`close`) after a click, so the
  model can tell "that worked as expected" from "something's off" instead of
  assuming a click landed.

This module's core is closed-source in full (not just the hot path), also
shipped only as a compiled `.pyd`.

Both cores are gated by the offline Ed25519 license check described in
[Installation](#installation) and [License](#license); the gate runs inside
the compiled binary itself, not only in the public wrapper around it.

## Benchmarks

> Measured on this machine. Full numbers and methodology:
> [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

Fovea is not a rewrite — it is an upgrade layer wrapped directly around the
old canvas grid-compression core. The old canvas build, run in real-world
use on Windows, had four bottlenecks: switching between familiar
windows/tabs cost ~600 tokens every time with no memory of prior scenes;
small adjacent characters on the shrunk 960px grid were unreadable, forcing
the model to guess; a focus-switch race (changing windows in the wrong
millisecond, or the UIA tree changing while pixels stayed still) could apply
the wrong delta or take up to 8 steps to notice; and long sessions grew RAM
and the cell store without bound, while black or minimized-window frames
still got written into history as if they were real content. Fovea fixes
all four by keeping the old grid core and adding a 64-frame scene memory
(`RECALL #k`), a precise 1:1 zoom tool (`fovea_look`), an `HWND` lock plus a
lightweight UIA signature check, and a hard cap on the cell store.

| Measurement | Old canvas (baseline) | Fovea (patched) | What causes the difference |
|---|---|---|---|
| Avg tokens / step | 521 | **~138** (~73.5% lower) | 64-frame `RECALL` + `HWND` lock recapture on a detected race |
| Returning to a known window | ~600 tok | **<60 tok** (best case 3-15 tok) | Hash-matches a cached frame from the 64-frame memory (22 `RECALL` hits measured) |
| Reading small text precisely | not available (guessing on the 960px grid) | exact 1:1 region crop | `fovea_look` zooms only the region that needs reading |
| Window-mismatch errors (`KEYFRAME race`) | 3 (rising to 7 once RECALL was added) | **0** | `HWND` identity lock forces a recapture when a mismatch is detected |
| Detecting a silent UIA change (pixels static) | up to 8 steps | **1 step** | Lightweight 2-tier UIA signature scan (<=40 nodes, 0-29 ms) every step |
| Recovering when the canvas changes >=60% of cells (UIA static) | full keyframe (~700-1000+ tok) | targeted `KEYFRAME canvas` only | Separate UIA vs. canvas recovery channels, tracked individually in `fovea_status` |
| Processing time / step | UIA scan cost not controlled | ~51 ms (static) / ~100 ms (full: grab 51ms + png 2ms + step 47ms) | `mss` capture fully decoupled from `pywinauto` |
| Minimized window (`-32000`) / `hwnd=0` | treated as valid, costs a 524-tok keyframe | `WAIT` (0 tokens), canvas unchanged | Detects `IsWindow=False`, empty rect, or `hwnd=0` |
| Black frame / `mss` error | written into history (767 tok) or raised `RuntimeError` | `WAIT` (0 tokens); returning to a real frame costs 1 token | Black frames under 3 consecutive steps are ignored (3+ steps is treated as real content) |
| 500-step soak test (1080p, always-new content) | RAM +19 MB / 88,110 cells, growing linearly | RAM +9 MB / 28,860 cells, flattens after step 300 | Cell store capped at 30,000 (oldest evicted), frame history capped at 64, PNGs capped at 60 |

Everything that was already solid at the old canvas grid layer carries over
unchanged: 0% long-run state drift (0/46 checkpoints) and 0% stale OCR
(0/248 rows) in a 125-second dynamic-spreadsheet stress test, and correct
physical-pixel/DPI handling at Windows 150% scale (UIA and the captured
frame both resolve to the same physical 1920x1080 pixels, mapped to the
960x544 canvas at exactly a factor of 2).

## Security

- No tool controls the mouse or keyboard. `test_server.py` asserts this.
- **UI tree** (`ui_list_windows`, `ui_get_tree`, `ui_fuse`): hides sensitive
  windows (password managers, banking apps, UAC, credential UI), skips
  processes running as admin or whose permission level can't be determined
  (fail closed), masks password fields, and caps results at 500 nodes / 6
  levels.
- **Screenshot, fovea, and the pixel grid do NOT filter content**: they
  capture whatever is on screen, including any sensitive window that's
  open. Don't run the server when something you don't want the model to see
  is visible.
- Text found in the UI tree or in images is untrusted data and may contain
  prompt injection.
- The server only listens on `127.0.0.1` by default over HTTP; there is no
  authentication — don't expose it to a network.

## Known limitations

- Fovea and the pixel grid capture the **primary monitor**; `screenshot`
  captures every monitor.
- Only tested on Windows. Chromium/Electron apps may expose only a handful
  of UIA nodes (a Chromium-based browser tested during development showed
  only 4 nodes in the tree).
- The CI workflow in `.github/workflows/ci.yml` has not yet been run on
  GitHub.

## Testing

```bat
python -m pytest -q                        :: full suite, no display needed (35 passed, 1 skipped)
set SCA_INTEGRATION=1 && python -m pytest -q -m integration   :: adds the tests that use a real display/window
```

## Structure

```
src/super_computer_agent/
  cli.py  server.py  host.py        CLI, MCP server, plugin adapter
  coordination.py                   priority tiering, NEXT hints, screenshot guard-rail
  uia.py                            UI Automation tree (read-only)
  screenshot.py                     desktop capture
  licensing/                        offline Ed25519 license-key check (public key only)
  plugins/fovea_live.py             thin loader for the compiled fovea core — public, AGPL-3.0
  plugins/pixel_grid.py             thin loader for the compiled pixel_grid core — public, AGPL-3.0
  plugins/_compiled/fovea_live.pyd  fovea core (built on the old canvas_v6/v7/delta2/delta3) — compiled, proprietary
  plugins/_compiled/pixel_grid.pyd  pixel_grid core — compiled, proprietary
tests/   docs/
```

> **Licensing note:** `plugins/fovea_live.py`'s compiled core and
> `plugins/pixel_grid.py`'s compiled core are **not** covered by the
> AGPL-3.0 license below — see [License](#license).

## License

Copyright (C) 2026 asa (hoanggiabao40478@gmail.com)

This project is dual-licensed by component — see [NOTICE](NOTICE) for the
exact file list:

- Everything except the two modules below is licensed under the
  **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE).
- The fovea delta-compression core and the pixel-grid core (`pixel_grid`)
  are **proprietary**: their source is not published; they are distributed
  only as compiled binaries (`.pyd`/`.so`) protected by an offline,
  Ed25519-signed, machine/thread-bound license key. Reverse engineering,
  decompiling, and disassembling them is prohibited. Terms:
  [PROPRIETARY_EULA.md](PROPRIETARY_EULA.md).

Contact for licensing questions: hoanggiabao40478@gmail.com
