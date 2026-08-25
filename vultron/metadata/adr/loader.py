"""Loader for the docs/adr/*.md frontmatter registry.

Loader requirements: specs/meta-specifications.yaml MS-14 (ADR-0043).

Mirrors ``vultron.metadata.notes.loader``. Discovers every ADR under
``docs/adr/`` (and ``docs/adr/archived/``), validates its frontmatter against
:class:`~vultron.metadata.adr.schema.AdrFrontmatter`, and checks that any
``superseded_by`` target resolves to a real ADR file.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter

from vultron.metadata.adr.schema import AdrFrontmatter

# Files under docs/adr/ that are not decision records.
SKIP_FILES = {"index.md", "README.md"}


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``."""
    origin = start or Path.cwd()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) from {origin}"
    )


def load_adr_post(path: Path) -> frontmatter.Post:
    """Parse an ADR markdown file, raising ``ValueError`` on malformed YAML.

    ``frontmatter.load`` raises ``yaml`` parser/scanner errors on a malformed
    frontmatter block; those are neither ``ValueError`` nor
    ``FileNotFoundError``, so without this wrapper they escape the documented
    contract and crash ``spec-lint`` and the pre-commit hooks with a raw
    traceback instead of a clean, file-attributed error.
    """
    try:
        return frontmatter.load(str(path))
    except FileNotFoundError:
        raise
    except Exception as exc:  # noqa: BLE001 — re-raise with file context
        raise ValueError(f"{path}: malformed YAML frontmatter: {exc}") from exc


def _iter_adr_paths(adr_dir: Path) -> list[Path]:
    """Return ADR markdown paths in ``adr_dir`` and its ``archived/`` subdir.

    Skips the index, READMEs, and template files (``_*.md``).
    """
    paths = list(adr_dir.glob("*.md")) + list(
        (adr_dir / "archived").glob("*.md")
    )
    return sorted(
        p
        for p in paths
        if p.name not in SKIP_FILES and not p.name.startswith("_")
    )


def load_adr_registry(
    repo_root: Path | None = None,
) -> dict[str, AdrFrontmatter]:
    """Discover and validate frontmatter for all ``docs/adr/*.md`` files.

    Args:
        repo_root: Repository root. When ``None`` it is resolved by searching
            upward for ``pyproject.toml``.

    Returns:
        Mapping from relative path (e.g. ``"docs/adr/0009-hexagonal-...md"``)
        to validated :class:`AdrFrontmatter`.

    Raises:
        ValueError: If an ADR is missing frontmatter, fails schema validation,
            or names a ``superseded_by`` target that does not resolve to a file.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    root = repo_root or _find_repo_root()
    adr_dir = root / "docs" / "adr"
    registry: dict[str, AdrFrontmatter] = {}

    for path in _iter_adr_paths(adr_dir):
        post = load_adr_post(path)
        if not post.metadata:
            raise ValueError(f"{path}: missing YAML frontmatter")

        key = str(path.relative_to(root))
        try:
            fm = AdrFrontmatter.model_validate(post.metadata)
        except Exception as exc:  # noqa: BLE001 — re-raise with file context
            raise ValueError(f"{key}: {exc}") from exc

        if fm.superseded_by and not _superseded_target_exists(
            adr_dir, fm.superseded_by
        ):
            raise ValueError(
                f"{key}: superseded_by '{fm.superseded_by}' does not resolve "
                f"to an ADR file in {adr_dir} or {adr_dir / 'archived'}"
            )

        registry[key] = fm

    return registry


def _superseded_target_exists(adr_dir: Path, target: str) -> bool:
    """Return True if a ``superseded_by`` value points at a real ADR file.

    Accepts a bare filename (``0041-....md``), a relative path, or an
    ``ADR-NNNN`` reference (resolved by the ``NNNN-*.md`` glob).
    """
    candidate = target.strip().strip("[]")
    # ADR-NNNN form → match by number.
    if candidate.upper().startswith("ADR-"):
        number = candidate.split("-", 1)[1].strip()
        return any(adr_dir.glob(f"{number}-*.md")) or any(
            (adr_dir / "archived").glob(f"{number}-*.md")
        )
    # Otherwise treat as a filename / path fragment.
    name = Path(candidate).name
    return (adr_dir / name).exists() or (adr_dir / "archived" / name).exists()
