"""Vault initialization for Hermes memory wiki."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import WikiMarkdownError
from hermes_memory_wiki.paths import normalize_relative_path
from hermes_memory_wiki.schema import WikiPageSummary, to_page_summary


METADATA_DIRECTORY = ".hermes-wiki"
QUERY_DIRS = ["entities", "concepts", "sources", "syntheses", "reports"]

_REQUIRED_DIRECTORIES = [
    Path("sources"),
    Path("entities"),
    Path("concepts"),
    Path("syntheses"),
    Path("reports"),
    Path("_attachments"),
    Path("_views"),
    Path(METADATA_DIRECTORY),
    Path(METADATA_DIRECTORY) / "locks",
    Path(METADATA_DIRECTORY) / "cache",
    Path(METADATA_DIRECTORY) / "vector",
]

_STARTER_FILES = {
    Path("AGENTS.md"): """# Memory Wiki Agent Guide

- Treat generated blocks as plugin-owned.
- Preserve human notes outside managed markers.
- Prefer source-backed claims over wiki-to-wiki citation loops.
- Prefer structured `claims` with evidence over burying key beliefs only in prose.
- Use `.hermes-wiki/cache/agent-digest.json` and `claims.jsonl` for machine reads; markdown pages are the human view.
- Keep broad page kinds in `pageType`; `entityType`, not `pageType`, stores the entity subtype such as person, organization, project, or system.
- Generated markers are `<!-- hermes:wiki:generated:start -->` / `<!-- hermes:wiki:generated:end -->`.
- Human notes belong outside managed regions or inside `<!-- hermes:human:start -->` / `<!-- hermes:human:end -->` blocks.
- Lint output belongs in `<!-- hermes:wiki:lint:start -->` / `<!-- hermes:wiki:lint:end -->` blocks.
""",
    Path("WIKI.md"): """# Memory Wiki

This vault is maintained by the Hermes memory-wiki plugin.

## Architecture

- Raw sources remain the evidence layer.
- Wiki pages are the human-readable synthesis layer.
- `.hermes-wiki/cache/agent-digest.json` is the agent-facing compiled digest.
- `.hermes-wiki/cache/claims.jsonl` is the structured claim stream for machine reads.
- Markdown pages are the editable human view; generated blocks are plugin-owned.
- `.hermes-wiki/vector/` is a Hermes extension for local vector search over the same corpus.

## Taxonomy

- `sources/` stores source pages with `pageType: source`.
- `entities/` stores entity pages with `pageType: entity`; use `entityType` for subtypes such as person, organization, project, or system.
- `concepts/` stores concept pages with `pageType: concept`.
- `syntheses/` stores synthesis pages with `pageType: synthesis`.
- `reports/` stores report pages with `pageType: report`.

## Generated

<!-- hermes:wiki:generated:start -->
No compiled summary yet.
<!-- hermes:wiki:generated:end -->

## Lint

<!-- hermes:wiki:lint:start -->
No lint results yet.
<!-- hermes:wiki:lint:end -->

## Notes

<!-- hermes:human:start -->
<!-- hermes:human:end -->
""",
    Path("index.md"): """# Wiki Index

## Generated

<!-- hermes:wiki:index:start -->
- No compiled pages yet.
<!-- hermes:wiki:index:end -->
""",
    Path("inbox.md"): "# Inbox\n\nDrop raw ideas, questions, and source links here.\n",
}


@dataclass
class InitResult:
    root: Path
    created: bool
    created_directories: list[Path]
    created_files: list[Path]


@dataclass(frozen=True)
class GetPageResult:
    path: str
    id: str
    title: str
    kind: str
    content: str
    from_line: int
    line_count: int
    total_lines: int
    truncated: bool
    page: WikiPageSummary


def get_page(
    config: MemoryWikiConfig,
    lookup: str,
    *,
    from_line: int = 1,
    line_count: int = 200,
) -> GetPageResult | None:
    """Resolve a queryable wiki page and return a frontmatter-free excerpt."""
    page = _resolve_page(config.vault_path, lookup)
    if page is None:
        return None

    lines = page.body.splitlines()
    total_lines = len(lines)
    safe_from_line = max(1, from_line)
    safe_line_count = max(0, line_count)
    start_index = min(total_lines, safe_from_line - 1)
    end_index = min(total_lines, start_index + safe_line_count)
    content = "\n".join(lines[start_index:end_index])
    truncated = start_index > 0 or end_index < total_lines

    return GetPageResult(
        path=page.path,
        id=page.id,
        title=page.title,
        kind=page.kind,
        content=content,
        from_line=safe_from_line,
        line_count=safe_line_count,
        total_lines=total_lines,
        truncated=truncated,
        page=page,
    )


def list_wiki_markdown_files(root: Path) -> list[str]:
    """List immediate Markdown pages from queryable wiki directories."""
    files: list[str] = []
    for query_directory in QUERY_DIRS:
        directory = root / query_directory
        if directory.is_symlink() or not directory.is_dir():
            continue
        for path in directory.iterdir():
            if (
                path.is_symlink()
                or not path.is_file()
                or path.suffix != ".md"
                or path.name == "index.md"
            ):
                continue
            files.append(path.relative_to(root).as_posix())
    return sorted(files)


def read_queryable_pages(root: Path) -> list[WikiPageSummary]:
    """Read queryable wiki Markdown files into normalized page summaries."""
    pages: list[WikiPageSummary] = []
    for relative_path in list_wiki_markdown_files(root):
        raw = (root / relative_path).read_text(encoding="utf-8")
        try:
            summary = to_page_summary(relative_path, raw)
        except WikiMarkdownError:
            continue
        if summary is not None:
            pages.append(summary)
    return pages


def _resolve_page(root: Path, lookup: str) -> WikiPageSummary | None:
    normalized_lookup = lookup.strip()
    if not normalized_lookup:
        return None

    pages = read_queryable_pages(root)
    by_path = {page.path: page for page in pages}

    for candidate in _lookup_path_candidates(normalized_lookup):
        page = by_path.get(candidate)
        if page is not None:
            return page

    basename_matches = [
        page
        for page in pages
        if PurePosixPath(page.path).name == normalized_lookup
        or PurePosixPath(page.path).stem == normalized_lookup
    ]
    if basename_matches:
        return basename_matches[0]

    for page in pages:
        if page.id == normalized_lookup:
            return page

    for page in pages:
        if page.title == normalized_lookup:
            return page

    for page in pages:
        if normalized_lookup in page.aliases:
            return page

    for page in pages:
        if any(claim.id == normalized_lookup for claim in page.claims):
            return page

    return None


def _lookup_path_candidates(lookup: str) -> list[str]:
    try:
        normalized = normalize_relative_path(lookup)
    except ValueError:
        return []

    candidates = [normalized]
    if PurePosixPath(normalized).suffix != ".md":
        candidates.append(f"{normalized}.md")
    return candidates


def initialize_vault(
    config: MemoryWikiConfig, *, now: datetime | None = None
) -> InitResult:
    """Create the standard Hermes memory wiki vault structure if missing."""
    root = config.vault_path
    timestamp = _timestamp(now)
    created_directories: list[Path] = []
    created_files: list[Path] = []

    _reject_symlink(root, "Vault path")
    if not root.exists():
        root.mkdir(parents=True)
        created_directories.append(root)
    elif not root.is_dir():
        raise NotADirectoryError(f"Vault path exists and is not a directory: {root}")

    for relative_directory in _REQUIRED_DIRECTORIES:
        directory = root / relative_directory
        _reject_symlink(directory, "Vault directory path")
        if not directory.exists():
            directory.mkdir(parents=True)
            created_directories.append(directory)
        elif not directory.is_dir():
            raise NotADirectoryError(
                f"Vault directory path exists and is not a directory: {directory}"
            )

    for relative_file, content in _STARTER_FILES.items():
        path = root / relative_file
        _reject_symlink(path, "Vault file path")
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created_files.append(path)
        elif not path.is_file():
            raise IsADirectoryError(f"Vault file path exists and is not a file: {path}")

    state_path = root / METADATA_DIRECTORY / "state.json"
    _reject_symlink(state_path, "Vault file path")
    if not state_path.exists():
        state_path.write_text(
            json.dumps({"version": 1, "createdAt": timestamp}, indent=2) + "\n",
            encoding="utf-8",
        )
        created_files.append(state_path)
    elif not state_path.is_file():
        raise IsADirectoryError(f"Vault file path exists and is not a file: {state_path}")

    log_path = root / METADATA_DIRECTORY / "log.jsonl"
    _reject_symlink(log_path, "Vault file path")
    if not log_path.exists():
        log_path.write_text("", encoding="utf-8")
        created_files.append(log_path)
    elif not log_path.is_file():
        raise IsADirectoryError(f"Vault file path exists and is not a file: {log_path}")

    created = bool(created_directories or created_files)
    if created:
        _append_init_log(
            root,
            log_path,
            timestamp,
            created_directories=created_directories,
            created_files=created_files,
        )

    return InitResult(
        root=root,
        created=created,
        created_directories=created_directories,
        created_files=created_files,
    )


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {path}")


def _timestamp(now: datetime | None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    return now.isoformat()


def _append_init_log(
    root: Path,
    log_path: Path,
    timestamp: str,
    *,
    created_directories: list[Path],
    created_files: list[Path],
) -> None:
    entry = {
        "event": "init",
        "createdAt": timestamp,
        "createdDirectories": [
            _display_path(root, path) for path in created_directories
        ],
        "createdFiles": [_display_path(root, path) for path in created_files],
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _display_path(root: Path, path: Path) -> str:
    if path == root:
        return "."
    return path.relative_to(root).as_posix()
