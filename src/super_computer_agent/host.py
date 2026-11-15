"""Minimal host for plugins written against ASA's plugin API.

A plugin exposes `apply(ctx)` and uses only: ctx.tool (decorator), ctx.instructions(callable) and
`await ctx.ui_tree(hwnd, max_depth)` (JSON text of the UIA tree). This host records those calls so the
tools can be registered on any server (see server.py) or called directly in tests.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

from . import uia


class PluginHost:
    def __init__(self) -> None:
        self.tools: list[Callable] = []
        self._instructions: list[Callable[[], str]] = []

    # --- API seen by plugins ---
    def tool(self, fn: Callable) -> Callable:
        self.tools.append(fn)
        return fn

    def instructions(self, fn: Callable[[], str]) -> None:
        self._instructions.append(fn)

    async def ui_tree(self, hwnd: int, max_depth: int = 4) -> str:
        try:
            tree = await asyncio.to_thread(uia.get_tree, int(hwnd), int(max_depth))
        except Exception as exc:  # pixel_grid.ui_fuse turns a string starting with ERROR into its answer
            return f"ERROR: {type(exc).__name__}: {str(exc)[:200]}"
        return json.dumps(tree, ensure_ascii=False)

    # --- helpers for the server ---
    def instruction_text(self) -> str:
        return "\n\n".join(str(fn()) for fn in self._instructions)

    def by_name(self) -> dict[str, Callable]:
        return {fn.__name__: fn for fn in self.tools}
