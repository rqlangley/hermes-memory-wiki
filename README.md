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

Embeddings use OpenAI by default. Set the key before reindexing:

```bash
export OPENAI_API_KEY="sk-..."
```

If you do not want vector embeddings, disable them in config and use keyword search:

```yaml
memory_wiki:
  embeddings:
    enabled: false
  search:
    default_search_mode: keyword
```

## Documentation

- [Installation guide](docs/installation.md)
- [Configuration guide](docs/configuration.md)

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
