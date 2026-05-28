from hermes_memory_wiki.schema import WikiPageSummary
from hermes_memory_wiki.vault import (
    QUERY_DIRS,
    list_wiki_markdown_files,
    read_queryable_pages,
)


def _write(root, relative_path, content="# Title\n\nBody.\n"):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_lists_immediate_markdown_files_in_query_dirs_sorted_lexicographically(tmp_path):
    root = tmp_path / "vault"
    for directory in QUERY_DIRS:
        _write(root, f"{directory}/b.md")
        _write(root, f"{directory}/a.md")
        _write(root, f"{directory}/not-markdown.txt", "not markdown")
        _write(root, f"{directory}/nested/c.md")

    assert list_wiki_markdown_files(root) == [
        "concepts/a.md",
        "concepts/b.md",
        "entities/a.md",
        "entities/b.md",
        "reports/a.md",
        "reports/b.md",
        "sources/a.md",
        "sources/b.md",
        "syntheses/a.md",
        "syntheses/b.md",
    ]


def test_excludes_query_directory_index_markdown_files(tmp_path):
    root = tmp_path / "vault"
    _write(root, "sources/index.md")
    _write(root, "sources/source-1.md")
    _write(root, "entities/index.md")
    _write(root, "entities/person-1.md")

    assert list_wiki_markdown_files(root) == [
        "entities/person-1.md",
        "sources/source-1.md",
    ]


def test_ignores_files_outside_query_dirs_and_missing_query_dirs(tmp_path):
    root = tmp_path / "vault"
    _write(root, "inbox.md")
    _write(root, "index.md")
    _write(root, "misc/note.md")
    _write(root, ".hermes-wiki/cache/page.md")
    _write(root, "reports/weekly.md")

    assert list_wiki_markdown_files(root) == ["reports/weekly.md"]


def test_ignores_symlinked_markdown_files_that_escape_vault(tmp_path):
    root = tmp_path / "vault"
    _write(root, "sources/good.md", "# Good\n\nSafe.\n")
    secret = _write(tmp_path / "outside", "secret.md", "# Secret\n\nDo not read.\n")
    symlink = root / "sources" / "secret.md"
    symlink.symlink_to(secret)

    assert list_wiki_markdown_files(root) == ["sources/good.md"]
    assert [page.path for page in read_queryable_pages(root)] == ["sources/good.md"]


def test_ignores_symlinked_query_directories_that_escape_vault(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    outside_sources = tmp_path / "outside-sources"
    _write(outside_sources, "secret.md", "# Secret\n\nDo not read.\n")
    (root / "sources").symlink_to(outside_sources, target_is_directory=True)
    _write(root, "entities/good.md", "# Good\n\nSafe.\n")

    assert list_wiki_markdown_files(root) == ["entities/good.md"]
    assert [page.path for page in read_queryable_pages(root)] == ["entities/good.md"]


def test_read_queryable_pages_returns_page_summaries_from_raw_content(tmp_path):
    root = tmp_path / "vault"
    _write(
        root,
        "entities/ada.md",
        """---
id: entity.ada
title: Ada Lovelace
pageType: entity
entityType: person
aliases:
  - Countess of Lovelace
sourceIds:
  - source:notes
---
# Ignored Heading

Ada wrote notes.
""",
    )
    _write(root, "sources/source-notes.md", "# Source Notes\n\nRaw source body.\n")

    pages = read_queryable_pages(root)

    assert [page.path for page in pages] == ["entities/ada.md", "sources/source-notes.md"]
    assert all(isinstance(page, WikiPageSummary) for page in pages)
    ada = pages[0]
    assert ada.kind == "entity"
    assert ada.page_type == "entity"
    assert ada.entity_type == "person"
    assert ada.id == "entity.ada"
    assert ada.title == "Ada Lovelace"
    assert ada.aliases == ["Countess of Lovelace"]
    assert ada.source_ids == ["source:notes"]
    assert ada.body == "# Ignored Heading\n\nAda wrote notes.\n"
    source = pages[1]
    assert source.kind == "source"
    assert source.id == "source:source-notes"
    assert source.title == "Source Notes"
    assert source.body == "# Source Notes\n\nRaw source body.\n"


def test_read_queryable_pages_skips_invalid_markdown_pages(tmp_path):
    root = tmp_path / "vault"
    _write(root, "sources/good.md", "# Good\n\nValid.\n")
    _write(root, "sources/bad.md", "---\ntitle: [unterminated\n---\n# Bad\n")

    pages = read_queryable_pages(root)

    assert [page.path for page in pages] == ["sources/good.md"]
