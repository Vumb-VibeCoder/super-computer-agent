# super-computer-agent

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
git clone <repo> super-computer-agent
cd super-computer-agent
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
super-computer-agent doctor
```

`doctor` checks dependencies, takes a trial screenshot, and spins up the
server as a smoke test (verified on the development machine: 28 tools).

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
src/super_computer_agent/
  cli.py  server.py  host.py        CLI, MCP server, plugin adapter
  coordination.py                   priority tiering, NEXT hints, screenshot guard-rail
  uia.py                            UI Automation tree (read-only)
  screenshot.py                     desktop capture
  plugins/pixel_grid.py             color grid + change log + tree fusion
  plugins/canvas_live.py            canvas delta session (serialize, crop)
  canvas/canvas_delta2|3|v6|v7.py   delta-compression algorithm, v7 = v6 + scene recall
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
