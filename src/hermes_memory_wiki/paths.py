"""Path safety helpers for files in a configured memory wiki vault."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


_LEADING_CURRENT_DIR = "./"


def normalize_relative_path(value: str) -> str:
    """Normalize a user-facing relative wiki path to POSIX separators.

    Backslashes are accepted as separators for convenience. Empty paths,
    absolute paths, and paths containing parent-directory traversal are rejected.
    """
    normalized = value.replace("\\", "/").strip()
    while normalized.startswith(_LEADING_CURRENT_DIR):
        normalized = normalized[len(_LEADING_CURRENT_DIR) :]

    if not normalized:
        raise ValueError("path must not be empty")
    if Path(normalized).is_absolute() or PureWindowsPath(normalized).is_absolute():
        raise ValueError("path must be relative")

    parts = PurePosixPath(normalized).parts
    if any(part == ".." for part in parts):
        raise ValueError("path must not contain parent directory traversal")

    return PurePosixPath(normalized).as_posix()


def safe_join(root: Path, relative: str) -> Path:
    """Join a vault root and relative wiki path, rejecting vault escapes."""
    root_resolved = root.resolve()

    try:
        normalized = normalize_relative_path(relative)
    except ValueError as exc:
        raise ValueError(f"path is outside vault: {relative}") from exc

    candidate = (root_resolved / normalized).resolve()
    _ensure_inside(root_resolved, candidate)
    return candidate


def to_display_path(root: Path, path: Path) -> str:
    """Return a vault-relative POSIX display path for an absolute or relative path."""
    root_resolved = root.resolve()
    candidate = path.resolve()
    _ensure_inside(root_resolved, candidate)
    return candidate.relative_to(root_resolved).as_posix()


def _ensure_inside(root: Path, candidate: Path) -> None:
    if candidate == root:
        return
    if not candidate.is_relative_to(root):
        raise ValueError(f"path is outside vault: {candidate}")
