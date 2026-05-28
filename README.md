# hermes-memory-wiki

`hermes-memory-wiki` gives Hermes Agent a durable, source-backed memory wiki: a local Markdown vault that agents can initialize, search, update, compile, lint, and reindex through normal Hermes tools. It is useful when plain chat memory is too small or too unstructured, but you still want knowledge to stay inspectable, editable, and versionable as files.

This repository is a native Hermes Agent port of the OpenClaw `memory-wiki` plugin. It keeps the OpenClaw-style information architecture and maintenance workflow—directory-derived page kinds, structured frontmatter, source-backed claims, generated reports, and compile/lint loops—while avoiding an OpenClaw runtime dependency. The Hermes port also adds Hermes-native tool registration, workflow skills, and hybrid keyword + vector search.

At runtime it provides the `memory_wiki` toolset:

- `wiki_init`
- `wiki_status`
- `wiki_search`
- `wiki_get`
- `wiki_ingest`
- `wiki_apply`
- `wiki_compile`
- `wiki_reindex`
- `wiki_lint`

The runtime split is intentional: tools are deterministic file/index operations, while the Hermes agent/LLM decides what content, claims, and citations to submit. `wiki_ingest` captures source material from `local-file`, `conversation-summary`, or generic `text` inputs into managed source pages. `wiki_apply` then accepts structured mutations only: `create_synthesis`, `upsert_entity`, `upsert_concept`, and `update_metadata`. There is no arbitrary freeform page-write tool and no hidden tool-layer LLM call; source-backed claims are authored by the agent and written through typed schemas.

It also ships three workflow skills:

- `wiki-maintainer`
- `wiki-authoring`
- `wiki-search`

For best agent discoverability, install these as native Hermes skills under `~/.hermes/skills` during setup. The plugin also registers namespaced copies such as `memory-wiki:wiki-maintainer`, but current Hermes skill discovery may not list plugin-bundled skills for automatic loading.

## Quick start

The easiest installation path is to ask your Hermes agent to do it for you. For example:

```text
Please clone https://github.com/rqlangley/hermes-memory-wiki, install it as an editable Hermes user plugin, enable the memory-wiki plugin and memory_wiki toolset, install the bundled wiki skills as native Hermes skills, then initialize the default wiki vault.
```

That lets the agent adapt the steps to the active Hermes profile, Python environment, config location, and plugin layout. If you prefer to install manually, run the editable install with the Python interpreter used by your Hermes installation, then link the checkout as a user plugin:

```bash
python -m pip install -e .
mkdir -p ~/.hermes/plugins
ln -s "$PWD" ~/.hermes/plugins/memory-wiki
mkdir -p ~/.hermes/skills/memory-wiki
cp -a src/hermes_memory_wiki/skills/wiki-* ~/.hermes/skills/memory-wiki/
```

Enable the plugin in Hermes config:

```yaml
plugins:
  enabled:
    - memory-wiki
```

Enable the `memory_wiki` toolset, for example with the Hermes tools UI/CLI:

```bash
hermes tools enable memory_wiki
```

Start a fresh Hermes session after changing plugin or tool settings. Then initialize the vault and build the first index by invoking the plugin tools:

1. `wiki_init`
2. `wiki_status`
3. `wiki_reindex` with `{ "force": true }`

To use the workflow guidance, load the native skills by bare name, for example `/skill wiki-maintainer` or `skill_view(name="wiki-maintainer")`. If you skip the native-skill copy step, the plugin-scoped fallback names are `memory-wiki:wiki-maintainer`, `memory-wiki:wiki-authoring`, and `memory-wiki:wiki-search`, but those may not appear in automatic skill-discovery lists.

## Source-backed authoring workflow

Use the wiki as an auditable source-backed store rather than a direct Markdown scratchpad:

1. Search/read first with `wiki_search` and `wiki_get` to avoid duplicate pages and preserve existing human notes.
2. Capture new evidence with `wiki_ingest`:
   - `sourceType: local-file` for UTF-8 files on disk.
   - `sourceType: conversation-summary` for agent-authored summaries of user guidance or decisions from the current conversation.
   - `sourceType: text` for pasted or otherwise agent-supplied source text.
3. Use the returned source page `id` in `sourceIds` when calling `wiki_apply`.
4. Use `wiki_apply` `upsert_entity` or `upsert_concept` for typed source-backed pages, `create_synthesis` for cross-source synthesis, and `update_metadata` for structured metadata updates. Do not bypass the tools with arbitrary Markdown writes.
5. Verify with `wiki_compile`, `wiki_search`/`wiki_get`, and `wiki_lint`; run `wiki_reindex` when vector search should include the new content.

Embeddings use OpenAI by default. Set the key before reindexing:

```bash
export OPENAI_API_KEY="sk-..."
```

If you do not want vector embeddings in the current user-plugin integration, do not set `OPENAI_API_KEY`, skip `wiki_reindex`, and use keyword search mode where the tool call exposes `searchMode`. The Hermes user-plugin tool handlers currently honor a per-call `vaultPath` override, but they do **not** automatically read a `memory_wiki` section from Hermes config; see [Configuration](docs/configuration.md) for the current limitation and Python integration defaults.

## Documentation

- [Installation guide](docs/installation.md)
- [Configuration guide](docs/configuration.md)
- [Schema guide](docs/schema.md)
- [OpenClaw feature parity notes](docs/openclaw-feature-parity.md)
- [Development and testing guide](docs/development.md)

## Testing

Run the default offline suite without network/API calls:

```bash
python -m pytest -q
```

Live OpenAI tests are opt-in and marked `live_openai`; they are skipped unless `HERMES_MEMORY_WIKI_LIVE_OPENAI=1` and `OPENAI_API_KEY` are set. Current live modules validate the real OpenAI embedding provider contract, live vector reindex/hybrid search on temporary synthetic vaults, and the actual plugin tool workflow. The offline suite also simulates a pre-install Hermes user-plugin layout under `tmp_path`, exercises deterministic missing-key/vector-degradation paths, verifies keyword fallback without a vector index or API key, and checks stale-index updates/deletions with fake providers only. Final verification on 2026-05-28 passed compileall, the default offline suite (`205 passed, 5 skipped`), the opt-in live suite (`5 passed`), and the live smoke script. For a manual pre-install smoke, run `scripts/smoke_live_openai.py --json` with `OPENAI_API_KEY` set. See [Development](docs/development.md) for the current live-test commands and status.

## Goals

- Add wiki-management tools to Hermes Agent without modifying the default Hermes install.
- Port the OpenClaw memory-wiki information architecture and maintenance workflow to native Hermes tools and skills.
- Build vector search in from the beginning using OpenAI embeddings, with deterministic keyword search always available as a fallback.
- Package reusable skills for wiki maintenance, authoring, and search workflows.

## Non-goals

- No OpenClaw bridge-mode port.
- No migration of the existing OpenClaw wiki vault.
- No dependency on OpenClaw at runtime.

## License

This project is released under the [MIT License](LICENSE). You may use, modify, distribute, and fork it, provided the copyright notice and license text are preserved.

## Planning artifacts

- [`docs/plans/2026-05-27-hermes-memory-wiki-design.md`](docs/plans/2026-05-27-hermes-memory-wiki-design.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md`](docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md`](docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md)
- [`docs/references/openclaw-memory-wiki-source-inventory.md`](docs/references/openclaw-memory-wiki-source-inventory.md)
