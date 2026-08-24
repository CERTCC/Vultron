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

import yaml

from vultron.metadata.adr.loader import (
    SKIP_FILES,
    _find_repo_root,
    _iter_adr_paths,
    load_adr_post,
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
    post = load_adr_post(path)
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
        post = load_adr_post(path)
        fm = AdrFrontmatter.model_validate(post.metadata)
        entry = _entry(path, adr_dir)

        if fm.status in (AdrStatus.ACCEPTED, AdrStatus.ACCEPTED_PROVISIONAL):
            suffix = (
                " *(provisional)*"
                if fm.status is AdrStatus.ACCEPTED_PROVISIONAL
                else ""
            )
            # A live ADR with one decision replaced: say so here, because the
            # index is where a reader decides which ADR to open, and an
            # unannotated entry reads as wholly current.
            if fm.partially_superseded_by:
                suffix += (
                    " — partially superseded by "
                    f"{fm.partially_superseded_by}"
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


class _NavTagTolerantLoader(yaml.SafeLoader):
    """SafeLoader that tolerates mkdocs' custom YAML tags.

    ``mkdocs.yml`` carries ``!ENV`` and ``!!python/name:`` tags that a plain
    ``yaml.safe_load`` refuses to construct. We only need the ``nav:`` file
    paths, so we register permissive constructors that discard the tag and
    keep the underlying scalar/sequence rather than executing anything.
    """


_NavTagTolerantLoader.add_multi_constructor("!", lambda _l, _s, _n: None)
_NavTagTolerantLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", lambda _l, _s, _n: None
)


def _iter_nav_paths(nav: object) -> "list[str]":
    """Yield every string file path referenced anywhere in a mkdocs nav tree."""
    found: list[str] = []
    if isinstance(nav, str):
        found.append(nav)
    elif isinstance(nav, list):
        for item in nav:
            found.extend(_iter_nav_paths(item))
    elif isinstance(nav, dict):
        for value in nav.values():
            found.extend(_iter_nav_paths(value))
    return found


def missing_nav_entries(repo_root: Path | None = None) -> list[str]:
    """Return ADR file paths (relative to docs/) absent from the mkdocs nav.

    The nav uses hand-crafted labels, so completeness is checked rather than
    the nav regenerated: every ADR must appear as a file entry in the
    ``nav:`` tree. The nav tree is parsed as YAML and walked structurally — a
    raw substring match would false-pass on a path that appears only in a
    comment or unrelated key, letting a genuinely un-navved ADR slip through
    and then break ``mkdocs build --strict`` (MS-14-006).
    """
    root = repo_root or _find_repo_root()
    adr_dir = root / "docs" / "adr"

    with (root / "mkdocs.yml").open(encoding="utf-8") as fh:
        config = yaml.load(fh, Loader=_NavTagTolerantLoader)  # noqa: S506
    nav_paths = set(_iter_nav_paths((config or {}).get("nav")))

    missing: list[str] = []
    for path in _iter_adr_paths(adr_dir):
        rel_to_docs = str(path.relative_to(root / "docs"))
        # archived ADRs are intentionally excluded from nav.
        if rel_to_docs.startswith("adr/archived/"):
            continue
        if rel_to_docs not in nav_paths:
            missing.append(rel_to_docs)
    return missing


def duplicate_numbers(repo_root: Path | None = None) -> dict[str, list[str]]:
    """Return ADR numbers claimed by more than one file, worst offender first.

    An ADR number is allocated as ``max(existing) + 1`` at authoring time but is
    not *reserved* until the PR merges, so a long-lived branch holds a claim on a
    sequence ``main`` keeps allocating from. Any ADR that lands first invalidates
    it — and nothing detected that: two files could share a number indefinitely,
    ``--check`` compared only the index against the files on disk, and the index
    rendered both entries without complaint.

    One branch hit this **four times** while being kept up to date (ISSUE-2238's
    ADR went 0066 → 0069 → 0070 → 0071 → 0072), each renumber moving ~230
    citations across ~128 files, twice *after* the PR had been marked ready for
    review. Catching it at the first commit costs nothing; catching it at merge
    costs a full renumber pass and risks separating the two ADRs' citations wrongly.

    Returns:
        ``{number: [filename, …]}`` for numbers with more than one claimant.
    """
    adr_dir = (repo_root or _find_repo_root()) / "docs" / "adr"
    claims: dict[str, list[str]] = {}
    for path in sorted(adr_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        number = _adr_number(path)
        if number is None:
            continue
        claims.setdefault(number, []).append(path.name)
    return {n: f for n, f in claims.items() if len(f) > 1}


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
        dupes = duplicate_numbers(root)
        if dupes:
            for number, files in sorted(dupes.items()):
                print(
                    f"[ERROR] ADR-{number} is claimed by: {', '.join(files)}",
                    file=sys.stderr,
                )
            print(
                "[ERROR] Refusing to write an index that renders a duplicate"
                " number. Renumber the unlanded ADR first.",
                file=sys.stderr,
            )
            sys.exit(1)
        index_path.write_text(desired, encoding="utf-8")
        print(f"Wrote {index_path.relative_to(root)}")
        return

    # --check
    problems: list[str] = []
    for number, files in sorted(duplicate_numbers(root).items()):
        problems.append(
            f"ADR-{number} is claimed by {len(files)} files: "
            f"{', '.join(files)}. An unlanded ADR number is not reserved — "
            "renumber the one that has not merged yet, and separate its "
            "citations by topic rather than by find-and-replace."
        )
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
    "duplicate_numbers",
    "generate_index",
    "missing_nav_entries",
    "main",
    "SKIP_FILES",
]
