"""Loader for the notes/*.md frontmatter registry.

Loader requirements: specs/notes-frontmatter.md NF-03.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter

from vultron.metadata.notes.schema import NotesFrontmatter

SKIP_FILES = {"README.md"}


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Satisfies NF-03-005: works regardless of the caller's working directory.
    """
    origin = start or Path.cwd()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) starting from {origin}"
    )


def load_notes_registry(
    repo_root: Path | None = None,
) -> dict[str, NotesFrontmatter]:
    """Discover and validate frontmatter for all ``notes/*.md`` files.

    Args:
        repo_root: Repository root path.  When ``None`` the root is resolved
            automatically by searching upward for ``pyproject.toml``.

    Returns:
        Mapping from relative file path (e.g. ``"notes/bt-integration.md"``)
        to validated :class:`NotesFrontmatter` instance.

    Raises:
        ValueError: If a notes file is missing frontmatter or its frontmatter
            fails schema validation.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    root = repo_root or _find_repo_root()
    notes_dir = root / "notes"
    registry: dict[str, NotesFrontmatter] = {}

    for path in sorted(notes_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue

        post = frontmatter.load(str(path))
        if not post.metadata:
            raise ValueError(f"{path}: missing YAML frontmatter")

        key = str(path.relative_to(root))
        registry[key] = NotesFrontmatter.model_validate(post.metadata)

    return registry
