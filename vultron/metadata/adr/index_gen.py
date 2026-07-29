"""Generate docs/adr/index.md and check mkdocs ADR nav completeness.

Requirements: specs/meta-specifications.yaml MS-14-003 (ADR-0043).

The ADR index and the mkdocs nav both drifted from the ADR corpus (ADR-0027
was filed under the wrong index section; several ADRs were missing from nav,
breaking ``mkdocs build --strict``). This module makes both mechanical:

- ``generate_index()`` rebuilds the status-organised section list in
  ``docs/adr/index.md`` from each ADR's validated frontmatter + H1 title,
  preserving the hand-written prose preamble.
- ``missing_nav_entries()`` returns ADR files absent from the mkdocs nav. The
  nav uses hand-crafted short labels, so it is *checked for completeness* (no
  ADR left out) rather than regenerated.

CLI (``uv run adr-index``):
    --check   exit 1 if index.md is stale or the nav is missing any ADR
    --write   rewrite docs/adr/index.md in place
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import frontmatter

from vultron.metadata.adr.loader import (
    SKIP_FILES,
    _find_repo_root,
    _iter_adr_paths,
)
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.schema import AdrStatus

# Marker after which the status-organised sections begin. Everything before it
# (title + "What is an ADR?" prose) is hand-written and preserved verbatim.
_SECTIONS_START = "## Accepted ADRs"

_H1_RE = re.compile(r"^#\s+(.*?)\s*$", re.MULTILINE)
_ADR_NUM_RE = re.compile(r"^(\d{4})-")


def _adr_number(path: Path) -> str | None:
    """Return the zero-padded ADR number from a filename, or None."""
    match = _ADR_NUM_RE.match(path.name)
    return match.group(1) if match else None


_TITLE_ADR_PREFIX_RE = re.compile(r"^ADR-\d{4}:?\s*", re.IGNORECASE)


def _adr_title(path: Path) -> str:
    """Return an ADR's H1 title, or its filename stem if none is present.

    Strips a redundant leading ``ADR-NNNN:`` from the H1 (some ADRs embed their
    own number in the heading) so the index label isn't doubled.
    """
    post = frontmatter.load(str(path))
    match = _H1_RE.search(post.content)
    title = match.group(1).strip() if match else path.stem
    return _TITLE_ADR_PREFIX_RE.sub("", title).strip()


def _entry(path: Path, adr_dir: Path) -> str:
    """Render one index bullet as ``- [ADR-NNNN <title>](rel-path)``."""
    rel = str(path.relative_to(adr_dir))
    title = _adr_title(path)
    number = _adr_number(path)
    label = f"ADR-{number} {title}" if number else title
    return f"- [{label}]({rel})"


def generate_index(repo_root: Path | None = None) -> str:
    """Return the full desired contents of ``docs/adr/index.md``.

    Preserves the hand-written preamble (everything before the first status
    section) and regenerates the Accepted / Proposed / Rejected /
    Superseded-Archived sections from ADR frontmatter.
    """
    root = repo_root or _find_repo_root()
    adr_dir = root / "docs" / "adr"
    index_path = adr_dir / "index.md"

    preamble = index_path.read_text(encoding="utf-8")
    cut = preamble.find(_SECTIONS_START)
    if cut != -1:
        preamble = preamble[:cut]
    preamble = preamble.rstrip() + "\n\n"

    accepted: list[str] = []
    proposed: list[str] = []
    rejected: list[str] = []
    retired: list[str] = []

    # Sort numerically by ADR number so the index is stable and scannable.
    for path in sorted(_iter_adr_paths(adr_dir), key=lambda p: p.name):
        post = frontmatter.load(str(path))
        fm = AdrFrontmatter.model_validate(post.metadata)
        entry = _entry(path, adr_dir)

        if fm.status in (AdrStatus.ACCEPTED, AdrStatus.ACCEPTED_PROVISIONAL):
            suffix = (
                " *(provisional)*"
                if fm.status is AdrStatus.ACCEPTED_PROVISIONAL
                else ""
            )
            accepted.append(entry + suffix)
        elif fm.status is AdrStatus.PROPOSED:
            proposed.append(entry)
        elif fm.status is AdrStatus.REJECTED:
            rejected.append(entry)
        else:  # superseded / deprecated
            link = (
                f" — superseded by {fm.superseded_by}"
                if fm.superseded_by
                else ""
            )
            retired.append(entry + link)

    def _section(header: str, items: list[str], preface: str = "") -> str:
        body = "\n".join(items) if items else "- none"
        return f"## {header}\n\n{preface}{body}\n"

    retired_preface = (
        "Retired ADRs (`status: deprecated` or `superseded`) are moved to\n"
        "`docs/adr/archived/` so they stay out of the default `docs/adr/` "
        "context sweep.\nEach is listed here with a forward link to its "
        "replacement.\n\n"
    )

    sections = "\n".join(
        [
            _section("Accepted ADRs", accepted),
            _section("Proposed ADRs", proposed),
            _section("Rejected ADRs", rejected),
            _section(
                "Superseded / Archived ADRs", retired, preface=retired_preface
            ),
        ]
    )
    return preamble + sections


def missing_nav_entries(repo_root: Path | None = None) -> list[str]:
    """Return ADR file paths (relative to docs/) absent from the mkdocs nav.

    The nav uses hand-crafted labels, so completeness is checked rather than
    the nav regenerated: every ADR must be referenced somewhere in mkdocs.yml.
    """
    root = repo_root or _find_repo_root()
    adr_dir = root / "docs" / "adr"
    nav_text = (root / "mkdocs.yml").read_text(encoding="utf-8")

    missing: list[str] = []
    for path in _iter_adr_paths(adr_dir):
        rel_to_docs = str(path.relative_to(root / "docs"))
        # archived ADRs are intentionally excluded from nav.
        if rel_to_docs.startswith("adr/archived/"):
            continue
        if rel_to_docs not in nav_text:
            missing.append(rel_to_docs)
    return missing


def main() -> None:
    """CLI entry point: ``uv run adr-index [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if index.md is stale or nav is missing any ADR.",
    )
    mode.add_argument(
        "--write", action="store_true", help="Rewrite docs/adr/index.md."
    )
    args = parser.parse_args()

    root = _find_repo_root()
    index_path = root / "docs" / "adr" / "index.md"
    desired = generate_index(root)

    if args.write:
        index_path.write_text(desired, encoding="utf-8")
        print(f"Wrote {index_path.relative_to(root)}")
        return

    # --check
    problems: list[str] = []
    current = index_path.read_text(encoding="utf-8")
    if current != desired:
        problems.append(
            "docs/adr/index.md is stale — run 'uv run adr-index --write' "
            "(MS-14-003)."
        )
    for rel in missing_nav_entries(root):
        problems.append(f"mkdocs nav is missing ADR: docs/{rel} (MS-14-003).")

    if problems:
        for p in problems:
            print(f"[ERROR] {p}", file=sys.stderr)
        sys.exit(1)
    print("ADR index and nav are in sync.")


if __name__ == "__main__":
    main()


# Re-export for callers that only need the skip set / discovery.
__all__ = [
    "generate_index",
    "missing_nav_entries",
    "main",
    "SKIP_FILES",
]
