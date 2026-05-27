import json
from datetime import datetime, timezone

import pytest

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.vault import initialize_vault


REQUIRED_DIRECTORIES = [
    "sources",
    "entities",
    "concepts",
    "syntheses",
    "reports",
    ".hermes-wiki",
    ".hermes-wiki/cache",
    ".hermes-wiki/vector",
]

REQUIRED_FILES = [
    "AGENTS.md",
    "WIKI.md",
    "index.md",
    "inbox.md",
    ".hermes-wiki/state.json",
    ".hermes-wiki/log.jsonl",
]


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def _init_time():
    return datetime(2026, 5, 27, 12, 30, 45, tzinfo=timezone.utc)


def _log_entries(root):
    log_path = root / ".hermes-wiki" / "log.jsonl"
    return [json.loads(line) for line in log_path.read_text().splitlines() if line]


def test_initialization_creates_required_directories_and_files(tmp_path):
    root = tmp_path / "vault"

    result = initialize_vault(_config(root), now=_init_time())

    assert result.root == root
    assert result.created is True
    for relative_path in REQUIRED_DIRECTORIES:
        assert (root / relative_path).is_dir()
        assert root / relative_path in result.created_directories
    for relative_path in REQUIRED_FILES:
        assert (root / relative_path).is_file()
        assert root / relative_path in result.created_files

    state = json.loads((root / ".hermes-wiki" / "state.json").read_text())
    assert state["version"] == 1
    assert state["createdAt"] == "2026-05-27T12:30:45+00:00"


def test_second_initialization_is_idempotent(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root), now=_init_time())

    result = initialize_vault(_config(root), now=_init_time())

    assert result.root == root
    assert result.created is False
    assert result.created_directories == []
    assert result.created_files == []
    assert len(_log_entries(root)) == 1


def test_existing_inbox_content_is_not_overwritten(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    inbox = root / "inbox.md"
    original = "# My inbox\n\nDo not replace this.\n"
    inbox.write_text(original)

    result = initialize_vault(_config(root), now=_init_time())

    assert inbox.read_text() == original
    assert inbox not in result.created_files


def test_log_entry_is_appended_only_when_something_changed(tmp_path):
    root = tmp_path / "vault"

    first = initialize_vault(_config(root), now=_init_time())
    second = initialize_vault(_config(root), now=_init_time())

    entries = _log_entries(root)
    assert first.created is True
    assert second.created is False
    assert len(entries) == 1
    assert entries[0]["event"] == "init"
    assert entries[0]["createdAt"] == "2026-05-27T12:30:45+00:00"
    assert "sources" in entries[0]["createdDirectories"]
    assert "AGENTS.md" in entries[0]["createdFiles"]


def test_metadata_directory_is_hermes_wiki(tmp_path):
    root = tmp_path / "vault"

    initialize_vault(_config(root), now=_init_time())

    assert (root / ".hermes-wiki").is_dir()
    assert not (root / ".openclaw-wiki").exists()


def test_rejects_metadata_directory_symlink_without_writing_outside_vault(tmp_path):
    root = tmp_path / "vault"
    external = tmp_path / "external-metadata"
    root.mkdir()
    external.mkdir()
    (root / ".hermes-wiki").symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        initialize_vault(_config(root), now=_init_time())

    assert not (external / "state.json").exists()
    assert not (external / "log.jsonl").exists()


def test_rejects_starter_file_symlink_without_writing_outside_vault(tmp_path):
    root = tmp_path / "vault"
    external = tmp_path / "external-files"
    external_target = external / "AGENTS.md"
    root.mkdir()
    external.mkdir()
    (root / "AGENTS.md").symlink_to(external_target)

    with pytest.raises(ValueError, match="symlink"):
        initialize_vault(_config(root), now=_init_time())

    assert not external_target.exists()
