# Installation

This guide installs `hermes-memory-wiki` as a user plugin. It does not require modifying Hermes Agent core files and has no OpenClaw runtime dependency.

The recommended path is agent-assisted installation: ask your Hermes agent to clone this repository and install it into the active Hermes profile for you. That is usually safer than copying commands by hand because the agent can inspect the actual Hermes venv, plugin directory, config shape, enabled toolsets, and profile-specific skill location.

Example prompt:

```text
Please clone https://github.com/rqlangley/hermes-memory-wiki, install it as an editable Hermes user plugin, enable the memory-wiki plugin and memory_wiki toolset, install the bundled wiki skills as native Hermes skills, then initialize the default wiki vault.
```

The manual steps below are useful for development, review, or environments where you prefer to control each command yourself.

## Prerequisites

- A working Hermes Agent installation.
- This repository checked out locally.
- The Python environment that Hermes will use for user plugins. For an existing Hermes install this is often a Hermes-managed venv; for development checkouts you may create your own local `.venv/`.
- A fresh Hermes session after changing plugin or tool configuration.

All commands below assume you are in the repository root.

## 1. Install the Python package in editable mode

Install the package into the environment Hermes will use. The generic command is:

```bash
python -m pip install -e .
```

Replace `python` with the Hermes-managed interpreter if Hermes uses a managed venv. If you are doing local development and want an isolated project environment, create it first with `python -m venv .venv`, install test dependencies, and then use `.venv/bin/python`. The `.venv/` directory is intentionally not committed to this repository.

You can verify the package import non-destructively:

```bash
python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
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

## 5. Install the wiki skills as native Hermes skills

The plugin ships workflow skills for maintenance, authoring, and search. Install them into the native Hermes skills directory so `skills_list`, the injected available-skills context, and automatic skill-selection behavior can see them by bare name:

```bash
mkdir -p ~/.hermes/skills/memory-wiki
cp -a src/hermes_memory_wiki/skills/wiki-* ~/.hermes/skills/memory-wiki/
```

For a development checkout, you can symlink them instead so edits are visible after `/reload-skills` or a fresh session:

```bash
mkdir -p ~/.hermes/skills/memory-wiki
ln -s "$PWD/src/hermes_memory_wiki/skills/wiki-maintainer" ~/.hermes/skills/memory-wiki/wiki-maintainer
ln -s "$PWD/src/hermes_memory_wiki/skills/wiki-authoring" ~/.hermes/skills/memory-wiki/wiki-authoring
ln -s "$PWD/src/hermes_memory_wiki/skills/wiki-search" ~/.hermes/skills/memory-wiki/wiki-search
```

After installing or updating native skills, run `/reload-skills` in an existing Hermes session or start a fresh session. The native skill names should then be available as:

- `wiki-maintainer`
- `wiki-authoring`
- `wiki-search`

Examples:

```text
/skill wiki-maintainer
```

or, from an agent/tool context:

```text
skill_view(name="wiki-maintainer")
```

The plugin also registers bundled fallback skills. Hermes exposes plugin-bundled skills with a plugin namespace, so if you intentionally skip the native-skill install, use the qualified names:

- `memory-wiki:wiki-maintainer`
- `memory-wiki:wiki-authoring`
- `memory-wiki:wiki-search`

Native-skill installation is recommended because current Hermes skill-listing/discovery may not surface plugin-bundled skills to the agent before a task begins.

## 6. Initialize the vault

The initialized vault uses the OpenClaw-compatible schema described in [Schema](schema.md): queryable pages live under `entities/`, `concepts/`, `syntheses/`, `sources/`, and `reports/`; `pageType` must match the directory-derived broad kind; entity subtypes such as people use `entityType`.

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

Current limitation: the user-plugin tool handlers do not automatically read `memory_wiki.vault_path` from Hermes config. Use the default vault path or pass `vaultPath` per tool call until config wiring is added; see [Configuration](configuration.md).

## 7. Run the first reindex

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

If you do not want vector embeddings today, do not set `OPENAI_API_KEY`, skip `wiki_reindex`, and use keyword search mode where available. Keyword search remains available without an API key. The Hermes config key `memory_wiki.embeddings.enabled` is part of the Python library config shape, but the current user-plugin handlers do not read it from Hermes config.

## 8. Optional install verification

Before enabling the plugin in a real Hermes profile, you can verify the checkout without touching `~/.hermes`:

```bash
python -m pytest tests/test_user_plugin_layout.py -q
```

Live OpenAI verification is opt-in and uses temporary synthetic vaults only:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" python -m pytest tests/live -q
OPENAI_API_KEY="$OPENAI_API_KEY" python scripts/smoke_live_openai.py --json
```

## Upgrade notes

For a symlink install, pull/update the repository, rerun the editable install if packaging metadata or dependencies changed, and restart Hermes:

```bash
git pull
python -m pip install -e .
```

For a copy install, replace the copied plugin directory and restart Hermes.
