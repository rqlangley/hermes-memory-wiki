from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.vault import GetPageResult, get_page


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def _write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _sample_page(title="Ada Lovelace"):
    return f"""---
id: person:ada
title: {title}
pageType: person
claims:
  - id: claim:ada-first-programmer
    text: Ada is often described as the first computer programmer.
---
# Heading Ignored For Frontmatter Title

Line one.
Line two.
Line three.
"""


def test_get_page_resolves_exact_relative_path(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "entities/ada.md")

    assert isinstance(result, GetPageResult)
    assert result.path == "entities/ada.md"
    assert result.id == "person:ada"
    assert result.title == "Ada Lovelace"
    assert result.content == "# Heading Ignored For Frontmatter Title\n\nLine one.\nLine two.\nLine three."
    assert "person:ada" not in result.content


def test_get_page_resolves_path_without_md_extension(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "entities/ada")

    assert result is not None
    assert result.path == "entities/ada.md"


def test_get_page_resolves_basename(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "ada.md")

    assert result is not None
    assert result.path == "entities/ada.md"


def test_get_page_resolves_frontmatter_id(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "person:ada")

    assert result is not None
    assert result.path == "entities/ada.md"


def test_get_page_resolves_title(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page(title="Countess of Lovelace"))

    result = get_page(_config(root), "Countess of Lovelace")

    assert result is not None
    assert result.path == "entities/ada.md"


def test_get_page_resolves_claim_id_to_parent_page(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "claim:ada-first-programmer")

    assert result is not None
    assert result.path == "entities/ada.md"
    assert result.id == "person:ada"


def test_get_page_line_slicing_returns_expected_content_and_truncated_flag(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    result = get_page(_config(root), "entities/ada.md", from_line=3, line_count=2)

    assert result is not None
    assert result.content == "Line one.\nLine two."
    assert result.from_line == 3
    assert result.line_count == 2
    assert result.total_lines == 5
    assert result.truncated is True


def test_get_page_returns_none_for_missing_lookup(tmp_path):
    root = tmp_path / "vault"
    _write(root, "entities/ada.md", _sample_page())

    assert get_page(_config(root), "missing") is None
