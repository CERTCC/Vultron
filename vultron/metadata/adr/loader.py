"""Loader for the docs/adr/*.md frontmatter registry.

Loader requirements: specs/meta-specifications.yaml MS-14 (ADR-0043).

Mirrors ``vultron.metadata.notes.loader``. Discovers every ADR under
``docs/adr/`` (and ``docs/adr/archived/``), validates its frontmatter against
:class:`~vultron.metadata.adr.schema.AdrFrontmatter`, checks that every
supersession pointer resolves to a real ADR file, and checks that every
supersession link is recorded on both ADRs it joins (MS-14-011).
"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter

from vultron.metadata.adr.schema import (
    SUPERSESSION_FIELDS,
    SUPERSESSION_PAIRS,
    AdrFrontmatter,
)
from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.file_loading import (
    MetadataLoadError,
    display_path,
    load_frontmatter,
    validate,
)

# Files under docs/adr/ that are not decision records.
SKIP_FILES = {"index.md", "README.md"}

_ADR_NUM_RE = re.compile(r"^(\d{4})-")


def adr_number(path: Path) -> str | None:
    """Return the zero-padded ADR number from a filename, or None."""
    match = _ADR_NUM_RE.match(path.name)
    return match.group(1) if match else None


def load_adr_post(path: Path, root: Path | None = None) -> frontmatter.Post:
    """Parse an ADR markdown file, attributing malformed YAML to it.

    A thin name over :func:`~vultron.metadata.file_loading.load_frontmatter`,
    kept because the index generator imports it.

    Raises:
        MetadataLoadError: On malformed YAML frontmatter (MS-17-001).
        FileNotFoundError: If *path* does not exist.
    """
    return load_frontmatter(path, root=root)


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
            names a supersession target that does not resolve to a file, or
            records a supersession link on only one of the two ADRs it joins.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    root = repo_root or _find_repo_root()
    adr_dir = root / "docs" / "adr"
    registry: dict[str, AdrFrontmatter] = {}

    for path in _iter_adr_paths(adr_dir):
        post = load_adr_post(path, root)
        if not post.metadata:
            raise MetadataLoadError(
                "missing YAML frontmatter", path=display_path(path, root)
            )

        key = str(path.relative_to(root))
        fm = validate(AdrFrontmatter, post.metadata, path=path, root=root)
        registry[key] = fm

    _check_supersession_links(adr_dir, root, registry)
    return registry


def _check_supersession_links(
    adr_dir: Path, root: Path, registry: dict[str, AdrFrontmatter]
) -> None:
    """Resolve every supersession pointer and require each link two-way.

    Every entry of the four supersession fields must name a real ADR
    (MS-14-005), and each ``superseded_by`` / ``partially_superseded_by``
    entry must be matched by a ``supersedes`` / ``partially_supersedes`` entry
    on the ADR it names, and the reverse (MS-14-011). Pointers are compared by
    ADR number, so a bare filename, a ``docs/adr/`` path and an ``ADR-NNNN``
    reference to the same ADR are the same link. Every fault in the corpus is
    reported in one error, not just the first.

    Raises:
        ValueError: Listing every dangling pointer and one-sided link.
    """
    resolved, faults = _resolve_pointers(adr_dir, root, registry)
    faults += _one_sided_links(resolved)
    if faults:
        raise ValueError(
            "ADR supersession links are invalid:\n  " + "\n  ".join(faults)
        )


# Each supersession field paired with the field that must answer it on the ADR
# it names: a retired-side pointer with its successor-side twin, and back.
_TWIN_FIELD: dict[str, str] = {
    **dict(SUPERSESSION_PAIRS),
    **{back: fwd for fwd, back in SUPERSESSION_PAIRS},
}

# ADR key → supersession field → the ADR numbers it points at.
_Resolved = dict[str, dict[str, set[str]]]


def _resolve_pointers(
    adr_dir: Path, root: Path, registry: dict[str, AdrFrontmatter]
) -> tuple[_Resolved, list[str]]:
    """Normalise every supersession pointer to an ADR number.

    Returns the resolved pointers and one fault per pointer that names no
    numbered ADR file.
    """
    resolved: _Resolved = {}
    faults: list[str] = []
    for key, fm in registry.items():
        resolved[key] = {}
        for field in SUPERSESSION_FIELDS:
            numbers: set[str] = set()
            for target in getattr(fm, field):
                target_number = _superseded_target_number(adr_dir, target)
                if target_number is None:
                    faults.append(
                        f"{key}: {field} '{target}' does not resolve to a "
                        f"numbered ADR file in {display_path(adr_dir, root)} "
                        f"or {display_path(adr_dir / 'archived', root)}"
                    )
                else:
                    numbers.add(target_number)
            resolved[key][field] = numbers
    return resolved, faults


def _one_sided_links(resolved: _Resolved) -> list[str]:
    """Return one fault per supersession link recorded on only one ADR."""
    key_by_number = {
        number: key
        for key in resolved
        if (number := adr_number(Path(key))) is not None
    }
    faults: list[str] = []
    for key, fields in resolved.items():
        number = adr_number(Path(key))
        for field, targets in fields.items():
            twin = _TWIN_FIELD[field]
            for target_number in sorted(targets):
                # Resolution only succeeds on a numbered file the discovery
                # glob also loads, so the lookup cannot miss.
                target_key = key_by_number[target_number]
                if number not in resolved[target_key][twin]:
                    faults.append(
                        f"{key}: {field} names {target_key}, but "
                        f"{target_key} has no {twin} entry naming {key} "
                        "— record the link on both ADRs (MS-14-011)"
                    )
    return faults


def _superseded_target_number(adr_dir: Path, target: str) -> str | None:
    """Return the ADR number a supersession pointer names, or None.

    Accepts a bare filename (``0041-....md``), a relative path
    (``docs/adr/0041-....md``), or an ``ADR-NNNN`` reference (resolved by the
    ``NNNN-*.md`` glob). Returns ``None`` when the pointer names no ADR file in
    ``adr_dir`` or its ``archived/`` subdirectory, or a file without a number.
    """
    candidate = target.strip().strip("[]")
    # ADR-NNNN form → match by number.
    if candidate.upper().startswith("ADR-"):
        number = candidate.split("-", 1)[1].strip()
        found = any(adr_dir.glob(f"{number}-*.md")) or any(
            (adr_dir / "archived").glob(f"{number}-*.md")
        )
        return number if found and _ADR_NUM_RE.match(f"{number}-") else None
    # Otherwise treat as a filename / path fragment.
    name = Path(candidate).name
    if not (
        (adr_dir / name).exists() or (adr_dir / "archived" / name).exists()
    ):
        return None
    return adr_number(Path(name))
