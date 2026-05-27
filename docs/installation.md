# Installation

This guide installs `hermes-memory-wiki` as a user plugin. It does not require modifying Hermes Agent core files and has no OpenClaw runtime dependency.

## Prerequisites

- A working Hermes Agent installation.
- This repository checked out locally.
- The repository virtual environment available at `.venv/`.
- A fresh Hermes session after changing plugin or tool configuration.

All commands below assume you are in the repository root.

## 1. Install the Python package in editable mode

Install the package into the environment Hermes will use:

```bash
.venv/bin/python -m pip install -e .
```

You can verify the package import non-destructively:

```bash
.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
```

The project also exposes a Python entry point named `memory-wiki` under `hermes_agent.plugins`, but the user-plugin layout below is the recommended local development/install path for this repository.

## 2. Install as a Hermes user plugin

Hermes user plugins live under `~/.hermes/plugins/`. This repository already has the expected user-plugin layout at its root:

- `plugin.yaml`
- `__init__.py`
- `src/hermes_memory_wiki/...`

Use either a symlink or a copy. A symlink is convenient for development because edits in the checkout are immediately visible after restarting Hermes.

### Symlink install

```bash
mkdir -p ~/.hermes/plugins
ln -s /path/to/hermes-memory-wiki ~/.hermes/plugins/memory-wiki
```

From the repository root you can use:

```bash
mkdir -p ~/.hermes/plugins
ln -s "$PWD" ~/.hermes/plugins/memory-wiki
```

If a previous plugin directory exists, remove or rename it first so the symlink target is unambiguous.

### Copy install

```bash
mkdir -p ~/.hermes/plugins
cp -a /path/to/hermes-memory-wiki ~/.hermes/plugins/memory-wiki
```

When using a copy, repeat the copy step after updating this repository.

## 3. Enable the plugin in Hermes config

Enable the plugin by adding `memory-wiki` to the Hermes plugin list:

```yaml
plugins:
  enabled:
    - memory-wiki
```

You can usually edit this with:

```bash
hermes config edit
```

If your config already has enabled plugins, keep them and add `memory-wiki` to the same list:

```yaml
plugins:
  enabled:
    - existing-plugin
    - memory-wiki
```

Restart Hermes or start a fresh Hermes session after saving the config.

## 4. Enable the `memory_wiki` toolset

The plugin registers the `memory_wiki` toolset. Enable it in Hermes tools configuration or with the Hermes tools command if available:

```bash
hermes tools enable memory_wiki
```

You may also be able to use an interactive tools UI:

```bash
hermes tools
```

Start a fresh Hermes session after enabling the toolset. The available tools should include:

- `wiki_init`
- `wiki_status`
- `wiki_search`
- `wiki_get`
- `wiki_apply`
- `wiki_compile`
- `wiki_reindex`
- `wiki_lint`

## 5. Initialize the vault

The default vault path is:

```text
~/.hermes/wiki/main
```

In a Hermes session with the toolset enabled, invoke:

```text
wiki_init
```

Then check the result:

```text
wiki_status
```

To use a different vault for a one-off call, pass `vaultPath` to a tool invocation, for example:

```json
{ "vaultPath": "~/notes/hermes-wiki" }
```

For a persistent custom vault path, configure `memory_wiki.vault_path`; see [Configuration](configuration.md).

## 6. Run the first reindex

For vector search, set `OPENAI_API_KEY` in the environment used to launch Hermes before reindexing:

```bash
export OPENAI_API_KEY="sk-..."
```

Then invoke the reindex tool from Hermes:

```text
wiki_reindex
```

For the first full rebuild, use:

```json
{ "force": true }
```

If embeddings are disabled, `wiki_reindex` will skip vector embedding work. Keyword search remains available.

## Upgrade notes

For a symlink install, pull/update the repository, rerun the editable install if packaging metadata or dependencies changed, and restart Hermes:

```bash
git pull
.venv/bin/python -m pip install -e .
```

For a copy install, replace the copied plugin directory and restart Hermes.
