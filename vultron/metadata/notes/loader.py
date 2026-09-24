"""Loader for the notes/*.md frontmatter registry.

Loader requirements: specs/notes-frontmatter.yaml NF-03.
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.file_loading import (
    MetadataLoadError,
    display_path,
    load_frontmatter,
    validate,
)
from vultron.metadata.notes.schema import NotesFrontmatter

SKIP_FILES = {"README.md"}


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
        MetadataLoadError: If a notes file's frontmatter is missing, malformed,
            or fails schema validation. Names the file (NF-03-006); a
            ``ValueError`` subclass, so the NF-03-003 contract holds.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    root = repo_root or _find_repo_root()
    notes_dir = root / "notes"
    registry: dict[str, NotesFrontmatter] = {}

    for path in sorted(notes_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue

        post = load_frontmatter(path, root=root)
        if not post.metadata:
            raise MetadataLoadError(
                "missing YAML frontmatter", path=display_path(path, root)
            )

        key = str(path.relative_to(root))
        registry[key] = validate(
            NotesFrontmatter, post.metadata, path=path, root=root
        )

    return registry
