# super-computer-vision

A **read-only, observation-only** MCP server for Windows that bundles four
screen-observation capabilities into one package — it never clicks or types
anything.

| Capability | What it does | Main tools |
|---|---|---|
| **Screenshot** | Captures the whole desktop (all monitors) to PNG | `screenshot`, `view_image` |
| **UI tree** | Windows UI Automation tree of a window (JSON: index, parent, type, name, rect) | `ui_list_windows`, `ui_get_tree` |
| **Live pixel grid** | Raw color grid of the screen plus a log of changed regions, fused with the UI tree to label what changed | `live_start`, `grid_now`, `ui_fuse`, `changes_since`, `wait_stable`, `crop`, `zoom`, ... |
| **Canvas** | Sends one keyframe, then only the changed parts (patch, scroll, move, recall an earlier scene) to use far fewer image tokens | `canvas_start`, `canvas_step`, `canvas_crop`, `canvas_status`, `canvas_stop` |

28 tools total, no input injection of any kind.

## Installation

Requires Windows 10/11 and Python >= 3.10.

```bat
git clone <repo> super-computer-vision
cd super-computer-vision
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
super-computer-vision doctor
```

`doctor` checks dependencies, takes a trial screenshot, and spins up the
server as a smoke test (verified on the development machine: 28 tools).

**Canvas and pixel-grid need a license key — everything else works right away.**
Their core is closed-source and license-gated (see [License](#license)); without a
key, `canvas_start`/`live_start` fail with a clear error, but `screenshot` and the
UI tree still work.

- **Free 1-day trial key:** Email `hoanggiabao40478@gmail.com` with the subject
  `SCA 1-day trial` (or open a quick GitHub issue / DM me on Reddit) and I will
  send back a `.lickey` file valid for 24 hours so you can test the delta canvas
  and pixel grid locally.
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
| `SCA_OUTPUT_DIR` | Where images are written (`screenshots/`, `canvas_live/`, `pixel_grid/`). Defaults to `./outputs` relative to the working directory, so **set an absolute path** when running from an MCP client. `view_image` only opens files inside this directory. |
| `SCA_SCREENSHOT` | `free` disables `screenshot`'s guard-rail (the tiering tags and hints still apply). |
| `SCA_ALLOWED_PROCESSES` | Optional. `;`-separated list of executables (name or full path) allowed to be listed/read by the UI tree. Empty = every non-sensitive window. |

## Coordinating the tools

**Canvas is the default; a full-screen `screenshot` is the last resort, for
when things are genuinely hard to read any other way.** Priority order:
`canvas_step` -> `canvas_crop` (precise reading) -> `ui_fuse` (element
names/positions, as text) -> `wait_stable` (wait) -> a new keyframe
(`canvas_start`) -> only then `screenshot`. Details and the exact conditions
for using `screenshot`: [docs/WORKFLOW.md](docs/WORKFLOW.md). The server
enforces this ordering through tiering tags on tool descriptions, `NEXT:`
hints after results, warnings on repeated probing, and a guard-rail on
`screenshot` (it requires a valid `reason`, checked against the current
session; set `SCA_SCREENSHOT=free` to disable it). See the last section of
[docs/WORKFLOW.md](docs/WORKFLOW.md).

## Using canvas (summary)

1. Call `canvas_start()` once, then `canvas_step()` whenever you need to look
   at the screen.
2. The first call, and every scene change, is a `KEY` (a full image, opened
   with `view_image`). Subsequent calls are just delta commands (`PATCH`,
   `SCROLL`, `MOVE`, `DC`, `RECALL`) applied to the canvas in order.
3. Canvas is an **approximate** image. To read small text/numbers precisely,
   use `canvas_crop(x, y, w, h)`.

Full spec: [docs/CANVAS_PROTOCOL.md](docs/CANVAS_PROTOCOL.md). Measurements:
[docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## How it works

**Canvas** (`canvas_start` -> `canvas_step`): instead of sending a full
screenshot every time (expensive — models are billed by pixel count), it
sends only what changed.

- First call, and every time the scene changes: a **KEY** — a full image
  (the keyframe).
- Every call after that is just the delta needed to update the previous
  canvas: `PATCH` (the real pixels of just the changed region, packed into a
  small atlas), `SCROLL` (a region shifted up/down by N px), `MOVE` (a region
  copied from elsewhere in the same frame — e.g. a dragged window), `DC` (a
  large tile whose background color simply changed), and `RECALL` — the
  centerpiece of v7: it remembers a handful of recently-seen scenes, so
  alt-tabbing between two familiar windows costs a few tokens ("go back to
  scene S\<n\>") instead of a fresh keyframe.
- `STALE` flags tiles that may be out of date; the model should re-check
  them with `canvas_crop` rather than trust them blindly.

The frame-diffing algorithm itself (`canvas_v6`/`v7`/`delta2`/`delta3`) is
closed-source, shipped only as a compiled `.pyd`.

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

> Small sample sizes, not re-run for this repo, indicative only. Tokens are a
> pixels/750 estimate, not real API usage. Full numbers and methodology:
> [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

| Measurement | Result |
|---|---|
| 9 canvas steps vs. full images (Chromium browser) | ~3256 tok vs. ~11,800 tok |
| Real task: 10 rows entered into a Google Sheet | ~3263 tok vs. ~7870 tok (full screenshots) |
| Blind reading accuracy, canvas vs. full image | 18/18 vs. 10/12 and 8/9 (across 2 separate seeds) |
| 6 canvas steps vs. 4 full images | ~2203 tok vs. ~6360 tok |
| Latency (dev machine) | capture ~62 ms, encoding ~90-114 ms |
| RECALL (alt-tab back to a known scene) | 3-15 tok, vs. a fresh keyframe |

Conclusion: canvas reads about as well as a plain screenshot and is cheaper
for small incremental changes, but is still **beta** — ship it opt-in, not
as the only path.

## Security

- No tool controls the mouse or keyboard. `test_server.py` asserts this.
- **UI tree** (`ui_list_windows`, `ui_get_tree`, `ui_fuse`): hides sensitive
  windows (password managers, banking apps, UAC, credential UI), skips
  processes running as admin or whose permission level can't be determined
  (fail closed), masks password fields, and caps results at 500 nodes / 6
  levels.
- **Screenshot, canvas, and the pixel grid do NOT filter content**: they
  capture whatever is on screen, including any sensitive window that's
  open. Don't run the server when something you don't want the model to see
  is visible.
- Text found in the UI tree or in images is untrusted data and may contain
  prompt injection.
- The server only listens on `127.0.0.1` by default over HTTP; there is no
  authentication — don't expose it to a network.

## Known limitations

- Canvas is **beta**: small benchmark sample, token counts are a
  pixels/750 estimate rather than real API usage; the `STALE` flag has not
  been exercised by any test; a very small change (e.g. a single 6-character
  code) can produce a patch that is hard to read, requiring `canvas_crop`.
- Canvas and the pixel grid capture the **primary monitor**; `screenshot`
  captures every monitor.
- Only tested on Windows. Chromium/Electron apps may expose only a handful
  of UIA nodes (a Chromium-based browser tested during development showed
  only 4 nodes in the tree).
- The CI workflow in `.github/workflows/ci.yml` has not yet been run on
  GitHub.

## Testing

```bat
python -m pytest -q                        :: 22 tests, no display needed
set SCA_INTEGRATION=1 && python -m pytest -q -m integration   :: adds 1 test that uses a real display
```

## Structure

```
src/super_computer_vision/
  cli.py  server.py  host.py        CLI, MCP server, plugin adapter
  coordination.py                   priority tiering, NEXT hints, screenshot guard-rail
  uia.py                            UI Automation tree (read-only)
  screenshot.py                     desktop capture
  licensing/                        offline Ed25519 license-key check (public key only)
  plugins/canvas_live.py            canvas delta session (serialize, crop) — public, AGPL-3.0
  plugins/pixel_grid.py             thin loader for the compiled pixel_grid core — public, AGPL-3.0
  canvas/_compiled/*.pyd            canvas_v6/v7/delta2/delta3 — compiled, proprietary
  plugins/_compiled/pixel_grid.pyd  pixel_grid core — compiled, proprietary
tests/   docs/
```

> **Licensing note:** `canvas/canvas_v6.py`, `canvas/canvas_v7.py` (and their
> predecessor revisions `canvas_delta2.py`/`canvas_delta3.py`) and
> `plugins/pixel_grid.py` are **not** covered by the AGPL-3.0 license below —
> see [License](#license).

## License

Copyright (C) 2026 asa (hoanggiabao40478@gmail.com)

This project is dual-licensed by component — see [NOTICE](NOTICE) for the
exact file list:

- Everything except the two modules below is licensed under the
  **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE).
- The delta-compression core (`canvas_v7`/`canvas_v6` and predecessors) and
  the pixel-grid core (`pixel_grid`) are **proprietary**: their source is not
  published; they are distributed only as compiled binaries (`.pyd`/`.so`)
  protected by an offline, Ed25519-signed, machine/thread-bound license key.
  Reverse engineering, decompiling, and disassembling them is prohibited.
  Terms: [PROPRIETARY_EULA.md](PROPRIETARY_EULA.md).

Contact for licensing questions: hoanggiabao40478@gmail.com
