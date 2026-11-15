# Canvas benchmarks

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
