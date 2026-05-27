from __future__ import annotations

from pathlib import Path
from typing import Any

from hermes_memory_wiki.tools import register as register_tools


_SKILLS_ROOT = Path(__file__).parent / "skills"


def register(ctx: Any) -> None:
    """Hermes plugin entry point."""
    register_tools(ctx)
    ctx.register_skill(
        "wiki-maintainer",
        _SKILLS_ROOT / "wiki-maintainer" / "SKILL.md",
        description="Use when maintaining Hermes memory wiki vaults safely.",
    )
    ctx.register_skill(
        "wiki-authoring",
        _SKILLS_ROOT / "wiki-authoring" / "SKILL.md",
        description="Use when creating or updating Hermes memory wiki content safely.",
    )
    ctx.register_skill(
        "wiki-search",
        _SKILLS_ROOT / "wiki-search" / "SKILL.md",
        description="Use when finding and retrieving Hermes memory wiki information safely.",
    )
