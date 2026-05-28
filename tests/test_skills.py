from pathlib import Path

from hermes_memory_wiki import plugin


EXPECTED_SKILLS = {
    "wiki-maintainer": {
        "relative_path": Path("skills/wiki-maintainer/SKILL.md"),
        "tools": {
            "wiki_init",
            "wiki_status",
            "wiki_search",
            "wiki_get",
            "wiki_apply",
            "wiki_ingest",
            "wiki_compile",
            "wiki_reindex",
            "wiki_lint",
        },
    },
    "wiki-authoring": {
        "relative_path": Path("skills/wiki-authoring/SKILL.md"),
        "tools": {"wiki_get", "wiki_apply", "wiki_ingest", "wiki_compile", "wiki_lint"},
    },
    "wiki-search": {
        "relative_path": Path("skills/wiki-search/SKILL.md"),
        "tools": {"wiki_search", "wiki_get", "wiki_status", "wiki_reindex"},
    },
}

EXPECTED_TOOLS = {
    "wiki_init",
    "wiki_status",
    "wiki_search",
    "wiki_get",
    "wiki_apply",
    "wiki_ingest",
    "wiki_compile",
    "wiki_reindex",
    "wiki_lint",
}

FORBIDDEN_REFERENCES = {
    "claude",
    "unsafe-local",
}

SCHEMA_TERMS = {
    "pageType: entity",
    "entityType: person",
    "sourceIds",
    "claims",
    "evidence",
}


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_skill(self, name, path, **kwargs):
        self.skills[name] = {"path": Path(path), **kwargs}


def _registered_context():
    ctx = FakeContext()
    plugin.register(ctx)
    return ctx


def _read_skill_text(path: Path) -> str:
    assert path.is_file(), f"missing skill file: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start at byte 0 with YAML frontmatter"
    assert "\n---\n" in text[4:], "frontmatter must be closed before body"
    body = text.split("\n---\n", 1)[1].strip()
    assert body, "skill body must be non-empty"
    return text


def test_register_registers_expected_wiki_skills():
    ctx = _registered_context()

    assert set(ctx.skills) == set(EXPECTED_SKILLS)
    for name, entry in ctx.skills.items():
        assert entry["description"].startswith("Use when ")
        assert len(entry["description"]) <= 1024


def test_registered_skill_paths_exist_and_point_to_expected_skill_docs():
    ctx = _registered_context()
    package_root = Path(plugin.__file__).parent

    for name, expected in EXPECTED_SKILLS.items():
        path = ctx.skills[name]["path"]
        assert path == package_root / expected["relative_path"]
        _read_skill_text(path)


def test_skill_docs_are_hermes_native_and_reference_existing_tools_only():
    ctx = _registered_context()
    assert set(ctx.tools) == EXPECTED_TOOLS

    for name, expected in EXPECTED_SKILLS.items():
        text = _read_skill_text(ctx.skills[name]["path"])
        lower_text = text.lower()

        for forbidden in FORBIDDEN_REFERENCES:
            assert forbidden not in lower_text

        for tool_name in expected["tools"]:
            assert tool_name in text

        mentioned_wiki_tokens = {token for token in text.replace("`", " ").split() if token.startswith("wiki_")}
        assert mentioned_wiki_tokens <= EXPECTED_TOOLS


def test_skill_frontmatter_uses_required_names_and_descriptions():
    ctx = _registered_context()

    for name in EXPECTED_SKILLS:
        text = _read_skill_text(ctx.skills[name]["path"])
        frontmatter = text.split("\n---\n", 1)[0]
        assert f"name: {name}" in frontmatter
        assert "description: Use when " in frontmatter


def test_skill_docs_describe_openclaw_compatible_schema_without_page_type_person():
    ctx = _registered_context()

    for skill_name in ("wiki-authoring", "wiki-maintainer"):
        text = _read_skill_text(ctx.skills[skill_name]["path"])
        assert "OpenClaw-compatible" in text

    authoring = _read_skill_text(ctx.skills["wiki-authoring"]["path"])
    for term in SCHEMA_TERMS:
        assert term in authoring
    assert "pageType: person" not in authoring

    search = _read_skill_text(ctx.skills["wiki-search"]["path"])
    assert "Search first" in search
    assert "claim ID" in search

    maintainer = _read_skill_text(ctx.skills["wiki-maintainer"]["path"])
    for term in ("wiki_status", "wiki_compile", "wiki_lint", "wiki_reindex", "search smoke"):
        assert term in maintainer


def test_authoring_and_maintainer_skills_teach_source_backed_workflow():
    ctx = _registered_context()

    authoring = _read_skill_text(ctx.skills["wiki-authoring"]["path"])
    maintainer = _read_skill_text(ctx.skills["wiki-maintainer"]["path"])
    combined = f"{authoring}\n{maintainer}"

    for term in (
        "wiki_ingest",
        "conversation-summary",
        "local-file",
        "upsert_entity",
        "upsert_concept",
        "create_synthesis",
        "sourceIds",
        "deterministic",
        "no hidden tool-layer LLM calls",
    ):
        assert term in combined

    assert "wiki_get" in authoring and "wiki_search" in authoring
    assert "before editing" in authoring
