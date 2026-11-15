# Architecture

```
MCP client  <--stdio/http-->  server.py (FastMCP)
                                |-- native tools: screenshot, ui_list_windows, ui_get_tree, view_image
                                |-- PluginHost (host.py) --apply()--> plugins/pixel_grid.py
                                |                                     plugins/canvas_live.py --> canvas/ (v2,v3,v6,v7)
                                `-- uia.py (pywinauto)  <-- ctx.ui_tree() used by pixel_grid.ui_fuse
```

- Plugins are written against ASA's small plugin API: `apply(ctx)` with
  `ctx.tool`, `ctx.instructions`, `await ctx.ui_tree(hwnd, depth)`.
  `PluginHost` records those calls; `server.py` registers each function as
  an MCP tool.
- Synchronous tools run in a thread (`asyncio.to_thread`) so blocking calls
  (`wait_stable`, `watch_until_change`) don't stall the event loop.
- Tools with a `readonly` attribute get `readOnlyHint=True`.
- Canvas: `canvas_v7.CanvasDelta.step(frame)` returns a list of ops (`key`,
  `recall`, `scroll`, `move`, `dc`, `patch`); `canvas_live.serialize` turns
  each op into a text line + PNG; `canvas_v7.Decoder` rebuilds the canvas
  from the ops to verify correctness (used in tests).
