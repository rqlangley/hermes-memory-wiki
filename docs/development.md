# Development

This guide documents the local development, test, contribution, and release workflow for `hermes-memory-wiki`.

All commands assume you are running from the repository root and use a project virtual environment. The repository does not commit `.venv/`; create it locally before using the `.venv/bin/python` commands below:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[tests]'
```

Use `.venv/bin/python` for development commands after creating the environment; do not rely on a bare `python` command once the local venv exists.

## Development principles

- Keep the plugin installable as a Hermes user plugin without modifying Hermes Agent core files.
- Do not add OpenClaw runtime dependencies.
- Preserve the OpenClaw-compatible wiki schema documented in `docs/schema.md`: directory-derived broad page kinds, `pageType` matching those kinds, and entity subtypes in `entityType`.
- Prefer deterministic, local behavior for development and tests. Network/API-backed behavior must be explicit opt-in.
- Keep documentation and code aligned with the current user-plugin limitations described in the installation and configuration guides.

## TDD expectations

Code changes should follow strict test-driven development:

1. Add or update a failing test that describes the desired behavior.
2. Run the focused test and confirm it fails for the expected reason.
3. Implement the smallest change that satisfies the test.
4. Rerun the focused test, then the full non-live suite.
5. Refactor only with tests passing.

Documentation-only changes, such as updates under `docs/`, do not require new product tests unless they document behavior that is not already covered. Still run the verification commands before committing.

Implementation and review work is commonly handled by focused subagents. Keep each change scoped to the assigned task and avoid opportunistic changes outside that scope.

## Test commands

Run the full non-live test suite:

```bash
.venv/bin/python -m pytest -q
```

Run a focused test file while developing:

```bash
.venv/bin/python -m pytest tests/test_config.py -q
```

Run the pre-install Hermes user-plugin layout simulation:

```bash
.venv/bin/python -m pytest tests/test_user_plugin_layout.py -q
```

This offline test builds a fake Hermes home under pytest `tmp_path` with `plugins/memory-wiki` symlinked to the checkout, parses `plugin.yaml`, imports the root plugin entry point from that layout, calls `register(ctx)`, verifies expected tools and skills, and checks public tool-schema field casing (`vaultPath`, `searchMode`, `maxResults`, `lineCount`, `op`, etc.). It must not create or mutate any real `~/.hermes` profile.

Run deterministic vector degradation and stale-index coverage:

```bash
.venv/bin/python -m pytest tests/test_reindex.py tests/test_hybrid_search.py tests/test_vector_index.py -q
```

These tests use `tmp_path`, fake embedding providers, and explicit environment removal such as `monkeypatch.delenv("OPENAI_API_KEY", raising=False)`. They cover clear missing-key diagnostics, keyword-only search without vectors, hybrid-to-keyword fallback diagnostics when no vector provider/index is available, incremental re-embedding of changed documents only, and deletion of stale vector documents for removed pages. They must not make network calls.

Run a single test by node id:

```bash
.venv/bin/python -m pytest tests/test_config.py::test_load_config_defaults -q
```

Compile-check source, tests, and scripts:

```bash
.venv/bin/python -m compileall src tests scripts
```

Optionally verify the installed/importable package version:

```bash
.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
```

## Live OpenAI tests

Live OpenAI tests are explicit opt-in tests marked with `@pytest.mark.live_openai`. They are skipped unless both of these environment conditions are true:

- `HERMES_MEMORY_WIKI_LIVE_OPENAI=1`
- `OPENAI_API_KEY` is set

Run the default non-live suite without network/API calls:

```bash
.venv/bin/python -m pytest -q
```

When live tests exist and are explicitly allowed, run them with:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live -q
```

You can inspect the marker registration with:

```bash
.venv/bin/python -m pytest --markers | grep live_openai
```

Requirements and expectations:

- `OPENAI_API_KEY` must already be set in the environment used for the command.
- The command may send synthetic test inputs to OpenAI and may incur cost.
- Keep live fixtures minimal and avoid sensitive or user-private content.
- Non-live tests must remain useful without network access or an API key.

Current live-testing implementation status:

- 2026-05-28: pytest marker/gating infrastructure added in `tests/conftest.py` and `pyproject.toml`.
- 2026-05-28: live OpenAI embedding provider contract tests added in `tests/live/test_openai_embeddings.py`.
- 2026-05-28: live vector reindex/hybrid search tests added in `tests/live/test_live_reindex_search.py` using temporary synthetic vaults.
- 2026-05-28: reusable live plugin tool smoke workflow added in `scripts/smoke_live_openai.py` with coverage in `tests/live/test_live_tool_workflow.py`.
- 2026-05-28: pre-install user-plugin layout simulation strengthened in `tests/test_user_plugin_layout.py`; focused run passed with 6 tests, and full default suite passed with 200 tests and 5 live skips.
- 2026-05-28: deterministic negative/degradation coverage strengthened across `tests/test_reindex.py`, `tests/test_hybrid_search.py`, and `tests/test_vector_index.py`; focused run passed with 35 tests, and full default suite passed with 204 tests and 5 live skips.
- 2026-05-28 verification: `.venv/bin/python -m pytest --markers | grep live_openai` shows the marker; `.venv/bin/python -m pytest -q` passed with 195 tests.
- 2026-05-28 live verification: default `tests/live/test_openai_embeddings.py` run skipped 2 tests; opt-in live run passed 2 tests.
- 2026-05-28 live verification: default `tests/live/test_live_reindex_search.py` run skipped 2 tests; opt-in live run passed 2 tests; full default suite passed with 195 passed and 4 skipped.
- 2026-05-28 live verification: `tests/live/test_live_tool_workflow.py` opt-in run passed 1 test; `scripts/smoke_live_openai.py` produced an OK JSON summary with OpenAI embeddings; full default suite passed with 195 passed and 5 skipped.
- 2026-05-28 final verification: compileall passed; default offline suite passed with 205 tests and 5 live skips; full live suite passed with 5 tests; `scripts/smoke_live_openai.py --json` produced an OK JSON summary with OpenAI reindex details.

## Source-reference notes

When adding wiki content, examples, generated pages, or behavior documentation that depends on external sources, preserve enough source context for future maintainers to verify it:

- Prefer stable source references over vague summaries.
- Record filenames, page paths, claim ids, URLs, or upstream documentation versions where relevant.
- Distinguish observed behavior from intended/future behavior.
- Do not document planned capabilities as current runtime behavior.
- Update docs when tests or implementation prove a previous note is stale.

For source code changes, keep tests close to the behavior they validate and name fixtures clearly enough to explain their origin and purpose.

## Privacy and security notes

The memory wiki may store user-maintained notes, generated indexes, search metadata, and optional embedding artifacts. Treat these as potentially sensitive.

- Do not commit real user vaults, personal notes, API keys, generated secrets, or local environment files.
- Use temporary directories and synthetic fixtures in tests.
- Keep `OPENAI_API_KEY` and any other credentials in environment variables, never in tracked files.
- Avoid sending sensitive content to live OpenAI tests or embedding workflows.
- Review generated files before committing; ensure they do not contain private local paths or personal data.
- Prefer keyword-only/local workflows when validating private content.
- Be careful when editing Hermes profile directories. A profile's plugins, skills, cron, and memories affect that Hermes session.

## Contribution workflow

1. Confirm the branch and worktree state:

   ```bash
   git status --short
   git branch --show-current
   ```

2. Scope the change to the assigned task.
3. Follow TDD for code changes.
4. Run focused tests during implementation.
5. Run final verification:

   ```bash
   .venv/bin/python -m pytest -q
   .venv/bin/python -m compileall src tests
   ```

6. Optionally run the import/version check:

   ```bash
   .venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
   ```

7. Inspect the diff and commit only the files intended for the assigned task:

   ```bash
   git diff -- <intended-files>
   git add <intended-files>
   git commit -m "<type>: <concise description>"
   ```

Use precise commit messages and do not bundle unrelated code, documentation, generated artifacts, or environment changes.

## Release checklist

Before tagging or publishing a release:

- Confirm the worktree is clean and on the intended release branch.
- Review user-facing docs: `README.md`, installation, configuration, and development guides.
- Confirm package metadata in `pyproject.toml`, including version and dependencies.
- Run the full non-live suite:

  ```bash
  .venv/bin/python -m pytest -q
  ```

- Run compile checks:

  ```bash
  .venv/bin/python -m compileall src tests
  ```

- Verify the import/version output matches the release version:

  ```bash
  .venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
  ```

- If explicitly approved for the release, run the live OpenAI tests with an appropriate key.
- Inspect the final diff for secrets, private paths, generated noise, and accidental vault data.
- Confirm the plugin still has no OpenClaw runtime dependency.
- Create the release commit/tag according to the repository's release process.
