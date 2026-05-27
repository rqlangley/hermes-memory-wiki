# Configuration

`hermes-memory-wiki` reads a `memory_wiki` section from Hermes configuration. It also needs the Hermes plugin and toolset settings that make the tools available in a session.

The examples below are intended for the Hermes profile/config you use to run the agent. Edit with `hermes config edit` or the equivalent config workflow for your installation.

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

## Memory wiki config keys

Default configuration is equivalent to:

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

### `memory_wiki.vault_path`

Path to the wiki vault. The default is:

```yaml
memory_wiki:
  vault_path: ~/.hermes/wiki/main
```

Use an absolute path or `~`-relative path:

```yaml
memory_wiki:
  vault_path: ~/notes/hermes-memory-wiki
```

Most tools also accept a per-call `vaultPath` argument for one-off overrides.

### `memory_wiki.render`

Controls generated wiki output:

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

### `memory_wiki.search`

Controls search mode and hybrid scoring weights:

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

For keyword-only operation:

```yaml
memory_wiki:
  search:
    default_search_mode: keyword
```

### `memory_wiki.embeddings`

Embeddings are enabled by default and use OpenAI:

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

Set the environment variable named by `api_key_env` before launching Hermes:

```bash
export OPENAI_API_KEY="sk-..."
```

To use a different environment variable name:

```yaml
memory_wiki:
  embeddings:
    api_key_env: HERMES_MEMORY_WIKI_OPENAI_API_KEY
```

Then launch Hermes with that variable set:

```bash
export HERMES_MEMORY_WIKI_OPENAI_API_KEY="sk-..."
```

## Disable embeddings

Disable embeddings when you do not want network calls, do not have an OpenAI API key, or want deterministic keyword-only behavior:

```yaml
memory_wiki:
  embeddings:
    enabled: false
  search:
    default_search_mode: keyword
```

With embeddings disabled:

- `wiki_search` should use keyword search unless a different mode is explicitly requested.
- `wiki_reindex` will not create OpenAI embeddings.
- `OPENAI_API_KEY` is not required for keyword search, vault initialization, compile, get, apply, status, or lint workflows.

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

For vector search, make sure the configured API key environment variable is present in the Hermes process environment. With defaults:

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

After reindexing, `wiki_search` can use `hybrid` or `vector` modes. Keyword search remains available regardless of embedding configuration.

## Available tools

- `wiki_init`: initialize the configured vault.
- `wiki_status`: report vault status and cache/index presence.
- `wiki_search`: search pages and claims.
- `wiki_get`: read a page by path, id, title, or claim id.
- `wiki_apply`: apply a structured wiki mutation.
- `wiki_compile`: compile deterministic indexes and generated files.
- `wiki_reindex`: rebuild or update the vector index.
- `wiki_lint`: lint wiki structure and generated reports.
