# Configuration

`hermes-memory-wiki` needs Hermes plugin and toolset settings to make its tools available in a session. Current user-plugin tool handlers do **not** automatically read a `memory_wiki` section from Hermes configuration at runtime.

Use Hermes config today for `plugins.enabled` and Hermes toolset enablement. Use per-call tool arguments such as `vaultPath` for supported runtime overrides. The `memory_wiki` keys documented below describe the Python library/default config shape for direct integrations, tests, and future Hermes config wiring; they are not active Hermes config knobs in the current user-plugin integration unless a caller passes them to the library directly.

## Enable the plugin

Add `memory-wiki` to `plugins.enabled`:

```yaml
plugins:
  enabled:
    - memory-wiki
```

If other plugins are already enabled, keep them in the list:

```yaml
plugins:
  enabled:
    - other-plugin
    - memory-wiki
```

After changing plugin settings, restart Hermes or start a fresh session.

## Enable the toolset

The plugin registers its tools in the `memory_wiki` toolset. Enable that toolset with Hermes tools configuration or the Hermes tools CLI if available:

```bash
hermes tools enable memory_wiki
```

You can also inspect or change tool settings interactively with:

```bash
hermes tools
```

Start a fresh session after changing enabled toolsets.

## Install and load the native skills

`hermes-memory-wiki` ships workflow skills for wiki maintenance, authoring, and search. Install them into the native Hermes skills directory so `skills_list`, the injected available-skills context, and automatic skill-selection behavior can discover them:

```bash
mkdir -p ~/.hermes/skills/memory-wiki
cp -a src/hermes_memory_wiki/skills/wiki-* ~/.hermes/skills/memory-wiki/
```

After installing or updating the native skills, run `/reload-skills` in an existing session or start a fresh session. The skills should then load by bare name:

- `wiki-maintainer`
- `wiki-authoring`
- `wiki-search`

For example:

```text
/skill wiki-search
```

or from an agent/tool context:

```text
skill_view(name="wiki-search")
```

The plugin also registers namespaced fallback copies:

- `memory-wiki:wiki-maintainer`
- `memory-wiki:wiki-authoring`
- `memory-wiki:wiki-search`

These qualified names are useful as a fallback, but current Hermes skill-listing/discovery may not surface plugin-bundled skills automatically. Native-skill installation is therefore recommended for normal plugin usage.

## Current user-plugin runtime configuration

Supported today in Hermes sessions:

- Install the package in editable mode and install the repository as a user plugin by symlink or copy.
- Enable the plugin with `plugins.enabled`.
- Enable the `memory_wiki` toolset.
- Install the wiki workflow skills into `~/.hermes/skills/memory-wiki` for native discovery.
- Set `OPENAI_API_KEY` in the environment used to launch Hermes when you want vector indexing/search.
- Pass `vaultPath` per tool call for one-off custom vault locations.
- Initialize the vault with `wiki_init`, then run the first `wiki_reindex` with `force: true` if you want to build the vector index.

Current limitation:

- The user-plugin tool handlers currently create their runtime config from a per-call `vaultPath` when provided, otherwise from library defaults. They do not automatically read `memory_wiki.vault_path`, `memory_wiki.embeddings.enabled`, `memory_wiki.search.default_search_mode`, or other `memory_wiki` keys from Hermes config.

## Python library/default config shape

The following keys are supported by `MemoryWikiConfig` / `load_config()` for Python integrations, tests, or future Hermes config wiring. Do not rely on placing this block in Hermes config to control the current user-plugin behavior.

Default library configuration is equivalent to:

```yaml
memory_wiki:
  vault_path: ~/.hermes/wiki/main
  render:
    preserve_human_blocks: true
    create_backlinks: true
    create_dashboards: true
  search:
    default_search_mode: hybrid
    lexical_weight: 0.45
    vector_weight: 0.55
  embeddings:
    enabled: true
    provider: openai
    model: text-embedding-3-small
    api_key_env: OPENAI_API_KEY
    batch_size: 64
    timeout_seconds: 60
```

### `memory_wiki.vault_path` (library/direct integrations)

Path to the wiki vault for direct Python configuration. The default used by the current user-plugin handlers, unless a tool call supplies `vaultPath`, is:

```yaml
memory_wiki:
  vault_path: ~/.hermes/wiki/main
```

Use an absolute path or `~`-relative path in direct Python integrations:

```yaml
memory_wiki:
  vault_path: ~/notes/hermes-memory-wiki
```

Most user-plugin tools accept a per-call `vaultPath` argument; this is the supported Hermes-session override today.

### `memory_wiki.render` (library/direct integrations)

Controls generated wiki output when supplied to `MemoryWikiConfig` / `load_config()` directly:

```yaml
memory_wiki:
  render:
    preserve_human_blocks: true
    create_backlinks: true
    create_dashboards: true
```

- `preserve_human_blocks`: keep human-maintained markdown sections during generated updates where supported.
- `create_backlinks`: generate backlink/index content during compile workflows.
- `create_dashboards`: generate dashboard content during compile workflows.

### `memory_wiki.search` (library/direct integrations)

Controls search mode and hybrid scoring weights when supplied to `MemoryWikiConfig` / `load_config()` directly:

```yaml
memory_wiki:
  search:
    default_search_mode: hybrid
    lexical_weight: 0.45
    vector_weight: 0.55
```

Supported search modes exposed by tools are `auto`, `keyword`, `vector`, and `hybrid`.

- `keyword` uses deterministic lexical search and does not require embeddings.
- `vector` uses only the vector index when available.
- `hybrid` combines lexical and vector signals using the configured weights.
- `auto` lets the tool choose an effective mode based on request/config and index availability.

For keyword-only operation in direct Python integrations:

```yaml
memory_wiki:
  search:
    default_search_mode: keyword
```

In the current Hermes user-plugin integration, request keyword behavior per call where the tool exposes `searchMode` rather than relying on `memory_wiki.search.default_search_mode` in Hermes config.

### `memory_wiki.embeddings` (library/direct integrations)

Embeddings are enabled by default in the library config and use OpenAI:

```yaml
memory_wiki:
  embeddings:
    enabled: true
    provider: openai
    model: text-embedding-3-small
    api_key_env: OPENAI_API_KEY
    batch_size: 64
    timeout_seconds: 60
```

For the current user-plugin integration, set `OPENAI_API_KEY` before launching Hermes when you want vector indexing/search:

```bash
export OPENAI_API_KEY="sk-..."
```

To use a different environment variable name in direct Python integrations or future config wiring:

```yaml
memory_wiki:
  embeddings:
    api_key_env: HERMES_MEMORY_WIKI_OPENAI_API_KEY
```

Then launch the direct integration with that variable set:

```bash
export HERMES_MEMORY_WIKI_OPENAI_API_KEY="sk-..."
```

## Avoid embeddings in the current user-plugin integration

The current user-plugin handlers do not read `memory_wiki.embeddings.enabled` from Hermes config, so this Hermes config block does **not** disable embeddings today:

```yaml
memory_wiki:
  embeddings:
    enabled: false
  search:
    default_search_mode: keyword
```

Practical options today:

- Do not set `OPENAI_API_KEY` in the Hermes process environment.
- Use keyword search mode where a tool call exposes `searchMode`.
- Skip `wiki_reindex` if you do not want vector index creation attempts.
- For direct Python integrations, construct `MemoryWikiConfig(embeddings=EmbeddingConfig(enabled=False), search=SearchConfig(default_search_mode="keyword"))` or pass the equivalent raw config to `load_config()`.
- `OPENAI_API_KEY` is not required for keyword search, vault initialization, compile, get, apply, status, or lint workflows.

## Wiki schema

Vaults use the OpenClaw-compatible directory-derived schema documented in [Schema](schema.md). In short: pages under `entities/` use `pageType: entity` and store subtypes such as `person` in `entityType`; pages under `concepts/`, `syntheses/`, `sources/`, and `reports/` use matching broad `pageType` values.

## Initialize and maintain the vault

After installing and enabling the plugin/toolset, initialize the vault from a fresh Hermes session:

```text
wiki_init
```

Check status:

```text
wiki_status
```

Create or update pages with `wiki_apply`, then regenerate deterministic derived files:

```text
wiki_compile
```

Run lint checks:

```text
wiki_lint
```

## First reindex

For vector search, make sure `OPENAI_API_KEY` is present in the Hermes process environment:

```bash
export OPENAI_API_KEY="sk-..."
```

Then invoke:

```text
wiki_reindex
```

For the first full build or after large changes, pass `force: true`:

```json
{ "force": true }
```

After reindexing, `wiki_search` can use `hybrid` or `vector` modes. Keyword search remains available without vector embeddings.

## Test and smoke configuration

The default test suite stays offline and should pass without OpenAI credentials:

```bash
.venv/bin/python -m pytest -q
```

Live OpenAI tests require both the opt-in flag and an API key in the command environment:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPE...EY" .venv/bin/python -m pytest tests/live -q
```

The live smoke script also reads `OPENAI_API_KEY` from the environment and prints a compact JSON summary without embedding vectors or secrets:

```bash
OPENAI_API_KEY="$OPE...EY" .venv/bin/python scripts/smoke_live_openai.py --json
```

## Available tools

- `wiki_init`: initialize the default vault, or the per-call `vaultPath` when supplied.
- `wiki_status`: report vault status and cache/index presence.
- `wiki_search`: search pages and claims.
- `wiki_get`: read a page by path, id, title, or claim id.
- `wiki_apply`: apply a structured wiki mutation.
- `wiki_compile`: compile deterministic indexes and generated files.
- `wiki_reindex`: rebuild or update the vector index.
- `wiki_lint`: lint wiki structure and generated reports.
