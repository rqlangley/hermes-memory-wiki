# hermes-memory-wiki

hermes-memory-wiki is a Hermes Agent plugin for managing a persistent markdown knowledge wiki. It adds structured wiki tools, provenance-aware pages, deterministic compile/lint workflows, and hybrid keyword + vector search without modifying Hermes core.

The plugin is installed either as an editable Python package or as a user plugin copied/symlinked into `~/.hermes/plugins/memory-wiki`. At runtime it provides the `memory_wiki` toolset:

- `wiki_init`
- `wiki_status`
- `wiki_search`
- `wiki_get`
- `wiki_apply`
- `wiki_compile`
- `wiki_reindex`
- `wiki_lint`

It also registers three plugin-scoped skills. Because Hermes namespaces skills bundled by plugins, load them with the qualified `memory-wiki:` prefix:

- `memory-wiki:wiki-maintainer`
- `memory-wiki:wiki-authoring`
- `memory-wiki:wiki-search`

## Quick start

From this repository:

```bash
.venv/bin/python -m pip install -e .
mkdir -p ~/.hermes/plugins
ln -s "$PWD" ~/.hermes/plugins/memory-wiki
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

To use the bundled workflow guidance, explicitly load the plugin-scoped skills by qualified name, for example `/skill memory-wiki:wiki-maintainer` or `skill_view(name="memory-wiki:wiki-maintainer")`. Looking up `wiki-maintainer` without the `memory-wiki:` prefix may fail because it is a plugin-bundled skill, not a flat top-level skill installed under `~/.hermes/skills`.

Embeddings use OpenAI by default. Set the key before reindexing:

```bash
export OPENAI_API_KEY="sk-..."
```

If you do not want vector embeddings in the current user-plugin integration, do not set `OPENAI_API_KEY`, skip `wiki_reindex`, and use keyword search mode where the tool call exposes `searchMode`. The Hermes user-plugin tool handlers currently honor a per-call `vaultPath` override, but they do **not** automatically read a `memory_wiki` section from Hermes config; see [Configuration](docs/configuration.md) for the current limitation and Python integration defaults.

## Documentation

- [Installation guide](docs/installation.md)
- [Configuration guide](docs/configuration.md)
- [Development and testing guide](docs/development.md)

## Testing

Run the default offline suite without network/API calls:

```bash
.venv/bin/python -m pytest -q
```

Live OpenAI tests are opt-in and marked `live_openai`; they are skipped unless `HERMES_MEMORY_WIKI_LIVE_OPENAI=1` and `OPENAI_API_KEY` are set. Current live modules validate the real OpenAI embedding provider contract, live vector reindex/hybrid search on temporary synthetic vaults, and the actual plugin tool workflow. The offline suite also simulates a pre-install Hermes user-plugin layout under `tmp_path`, exercises deterministic missing-key/vector-degradation paths, verifies keyword fallback without a vector index or API key, and checks stale-index updates/deletions with fake providers only. Final verification on 2026-05-28 passed compileall, the default offline suite (`205 passed, 5 skipped`), the opt-in live suite (`5 passed`), and the live smoke script. For a manual pre-install smoke, run `scripts/smoke_live_openai.py --json` with `OPENAI_API_KEY` set. See [Development](docs/development.md) for the current live-test commands and status.

## Goals

- Add wiki-management tools to Hermes Agent without modifying the default Hermes install.
- Provide OpenClaw memory-wiki-like page management, search, compile, and lint workflows.
- Build vector search in from the beginning using OpenAI embeddings, with deterministic keyword search always available as a fallback.
- Package reusable skills for wiki maintenance, authoring, and search workflows.

## Non-goals

- No OpenClaw bridge-mode port.
- No migration of the existing OpenClaw wiki vault.
- No dependency on OpenClaw at runtime.

## Planning artifacts

- [`docs/plans/2026-05-27-hermes-memory-wiki-design.md`](docs/plans/2026-05-27-hermes-memory-wiki-design.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md`](docs/plans/2026-05-27-hermes-memory-wiki-implementation-plan.md)
- [`docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md`](docs/plans/2026-05-27-hermes-memory-wiki-execution-handoff.md)
- [`docs/references/openclaw-memory-wiki-source-inventory.md`](docs/references/openclaw-memory-wiki-source-inventory.md)
