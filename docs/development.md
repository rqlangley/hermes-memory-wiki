# Development

This guide documents the local development, test, contribution, and release workflow for `hermes-memory-wiki`.

All commands assume you are running from the repository root and use the project virtual environment. Use `.venv/bin/python`; do not rely on a bare `python` command.

## Development principles

- Keep the plugin installable as a Hermes user plugin without modifying Hermes Agent core files.
- Do not add OpenClaw runtime dependencies.
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

Run a single test by node id:

```bash
.venv/bin/python -m pytest tests/test_config.py::test_load_config_defaults -q
```

Compile-check source and tests:

```bash
.venv/bin/python -m compileall src tests
```

Optionally verify the installed/importable package version:

```bash
.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
```

## Live OpenAI tests

Live OpenAI tests are opt-in only. Do not run them by default in local verification, CI, or delegated tasks unless explicitly allowed and an API key is configured.

When live tests are explicitly allowed, run:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python -m pytest tests/live -v
```

Requirements and expectations:

- `OPENAI_API_KEY` must already be set in the environment.
- The command may send test inputs to OpenAI and may incur cost.
- Keep live fixtures minimal and avoid sensitive or user-private content.
- Non-live tests must remain useful without network access or an API key.

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

7. Inspect the diff and commit only the intended files:

   ```bash
   git diff -- docs/development.md
   git add docs/development.md
   git commit -m "docs: add development workflow"
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
