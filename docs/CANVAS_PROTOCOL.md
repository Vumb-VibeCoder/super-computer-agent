# Canvas protocol (v7)

This is the instruction block that `canvas_live` hands to the model (verbatim
translation of `canvas_live.INSTR`):

> CANVAS LIVE (v7): call canvas_start() once, then canvas_step() whenever you
> need to look at the screen. The first call, and every scene change, is a
> KEY = a full image (open it with view_image; the image folder is reported
> by canvas_start, the file name is given right on the KEY/PATCH line).
> Subsequent calls are just the changed part: apply the lines IN ORDER onto
> the canvas you're keeping in mind. KEY k7.png (saves S0; this image is S1):
> saves the current canvas as scene S0, the new canvas = this image (scene
> S1; no parenthetical means it's the very first keyframe). RECALL a->b:
> saves the current canvas as scene S<a>, then sets the canvas to scene
> S<b> in its last known state (its old keyframe plus every delta applied
> since); only valid while that scene is still in context — if it's no
> longer in context, call canvas_start then canvas_step for a fresh
> keyframe. SCROLL y0..y1 x0..x1 up dy: rows y0..y1, columns x0..x1 shift UP
> by dy px (negative = down); the exposed gap is patched afterward by a
> PATCH line. MOVE x,y,w,h from ox,oy: the region (x,y,w,h) is copied from
> (x+ox, y+oy) of the current canvas. DC tx,ty:v;...: the 64px cell (tx,ty)
> has color value v added to it (r/g/b or a single number). PATCH a13.png
> <legend>: an atlas image made of tiles packed left-to-right with a 1px
> gap, wrapping to a new row once the 1568px width is full, in the same
> order as the legend (entries separated by ';'). An entry 'tx,ty,s,wt'
> pastes the tile into cell (tx,ty) (px = tx*64, py = ty*64), wt cells wide,
> 1 cell tall; an entry 'px,py,s,w,h' pastes at px,py, with w,h being the
> size WITHIN the atlas. s = the downscale factor already applied (s=4:
> the tile was shrunk 4x, and is scaled back up 4x when pasted). STALE:
> some cells may be out of date, so look again with canvas_crop(x,y,w,h)
> (real pixels of that exact region, cheaper than a new keyframe) or with
> canvas_start if the whole scene is stale. The image is approximate (small
> errors); to read small text/numbers precisely, use canvas_crop (zoom 2-3
> for very small text). Call canvas_stop when done.

## Tools

| Tool | Parameters | Notes |
|---|---|---|
| `canvas_start` | `max_side=1280, ttl_tok=0, use_hwnd=False, settle_ms=400` | `ttl_tok>0`: once a scene/keyframe exceeds this age, send a fresh keyframe instead of a RECALL. `settle_ms`: wait up to N ms for the screen to settle before capturing. |
| `canvas_step` | - | Auto-starts if `canvas_start` hasn't been called yet. |
| `canvas_crop` | `x, y, w, h, zoom=1, scale=1.0, max_tok=0` | Canvas coordinates, original uncompressed pixels. `scale` 0.2-1.0 (0.5 made a 6-character code misread in testing). |
| `canvas_status` | - | Step count, estimated tokens, keyframes/recalls, time per phase. |
| `canvas_stop` | - | Frees the in-memory state. |
