"""Vault initialization for Hermes memory wiki."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.markdown import WikiMarkdownError
from hermes_memory_wiki.schema import WikiPageSummary, to_page_summary


METADATA_DIRECTORY = ".hermes-wiki"
QUERY_DIRS = ["entities", "concepts", "sources", "syntheses", "reports"]

_REQUIRED_DIRECTORIES = [
    Path("sources"),
    Path("entities"),
    Path("concepts"),
    Path("syntheses"),
    Path("reports"),
    Path(METADATA_DIRECTORY),
    Path(METADATA_DIRECTORY) / "cache",
    Path(METADATA_DIRECTORY) / "vector",
]

_STARTER_FILES = {
    Path("AGENTS.md"): "# Hermes Memory Wiki Agents\n\nGuidance for agents working with this vault.\n",
    Path("WIKI.md"): "# Hermes Memory Wiki\n\nThis vault stores durable memory as linked Markdown pages.\n",
    Path("index.md"): "# Memory Wiki Index\n\n- [Inbox](inbox.md)\n- [Sources](sources/)\n- [Entities](entities/)\n- [Concepts](concepts/)\n- [Syntheses](syntheses/)\n- [Reports](reports/)\n",
    Path("inbox.md"): "# Inbox\n\nCapture unsorted notes here before promoting them into wiki pages.\n",
}


@dataclass
class InitResult:
    root: Path
    created: bool
    created_directories: list[Path]
    created_files: list[Path]


def list_wiki_markdown_files(root: Path) -> list[str]:
    """List immediate Markdown pages from queryable wiki directories."""
    files: list[str] = []
    for query_directory in QUERY_DIRS:
        directory = root / query_directory
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix != ".md" or path.name == "index.md":
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
