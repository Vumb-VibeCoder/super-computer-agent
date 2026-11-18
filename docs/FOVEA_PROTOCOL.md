# Fovea protocol

This is the instruction block that `fovea_live` hands to the model (English
translation of `fovea_live.INSTR`):

> FOVEA LIVE: call fovea_start() once, then fovea_step() whenever you need
> to look at the screen. The canvas is the screenshot divided into a grid of
> 32px cells (cell coordinates y,x; px = 32*cell). Each image returned
> (aN.png, pN.png) is a GRID OF CELLS: aN.png is at most 40 cells wide per
> row (32px cells), pN.png is at most 160 cells wide per row (8px blurred
> cells, scaled up 4x when pasted). Open with view_image; the referenced
> image must still be in context. Apply the lines IN ORDER onto the canvas
> you're keeping in mind: 'CANVAS WxH' = a new empty canvas of that size
> (unfamiliar cells get fully drawn in by the COPY lines that follow).
> 'SCROLL y0..y1 x0..x1 up dy' = rows y0..y1, columns x0..x1 (px) shift UP
> by dy px (negative = down); the exposed gap is patched afterward by a
> COPY. 'COPY <image> y,x,n,r,c;...' = for each entry: cells (y,x..x+n-1) of
> the canvas are copied from cells (r,c..c+n-1) of the grid in <image> (r,c
> count in that image's own cells; the source may be a much older image).
> 'LOW <image> ...' = like COPY but the source is an 8px blurred cell: only
> a preview, text not yet readable; it sharpens on later steps (a PENDING
> line reports what fraction is still blurry). 'RECALL #k' = the canvas is
> RESET to exactly its state right after step #k (always the first line of
> a step); any COPY/LOW lines after it only patch what differs from that
> state. A cell not mentioned = unchanged. To read a region precisely, use
> fovea_look(x,y,w,h). To check "has this region changed" without spending
> image tokens, use fovea_expect (about 2 tokens); only call fovea_step if
> it answers NO. Call fovea_stop when done. At 960px small text is less
> clear: when you need to read exact numbers, names, codes, or small text,
> use fovea_look(x,y,w,h) (original pixel coordinates of that region)
> instead of reading it off the canvas.

## Relationship to the old canvas protocol

Fovea is not a new engine — it's the same underlying grid-compression core
used by the old `canvas_v6`/`v7`/`delta2`/`delta3` protocol, wrapped with a
different command set (`CANVAS`/`SCROLL`/`COPY`/`LOW`/`RECALL #k` instead of
`KEY`/`PATCH`/`SCROLL`/`MOVE`/`DC`/`RECALL a->b`) plus the additions
described in [BENCHMARKS.md](BENCHMARKS.md): a 64-frame scene memory, an
`HWND` lock with a lightweight UIA signature check to catch focus-switch
races, and a hard cap on the cell store.

## Tools

| Tool | Parameters | Notes |
|---|---|---|
| `fovea_start` | `max_side=1280, ttl_tok=0, use_hwnd=False, settle_ms=400` | `ttl_tok>0`: once a scene/keyframe exceeds this age, send a fresh keyframe instead of a RECALL. `settle_ms`: wait up to N ms for the screen to settle before capturing. `use_hwnd`: lock the session to one window and recapture on a detected focus-switch race. |
| `fovea_step` | - | Auto-starts if `fovea_start` hasn't been called yet. Returns `KEY`/`COPY`/`LOW`/`SCROLL`/`RECALL` lines to apply to the canvas in order. |
| `fovea_look` | `x, y, w, h, zoom=1, scale=1.0, max_tok=0` | Original (uncompressed) pixel coordinates — a precise 1:1 read of just that region. `scale` 0.2-1.0 (0.5 made a 6-character code misread in testing). |
| `fovea_expect` | `x, y, w, h` | Cheap (~2 tokens) check for whether a region has changed since the last step, without sending any image. Call `fovea_step` only if it answers NO. |
| `fovea_status` | - | Step count, estimated tokens, keyframes/recalls, time per phase, UIA-vs-canvas recovery counters. |
| `fovea_stop` | - | Frees the in-memory state. |
