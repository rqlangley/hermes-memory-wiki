from __future__ import annotations

from typing import Any

from hermes_memory_wiki.tools import register as register_tools


def register(ctx: Any) -> None:
    """Hermes plugin entry point."""
    register_tools(ctx)
