from pathlib import Path

import pytest

from hermes_memory_wiki.paths import (
    normalize_relative_path,
    safe_join,
    to_display_path,
)


def test_safe_join_returns_path_under_root(tmp_path):
    root = tmp_path / "vault"

    path = safe_join(root, "sources/a.md")

    assert path == root.resolve() / "sources" / "a.md"
    assert path.is_relative_to(root.resolve())


def test_safe_join_rejects_parent_directory_traversal(tmp_path):
    root = tmp_path / "vault"

    with pytest.raises(ValueError, match="outside vault"):
        safe_join(root, "../outside.md")


def test_safe_join_rejects_absolute_paths_outside_root(tmp_path):
    root = tmp_path / "vault"
    outside = tmp_path / "outside.md"

    with pytest.raises(ValueError, match="outside vault"):
        safe_join(root, str(outside))


def test_normalize_relative_path_normalizes_windows_backslashes():
    assert normalize_relative_path(r"sources\nested\a.md") == "sources/nested/a.md"


def test_normalize_relative_path_strips_leading_current_directory():
    assert normalize_relative_path("./sources/a.md") == "sources/a.md"


def test_to_display_path_returns_relative_posix_path(tmp_path):
    root = tmp_path / "vault"
    path = root / "sources" / "nested" / "a.md"

    assert to_display_path(root, path) == "sources/nested/a.md"


def test_to_display_path_rejects_paths_outside_root(tmp_path):
    root = tmp_path / "vault"
    outside = tmp_path / "outside.md"

    with pytest.raises(ValueError, match="outside vault"):
        to_display_path(root, outside)
