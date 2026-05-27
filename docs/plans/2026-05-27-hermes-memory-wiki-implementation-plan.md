# hermes-memory-wiki Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a native Hermes Agent plugin that provides markdown memory-wiki tools, skills, deterministic wiki management, and built-in hybrid keyword + OpenAI vector search.

**Architecture:** The project is a Python package with a Hermes plugin entry point. Core wiki behavior lives in small pure-Python modules; Hermes integration is a thin layer registering tools and skills. Local keyword search always works; vector search uses OpenAI embeddings with a local SQLite cache/index and fake embedding providers for tests.

**Tech Stack:** Python 3.11+, pytest, PyYAML, frontmatter-compatible parsing implemented internally or via optional dependency, SQLite stdlib, OpenAI embeddings through HTTPS/httpx or urllib, Hermes plugin API.

---

## Source references

Before implementing each relevant area, inspect the OpenClaw source inventory:

- `docs/references/openclaw-memory-wiki-source-inventory.md`

Primary OpenClaw files to reference:

- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/index.js`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/cli-Cx8TeRn1.js`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/config-U1dUmpXj.js`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/obsidian-vault-maintainer/SKILL.md`

Do **not** import these at runtime.

## Branch and commit strategy

- Work from `main` only for initial planning artifacts.
- Create implementation branch before coding:

```bash
git checkout -b feat/initial-hermes-memory-wiki-plugin
```

- Commit after each task or small task group.
- Push branch frequently.
- Open PR when implementation and verification pass.
- Merge to `main` only after tests, spec compliance review, and code quality review.

## Verification gates

Every implementation task must use TDD where practical:

1. Write failing test.
2. Run targeted test and confirm failure.
3. Implement minimal code.
4. Run targeted test and confirm pass.
5. Run relevant broader tests.
6. Commit.

Final verification:

```bash
python -m pytest -q
python -m compileall src tests
```

If package metadata exists:

```bash
python -m pip install -e .
python -m pytest -q
```

Optional live OpenAI check only when explicitly enabled:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 OPENAI_API_KEY="$OPENAI_API_KEY" pytest tests/live -v
```

---

## Phase 0: Project skeleton and package hygiene

### Task 0.1: Create Python package skeleton

**Objective:** Create minimal package/test structure without functional code.

**Files:**

- Create: `pyproject.toml`
- Create: `src/hermes_memory_wiki/__init__.py`
- Create: `src/hermes_memory_wiki/plugin.py`
- Create: `tests/test_import.py`
- Create: `.gitignore`

**Step 1: Write failing import test**

Create `tests/test_import.py`:

```python
def test_package_imports():
    import hermes_memory_wiki
    assert hermes_memory_wiki.__version__
```

**Step 2: Run test to verify failure**

```bash
pytest tests/test_import.py -q
```

Expected: fail because package metadata/files are absent.

**Step 3: Add package skeleton**

`pyproject.toml` should define:

- project name: `hermes-memory-wiki`
- package source under `src`
- pytest config
- optional dependencies group for tests
- entry point group `hermes_agent.plugins`

Entry point:

```toml
[project.entry-points."hermes_agent.plugins"]
memory-wiki = "hermes_memory_wiki.plugin"
```

`src/hermes_memory_wiki/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/hermes_memory_wiki/plugin.py`:

```python
def register(ctx):
    """Hermes plugin entry point; tool registration added in later tasks."""
    return None
```

**Step 4: Run test to verify pass**

```bash
python -m pip install -e .
pytest tests/test_import.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add pyproject.toml src tests .gitignore
git commit -m "chore: add python package skeleton"
```

---

## Phase 1: Config and path safety

### Task 1.1: Implement config defaults

**Objective:** Normalize wiki config with safe defaults.

**Files:**

- Create: `src/hermes_memory_wiki/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing tests**

Test cases:

- default vault path expands to `~/.hermes/wiki/main`;
- default search mode is `hybrid`;
- default embedding model is `text-embedding-3-small`;
- embeddings enabled by default;
- explicit config overrides defaults;
- env var name defaults to `OPENAI_API_KEY`.

**Step 2: Run targeted tests and confirm failure**

```bash
pytest tests/test_config.py -q
```

**Step 3: Implement config dataclasses/functions**

Create dataclasses:

- `RenderConfig`
- `SearchConfig`
- `EmbeddingConfig`
- `MemoryWikiConfig`

Expose:

```python
def expand_path(path: str, home: Path | None = None) -> Path: ...
def load_config(raw: Mapping[str, Any] | None = None, *, home: Path | None = None) -> MemoryWikiConfig: ...
```

For Hermes runtime, later add helper to read `memory_wiki` from Hermes config utilities. Keep this task pure.

**Step 4: Run tests**

```bash
pytest tests/test_config.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/config.py tests/test_config.py
git commit -m "feat: add memory wiki config defaults"
```

### Task 1.2: Add vault path guard

**Objective:** Prevent path traversal and writes outside the configured vault.

**Files:**

- Create: `src/hermes_memory_wiki/paths.py`
- Create/modify: `tests/test_paths.py`

**Step 1: Write failing tests**

Test cases:

- `safe_join(root, "sources/a.md")` returns a path under root;
- rejects `../outside.md`;
- rejects absolute paths outside root;
- normalizes Windows-style backslashes in relative wiki paths;
- returns relative POSIX paths for display.

**Step 2: Run tests and confirm failure**

```bash
pytest tests/test_paths.py -q
```

**Step 3: Implement path helpers**

Expose:

```python
def normalize_relative_path(value: str) -> str: ...
def safe_join(root: Path, relative: str) -> Path: ...
def to_display_path(root: Path, path: Path) -> str: ...
```

**Step 4: Run tests**

```bash
pytest tests/test_paths.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/paths.py tests/test_paths.py
git commit -m "feat: add vault path safety helpers"
```

---

## Phase 2: Markdown and schema handling

### Task 2.1: Parse and render wiki markdown frontmatter

**Objective:** Parse YAML frontmatter and body without losing data.

**Files:**

- Create: `src/hermes_memory_wiki/markdown.py`
- Create: `tests/test_markdown.py`

**Step 1: Write failing tests**

Test cases:

- parse markdown with YAML frontmatter;
- parse markdown without frontmatter;
- render frontmatter/body with trailing newline;
- preserve unknown frontmatter fields;
- body excludes frontmatter delimiters;
- invalid YAML raises a clear `WikiMarkdownError`.

**Step 2: Run tests and confirm failure**

```bash
pytest tests/test_markdown.py -q
```

**Step 3: Implement parser/renderer**

Expose:

```python
@dataclass
class WikiMarkdown:
    frontmatter: dict[str, Any]
    body: str

def parse_wiki_markdown(text: str) -> WikiMarkdown: ...
def render_wiki_markdown(doc: WikiMarkdown) -> str: ...
```

Use PyYAML if available via dependency.

**Step 4: Run tests**

```bash
pytest tests/test_markdown.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/markdown.py tests/test_markdown.py
git commit -m "feat: parse and render wiki markdown"
```

### Task 2.2: Implement page summary schema

**Objective:** Convert raw markdown pages into normalized queryable page summaries.

**Files:**

- Create: `src/hermes_memory_wiki/schema.py`
- Modify: `tests/test_markdown.py` or create `tests/test_schema.py`

**Step 1: Write failing tests**

Test cases:

- derive kind from `pageType` and path;
- normalize `id`, `title`, `sourceIds`, `aliases`;
- normalize claims with evidence;
- normalize questions and contradictions;
- support person-card-like fields for `find-person` and `route-question` modes;
- ignore invalid claim objects rather than crashing where safe.

**Step 2: Run tests**

```bash
pytest tests/test_schema.py -q
```

**Step 3: Implement normalized dataclasses**

Dataclasses:

- `WikiEvidence`
- `WikiClaim`
- `WikiPageSummary`
- optional `PersonCard`

Expose:

```python
def page_kind_from_path(path: str, frontmatter: Mapping[str, Any]) -> str: ...
def to_page_summary(relative_path: str, raw: str) -> WikiPageSummary | None: ...
```

Reference OpenClaw query/search fields in `cli-Cx8TeRn1.js:1526-1569`.

**Step 4: Run tests**

```bash
pytest tests/test_schema.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/schema.py tests/test_schema.py
git commit -m "feat: normalize wiki page summaries"
```

### Task 2.3: Preserve managed and human blocks

**Objective:** Implement generated/human marker handling.

**Files:**

- Modify: `src/hermes_memory_wiki/markdown.py`
- Modify: `tests/test_markdown.py`

**Step 1: Write failing tests**

Test cases:

- `replace_managed_block` replaces Hermes generated block;
- preserves Hermes human block;
- recognizes OpenClaw generated/human markers when reading;
- adds missing human notes block;
- never deletes text outside generated block.

**Step 2: Run tests**

```bash
pytest tests/test_markdown.py -q
```

**Step 3: Implement marker helpers**

Expose:

```python
HERMES_GENERATED_START = "<!-- hermes-wiki:generated:start -->"
HERMES_GENERATED_END = "<!-- hermes-wiki:generated:end -->"
HERMES_HUMAN_START = "<!-- hermes-wiki:human:start -->"
HERMES_HUMAN_END = "<!-- hermes-wiki:human:end -->"

def replace_managed_block(original: str, heading: str, body: str) -> str: ...
def ensure_human_notes_block(body: str) -> str: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:2289-2339`.

**Step 4: Run tests**

```bash
pytest tests/test_markdown.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/markdown.py tests/test_markdown.py
git commit -m "feat: preserve wiki managed and human blocks"
```

---

## Phase 3: Vault initialization and reading

### Task 3.1: Initialize vault structure

**Objective:** Create a new vault without overwriting existing files.

**Files:**

- Create: `src/hermes_memory_wiki/vault.py`
- Create: `tests/test_vault_init.py`

**Step 1: Write failing tests**

Test cases:

- initialization creates required directories/files;
- second initialization is idempotent;
- existing `inbox.md` content is not overwritten;
- log entry is appended only when something changed;
- metadata directory is `.hermes-wiki`.

**Step 2: Run tests**

```bash
pytest tests/test_vault_init.py -q
```

**Step 3: Implement `initialize_vault`**

Expose:

```python
@dataclass
class InitResult:
    root: Path
    created: bool
    created_directories: list[Path]
    created_files: list[Path]

def initialize_vault(config: MemoryWikiConfig, *, now: datetime | None = None) -> InitResult: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:473-508`.

**Step 4: Run tests**

```bash
pytest tests/test_vault_init.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vault.py tests/test_vault_init.py
git commit -m "feat: initialize hermes wiki vault"
```

### Task 3.2: List and read queryable pages

**Objective:** Read wiki pages from standard directories.

**Files:**

- Modify: `src/hermes_memory_wiki/vault.py`
- Create: `tests/test_vault_read.py`

**Step 1: Write failing tests**

Test cases:

- lists `.md` files in `sources`, `entities`, `concepts`, `syntheses`, `reports`;
- excludes directory `index.md`;
- ignores files outside query dirs;
- returns summaries with raw content;
- invalid markdown page is skipped or reported according to selected behavior.

**Step 2: Run tests**

```bash
pytest tests/test_vault_read.py -q
```

**Step 3: Implement page listing**

Expose:

```python
QUERY_DIRS = ["entities", "concepts", "sources", "syntheses", "reports"]

def list_wiki_markdown_files(root: Path) -> list[str]: ...
def read_queryable_pages(root: Path) -> list[WikiPageSummary]: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:1461-1483`.

**Step 4: Run tests**

```bash
pytest tests/test_vault_read.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vault.py tests/test_vault_read.py
git commit -m "feat: read queryable wiki pages"
```

---

## Phase 4: Keyword search

### Task 4.1: Build searchable text and snippets

**Objective:** Implement deterministic text extraction for snippets and keyword matching.

**Files:**

- Create: `src/hermes_memory_wiki/search_keyword.py`
- Create: `tests/test_keyword_search.py`

**Step 1: Write failing tests**

Test cases:

- generated related blocks removed from snippet text;
- frontmatter removed from snippet text;
- query tokens deduplicate and ignore tiny tokens;
- exact query line chosen for snippet;
- fallback snippet chooses first meaningful body line.

**Step 2: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 3: Implement text helpers**

Expose:

```python
def build_query_tokens(query: str) -> list[str]: ...
def build_page_search_text(page: WikiPageSummary) -> str: ...
def build_snippet(raw: str, query: str) -> str: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:1517-1579`.

**Step 4: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/search_keyword.py tests/test_keyword_search.py
git commit -m "feat: build wiki keyword search text"
```

### Task 4.2: Implement keyword scoring

**Objective:** Rank pages and claims using OpenClaw-like scoring.

**Files:**

- Modify: `src/hermes_memory_wiki/search_keyword.py`
- Modify: `tests/test_keyword_search.py`

**Step 1: Write failing tests**

Test cases:

- exact title match outranks body-only match;
- id/path match boosts score;
- claim text match returns matched claim metadata;
- confidence boosts claim score;
- stale/contested claims score lower;
- body occurrence boost is capped;
- nonmatching pages score zero.

**Step 2: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 3: Implement scoring**

Expose:

```python
@dataclass
class WikiSearchResult:
    corpus: str
    path: str
    title: str
    kind: str
    score: float
    snippet: str
    search_mode: str
    matched_claim_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

def score_page(page: WikiPageSummary, query: str, mode: str = "auto") -> float: ...
def keyword_search(pages: Sequence[WikiPageSummary], query: str, *, max_results: int = 10, mode: str = "auto") -> list[WikiSearchResult]: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:1632-1918`.

**Step 4: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/search_keyword.py tests/test_keyword_search.py
git commit -m "feat: rank wiki keyword search results"
```

### Task 4.3: Add search modes

**Objective:** Implement `auto`, `find-person`, `route-question`, `source-evidence`, and `raw-claim` boosts.

**Files:**

- Modify: `src/hermes_memory_wiki/search_keyword.py`
- Modify: `tests/test_keyword_search.py`

**Step 1: Write failing tests**

Test cases:

- `find-person` boosts person-like pages;
- `route-question` boosts pages with routing/best-used-for fields;
- `source-evidence` boosts source pages and evidence matches;
- `raw-claim` prioritizes pages with matching claims;
- invalid mode raises or defaults predictably.

**Step 2: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 3: Implement mode boosts**

Reference OpenClaw:

- `cli-Cx8TeRn1.js:1725-1764`
- `cli-Cx8TeRn1.js:1766-1799`

**Step 4: Run tests**

```bash
pytest tests/test_keyword_search.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/search_keyword.py tests/test_keyword_search.py
git commit -m "feat: add wiki keyword search modes"
```

---

## Phase 5: Vector indexing and OpenAI embeddings

### Task 5.1: Define embedding provider interface and fake provider

**Objective:** Make vector search testable offline.

**Files:**

- Create: `src/hermes_memory_wiki/embeddings.py`
- Create: `tests/test_embeddings.py`

**Step 1: Write failing tests**

Test cases:

- fake provider returns deterministic vectors;
- vector dimensions are stable;
- missing API key diagnostic is clear for OpenAI provider;
- embedding input batching preserves order.

**Step 2: Run tests**

```bash
pytest tests/test_embeddings.py -q
```

**Step 3: Implement provider interface**

Expose:

```python
class EmbeddingProvider(Protocol):
    provider: str
    model: str
    dimensions: int | None
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

class FakeEmbeddingProvider: ...
class OpenAIEmbeddingProvider: ...
```

For OpenAI:

- Use `OPENAI_API_KEY` by default.
- Call `/v1/embeddings`.
- Keep HTTP dependency minimal and mockable.

**Step 4: Run tests**

```bash
pytest tests/test_embeddings.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/embeddings.py tests/test_embeddings.py
git commit -m "feat: add embedding provider interface"
```

### Task 5.2: Build search documents

**Objective:** Convert pages and claims into embedding/search documents.

**Files:**

- Create: `src/hermes_memory_wiki/vector_index.py`
- Create: `tests/test_vector_index.py`

**Step 1: Write failing tests**

Test cases:

- page document includes title/path/kind/claims/questions/body;
- claim document includes claim text, page title, source ids, evidence;
- document ids are deterministic;
- text hash changes when text changes;
- generated related blocks and frontmatter are excluded from body text.

**Step 2: Run tests**

```bash
pytest tests/test_vector_index.py -q
```

**Step 3: Implement document builder**

Expose:

```python
@dataclass
class SearchDocument:
    id: str
    page_path: str
    kind: str
    title: str
    doc_type: Literal["page", "claim"]
    text: str
    text_hash: str
    metadata: dict[str, Any]

def build_search_documents(pages: Sequence[WikiPageSummary]) -> list[SearchDocument]: ...
```

**Step 4: Run tests**

```bash
pytest tests/test_vector_index.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vector_index.py tests/test_vector_index.py
git commit -m "feat: build wiki vector search documents"
```

### Task 5.3: Implement SQLite vector index storage

**Objective:** Persist search documents and embeddings locally.

**Files:**

- Modify: `src/hermes_memory_wiki/vector_index.py`
- Modify: `tests/test_vector_index.py`

**Step 1: Write failing tests**

Test cases:

- creates SQLite schema;
- upserts documents;
- stores embeddings;
- skips unchanged embeddings by hash/provider/model;
- deletes stale documents no longer present;
- loads all embeddings for a provider/model.

**Step 2: Run tests**

```bash
pytest tests/test_vector_index.py -q
```

**Step 3: Implement SQLite store**

Expose:

```python
class VectorIndex:
    def __init__(self, db_path: Path): ...
    def upsert_documents(self, docs: Sequence[SearchDocument]) -> None: ...
    def stale_documents_for_embedding(self, provider: EmbeddingProvider) -> list[SearchDocument]: ...
    def store_embeddings(...): ...
    def load_embeddings(...): ...
```

Store vectors as JSON for v1.

**Step 4: Run tests**

```bash
pytest tests/test_vector_index.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vector_index.py tests/test_vector_index.py
git commit -m "feat: persist wiki vector index in sqlite"
```

### Task 5.4: Implement reindex workflow

**Objective:** Rebuild or update embeddings for changed wiki docs.

**Files:**

- Modify: `src/hermes_memory_wiki/vector_index.py`
- Create/modify: `tests/test_reindex.py`

**Step 1: Write failing tests**

Test cases:

- reindex embeds all docs on first run;
- second run skips unchanged docs;
- force reindex re-embeds;
- changed page text re-embeds only changed docs;
- missing API key returns diagnostic without corrupting index.

**Step 2: Run tests**

```bash
pytest tests/test_reindex.py -q
```

**Step 3: Implement reindex function**

Expose:

```python
@dataclass
class ReindexResult:
    embedded_count: int
    skipped_count: int
    deleted_count: int
    provider: str
    model: str
    dimensions: int | None
    diagnostics: list[str]

def reindex_vault(config: MemoryWikiConfig, provider: EmbeddingProvider | None = None, *, force: bool = False) -> ReindexResult: ...
```

**Step 4: Run tests**

```bash
pytest tests/test_reindex.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vector_index.py tests/test_reindex.py
git commit -m "feat: reindex wiki embeddings incrementally"
```

### Task 5.5: Implement vector search

**Objective:** Search stored embeddings by cosine similarity.

**Files:**

- Modify: `src/hermes_memory_wiki/vector_index.py`
- Create: `tests/test_vector_search.py`

**Step 1: Write failing tests**

Test cases:

- cosine similarity ranks expected fake vectors;
- vector search embeds query once;
- returns page and claim results with snippets/metadata;
- handles empty/missing index gracefully;
- dimension mismatch is diagnosed.

**Step 2: Run tests**

```bash
pytest tests/test_vector_search.py -q
```

**Step 3: Implement vector search**

Expose:

```python
def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float: ...
def vector_search(config: MemoryWikiConfig, query: str, *, provider: EmbeddingProvider | None = None, max_results: int = 10, mode: str = "auto") -> list[WikiSearchResult]: ...
```

**Step 4: Run tests**

```bash
pytest tests/test_vector_search.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vector_index.py tests/test_vector_search.py
git commit -m "feat: search wiki vector index"
```

---

## Phase 6: Hybrid search

### Task 6.1: Implement score normalization and rank fusion

**Objective:** Combine keyword and vector results predictably.

**Files:**

- Create: `src/hermes_memory_wiki/hybrid_search.py`
- Create: `tests/test_hybrid_search.py`

**Step 1: Write failing tests**

Test cases:

- keyword-only results are returned when vector unavailable;
- vector-only results are returned for vector mode;
- hybrid combines same page hits by path/doc id;
- lexical/vector weights are respected;
- mode boosts remain applied;
- diagnostics explain fallback.

**Step 2: Run tests**

```bash
pytest tests/test_hybrid_search.py -q
```

**Step 3: Implement hybrid search**

Expose:

```python
@dataclass
class SearchDiagnostics:
    requested_mode: str
    effective_mode: str
    vector_available: bool
    messages: list[str]

def search_wiki(config: MemoryWikiConfig, query: str, *, max_results: int = 10, mode: str = "auto", search_mode: str | None = None, provider: EmbeddingProvider | None = None) -> tuple[list[WikiSearchResult], SearchDiagnostics]: ...
```

**Step 4: Run tests**

```bash
pytest tests/test_hybrid_search.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/hybrid_search.py tests/test_hybrid_search.py
git commit -m "feat: add hybrid wiki search"
```

---

## Phase 7: Get/apply/compile/lint workflows

### Task 7.1: Implement lookup and `wiki_get` core

**Objective:** Resolve pages by path/id/title/basename/claim id and return excerpts.

**Files:**

- Modify: `src/hermes_memory_wiki/vault.py`
- Create: `tests/test_get.py`

**Step 1: Write failing tests**

Test cases:

- exact path lookup;
- lookup without `.md`;
- basename lookup;
- frontmatter id lookup;
- title lookup;
- claim id lookup returns parent page;
- line slicing returns expected content/truncated flag.

**Step 2: Run tests**

```bash
pytest tests/test_get.py -q
```

**Step 3: Implement get helpers**

Expose:

```python
@dataclass
class GetPageResult: ...
def get_page(config: MemoryWikiConfig, lookup: str, *, from_line: int = 1, line_count: int = 200) -> GetPageResult | None: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:2209-2286`.

**Step 4: Run tests**

```bash
pytest tests/test_get.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/vault.py tests/test_get.py
git commit -m "feat: resolve and read wiki pages"
```

### Task 7.2: Implement `create_synthesis` mutation

**Objective:** Create or update synthesis pages through structured mutations.

**Files:**

- Create: `src/hermes_memory_wiki/apply.py`
- Create: `tests/test_apply.py`

**Step 1: Write failing tests**

Test cases:

- title/body/sourceIds required;
- slug path is deterministic under `syntheses/`;
- page id defaults to `synthesis.<slug>`;
- frontmatter contains claims/sourceIds/status/updatedAt;
- generated summary block is written;
- human notes block exists and is preserved on update.

**Step 2: Run tests**

```bash
pytest tests/test_apply.py -q
```

**Step 3: Implement create synthesis**

Expose:

```python
def normalize_mutation(raw: Mapping[str, Any]) -> WikiMutation: ...
def apply_mutation(config: MemoryWikiConfig, mutation: WikiMutation) -> ApplyResult: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:2293-2385`.

**Step 4: Run tests**

```bash
pytest tests/test_apply.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/apply.py tests/test_apply.py
git commit -m "feat: create wiki synthesis mutations"
```

### Task 7.3: Implement `update_metadata` mutation

**Objective:** Update existing page metadata safely.

**Files:**

- Modify: `src/hermes_memory_wiki/apply.py`
- Modify: `tests/test_apply.py`

**Step 1: Write failing tests**

Test cases:

- lookup required;
- missing page raises clear error;
- sourceIds update replaces normalized source IDs;
- empty claims remove claims field;
- confidence null removes confidence;
- body is preserved;
- updatedAt changes.

**Step 2: Run tests**

```bash
pytest tests/test_apply.py -q
```

**Step 3: Implement update metadata**

Reference OpenClaw `cli-Cx8TeRn1.js:2386-2432`.

**Step 4: Run tests**

```bash
pytest tests/test_apply.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/apply.py tests/test_apply.py
git commit -m "feat: update wiki page metadata"
```

### Task 7.4: Implement compile cache and indexes

**Objective:** Generate indexes, dashboards, and cache files.

**Files:**

- Create: `src/hermes_memory_wiki/compile.py`
- Create: `tests/test_compile.py`

**Step 1: Write failing tests**

Test cases:

- root index includes page counts;
- directory indexes list pages by kind;
- `agent-digest.json` includes pages and claim counts;
- `claims.jsonl` contains one claim per line;
- `search-docs.jsonl` contains page/claim docs;
- compile is idempotent if nothing changed;
- compile appends log when files update.

**Step 2: Run tests**

```bash
pytest tests/test_compile.py -q
```

**Step 3: Implement compile**

Expose:

```python
@dataclass
class CompileResult:
    vault_root: Path
    page_counts: dict[str, int]
    claim_count: int
    updated_files: list[Path]

def compile_vault(config: MemoryWikiConfig) -> CompileResult: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:1283-1350`.

Keep dashboard set small for v1:

- Open Questions
- Contradictions
- Low Confidence
- Claim Health
- Stale Pages
- Provenance Coverage

**Step 4: Run tests**

```bash
pytest tests/test_compile.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/compile.py tests/test_compile.py
git commit -m "feat: compile wiki indexes and caches"
```

### Task 7.5: Implement lint

**Objective:** Surface wiki structural and knowledge-health issues.

**Files:**

- Create: `src/hermes_memory_wiki/lint.py`
- Create: `tests/test_lint.py`

**Step 1: Write failing tests**

Test cases:

- missing claim evidence creates provenance warning;
- contradictions create contradiction issue;
- questions create open-question issue;
- low confidence creates low-confidence issue;
- stale updatedAt creates stale issue;
- duplicate ids create schema error;
- broken source links create broken-link issue;
- stale vector index creates vector-index warning;
- lint report written as markdown and JSON.

**Step 2: Run tests**

```bash
pytest tests/test_lint.py -q
```

**Step 3: Implement lint**

Expose:

```python
@dataclass
class LintIssue: ...
@dataclass
class LintResult: ...
def lint_vault(config: MemoryWikiConfig) -> LintResult: ...
```

Reference OpenClaw `cli-Cx8TeRn1.js:3260 onward`.

**Step 4: Run tests**

```bash
pytest tests/test_lint.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/lint.py tests/test_lint.py
git commit -m "feat: lint wiki health and provenance"
```

---

## Phase 8: Hermes tools and skills

### Task 8.1: Register plugin tools

**Objective:** Expose core workflows as Hermes tools under `memory_wiki` toolset.

**Files:**

- Create: `src/hermes_memory_wiki/tools.py`
- Modify: `src/hermes_memory_wiki/plugin.py`
- Create: `tests/test_tools.py`

**Step 1: Write failing tests**

Create fake context:

```python
class FakeContext:
    def __init__(self):
        self.tools = {}
        self.skills = {}
    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}
    def register_skill(self, name, path, description=""):
        self.skills[name] = {"path": path, "description": description}
```

Test:

- `register(ctx)` registers all expected tools;
- every tool uses toolset `memory_wiki`;
- schemas reject missing required fields where relevant;
- handlers return text content and details.

**Step 2: Run tests**

```bash
pytest tests/test_tools.py -q
```

**Step 3: Implement tool registration**

Tools:

- `wiki_init`
- `wiki_status`
- `wiki_search`
- `wiki_get`
- `wiki_apply`
- `wiki_compile`
- `wiki_reindex`
- `wiki_lint`

Use JSON-schema-like dicts accepted by Hermes `ctx.register_tool`.

**Step 4: Run tests**

```bash
pytest tests/test_tools.py -q
```

**Step 5: Commit**

```bash
git add src/hermes_memory_wiki/tools.py src/hermes_memory_wiki/plugin.py tests/test_tools.py
git commit -m "feat: register hermes wiki tools"
```

### Task 8.2: Add plugin manifest for user-plugin layout

**Objective:** Make the repo copyable into `~/.hermes/plugins/memory-wiki`.

**Files:**

- Create: `plugin.yaml`
- Create: `__init__.py`
- Create: `tests/test_user_plugin_layout.py`

**Step 1: Write failing test**

Test:

- root `__init__.py` exposes `register` imported from package;
- `plugin.yaml` includes expected name and tools.

**Step 2: Run test**

```bash
pytest tests/test_user_plugin_layout.py -q
```

**Step 3: Implement root plugin files**

`plugin.yaml`:

```yaml
name: memory-wiki
version: 0.1.0
kind: standalone
description: Hermes memory wiki tools with hybrid keyword/vector search.
provides_tools:
  - wiki_init
  - wiki_status
  - wiki_search
  - wiki_get
  - wiki_apply
  - wiki_compile
  - wiki_reindex
  - wiki_lint
```

Root `__init__.py`:

```python
from hermes_memory_wiki.plugin import register
```

**Step 4: Run tests**

```bash
pytest tests/test_user_plugin_layout.py -q
```

**Step 5: Commit**

```bash
git add plugin.yaml __init__.py tests/test_user_plugin_layout.py
git commit -m "feat: add hermes user plugin layout"
```

### Task 8.3: Add plugin skills

**Objective:** Ship wiki workflow skills with the plugin.

**Files:**

- Create: `src/hermes_memory_wiki/skills/wiki-maintainer/SKILL.md`
- Create: `src/hermes_memory_wiki/skills/wiki-authoring/SKILL.md`
- Create: `src/hermes_memory_wiki/skills/wiki-search/SKILL.md`
- Modify: `src/hermes_memory_wiki/plugin.py`
- Modify: `tests/test_tools.py` or create `tests/test_skills.py`

**Step 1: Write failing tests**

Test:

- `register(ctx)` registers three skills;
- skill paths exist;
- skill docs mention correct Hermes tools, not OpenClaw CLI commands.

**Step 2: Run tests**

```bash
pytest tests/test_skills.py -q
```

**Step 3: Write skill documents**

Adapt from:

- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/wiki-maintainer/SKILL.md`
- `/home/langley/.npm-global/lib/node_modules/openclaw/dist/extensions/memory-wiki/skills/obsidian-vault-maintainer/SKILL.md`

Remove bridge/unsafe-local/OpenClaw CLI references unless documented as non-goals.

**Step 4: Register skills**

In `plugin.py`, call:

```python
ctx.register_skill("wiki-maintainer", path_to_skill, description="Maintain Hermes memory wiki vaults safely.")
```

**Step 5: Run tests**

```bash
pytest tests/test_skills.py -q
```

**Step 6: Commit**

```bash
git add src/hermes_memory_wiki/skills src/hermes_memory_wiki/plugin.py tests/test_skills.py
git commit -m "feat: add memory wiki skills"
```

---

## Phase 9: Documentation and install workflow

### Task 9.1: Document installation and configuration

**Objective:** Explain how to install without modifying Hermes core.

**Files:**

- Modify: `README.md`
- Create: `docs/installation.md`
- Create: `docs/configuration.md`

**Step 1: Write docs**

Cover:

- pip editable install;
- user-plugin copy/symlink install;
- enabling plugin in Hermes config;
- enabling `memory_wiki` toolset;
- setting `OPENAI_API_KEY`;
- disabling embeddings;
- initializing vault;
- running first reindex.

**Step 2: Verify docs commands are plausible**

Run non-destructive commands only:

```bash
python -m pip install -e .
python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
```

**Step 3: Commit**

```bash
git add README.md docs/installation.md docs/configuration.md
git commit -m "docs: add installation and configuration guide"
```

### Task 9.2: Add development guide

**Objective:** Document test and contribution workflow.

**Files:**

- Create: `docs/development.md`

Include:

- TDD expectations;
- test commands;
- live OpenAI tests opt-in;
- source-reference notes;
- privacy/security notes;
- release checklist.

**Commit:**

```bash
git add docs/development.md
git commit -m "docs: add development workflow"
```

---

## Phase 10: Integration smoke test

### Task 10.1: Add local plugin registration smoke test script

**Objective:** Verify plugin can register with a fake Hermes context and run basic workflow.

**Files:**

- Create: `scripts/smoke_fake_hermes.py`
- Create: `tests/test_smoke_workflow.py`

**Step 1: Write failing integration test**

Workflow:

1. temp vault;
2. register plugin with fake context;
3. call `wiki_init`;
4. call `wiki_apply` create synthesis;
5. call `wiki_compile`;
6. call `wiki_reindex` with fake provider injection if available;
7. call `wiki_search` hybrid;
8. call `wiki_get`;
9. call `wiki_lint`.

**Step 2: Run test**

```bash
pytest tests/test_smoke_workflow.py -q
```

**Step 3: Implement script/test support**

Keep script optional but useful for manual debugging.

**Step 4: Run all tests**

```bash
pytest -q
```

**Step 5: Commit**

```bash
git add scripts/smoke_fake_hermes.py tests/test_smoke_workflow.py
git commit -m "test: add wiki workflow smoke test"
```

---

## Phase 11: Review and final verification

### Task 11.1: Spec compliance review

**Objective:** Verify implementation matches the approved design.

Checklist:

- [ ] No OpenClaw runtime dependency.
- [ ] No bridge-mode implementation.
- [ ] Default vault path is `~/.hermes/wiki/main`.
- [ ] Toolset is `memory_wiki`.
- [ ] Tools include all required v1 tools.
- [ ] Keyword search works without API key.
- [ ] Vector search uses OpenAI embeddings when configured.
- [ ] Hybrid search degrades cleanly.
- [ ] Skills are registered and accurate.
- [ ] Writes are restricted to configured vault root.
- [ ] Tests pass offline.

Use a reviewer subagent via `requesting-code-review`/`subagent-driven-development`.

### Task 11.2: Code quality review

**Objective:** Review maintainability, security, test coverage, and ergonomics.

Checklist:

- [ ] Clear module boundaries.
- [ ] Small functions.
- [ ] No leaked API keys.
- [ ] No broad exception swallowing that hides user-facing errors.
- [ ] SQLite connections handled safely.
- [ ] Deterministic tests.
- [ ] No network access in default tests.
- [ ] Helpful diagnostics.

### Task 11.3: Final verification

Run:

```bash
python -m pytest -q
python -m compileall src tests
python -m pip install -e .
python -c 'import hermes_memory_wiki; print(hermes_memory_wiki.__version__)'
```

If live test is explicitly allowed and `OPENAI_API_KEY` is available:

```bash
HERMES_MEMORY_WIKI_LIVE_OPENAI=1 pytest tests/live -v
```

### Task 11.4: Push and PR

```bash
git status --short
git push -u origin feat/initial-hermes-memory-wiki-plugin
gh pr create --title "Build initial Hermes memory wiki plugin" --body-file docs/pr-body.md
```

Merge only after review/verification passes.
