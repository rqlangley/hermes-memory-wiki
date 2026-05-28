## Summary

Builds the initial `hermes-memory-wiki` Hermes Agent plugin.

Highlights:

- Adds a markdown memory-wiki package with vault initialization, structured page parsing/rendering, and path-safety helpers.
- Implements provenance-aware page summaries, keyword search, OpenAI-backed vector indexing/search, and hybrid search with keyword fallback.
- Adds deterministic wiki mutations, generated compile caches/indexes, lint reports, and local smoke workflow coverage.
- Registers Hermes user-plugin tools under the `memory_wiki` toolset:
  - `wiki_init`
  - `wiki_status`
  - `wiki_search`
  - `wiki_get`
  - `wiki_apply`
  - `wiki_compile`
  - `wiki_reindex`
  - `wiki_lint`
- Adds root user-plugin layout (`plugin.yaml`, `__init__.py`) and bundled skills for maintenance, authoring, and search.
- Documents installation, configuration, development workflow, current config limitations, privacy/security notes, and release workflow.

## Verification

Final non-live verification passed:

```bash
.venv/bin/python -m pytest -q
# 195 passed

.venv/bin/python -m compileall src tests
# passed

.venv/bin/python -m pip install -e .
# passed

.venv/bin/python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
# 0.1.0
```

Additional review gates:

- Final spec compliance review: PASS after fixing vector reindex symlink safety.
- Final code quality review: APPROVED.
- Secret-pattern scan: no matches.

## Notes

- No OpenClaw runtime dependency or bridge mode is included; OpenClaw files are reference-only.
- Default tests are offline and deterministic.
- Live OpenAI tests were not run because this repository currently has no `tests/live/` suite and live tests require explicit approval plus an API key.
- Do not merge until repository review/CI expectations pass.
