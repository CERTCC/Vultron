"""Generate docs/adr/index.md and check that ADRs stay out of the mkdocs nav.

Requirements: specs/meta-specifications.yaml MS-14-003, MS-14-006 (ADR-0043);
specs/diataxis-requirements.yaml DF-11-003.

The ADR index drifted from the ADR corpus (ADR-0027 was filed under the wrong
index section). This module makes it mechanical:

- ``generate_index()`` rebuilds the status-organised section list in
  ``docs/adr/index.md`` from each ADR's validated frontmatter + H1 title,
  preserving the hand-written prose preamble. The index links every ADR, so it
  is the routing page readers reach them through.
- ``nav_placement_faults()`` reports each ADR that is listed in the mkdocs nav
  or not matched by ``not_in_nav``. ADRs are project working record, which
  stays out of the reader-facing nav (DF-11-003); an ADR in neither place
  fails ``mkdocs build --strict`` on an omitted-file warning.

CLI (``uv run adr-index``):
    --check   exit 1 if index.md is stale or any ADR is placed in the nav
    --write   rewrite docs/adr/index.md in place
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from vultron.metadata.adr.loader import (
    SKIP_FILES,
    _find_repo_root,
    _iter_adr_paths,
    load_adr_post,
)
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.base import (
    nav_exclusion_fault,
    nav_paths,
    not_in_nav_spec,
)
from vultron.metadata.file_loading import validate
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
        post = load_adr_post(path, root)
        fm = validate(AdrFrontmatter, post.metadata, path=path, root=root)
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
        "[`docs/adr/archived/`](archived/README.md) so they stay out of the "
        "default `docs/adr/` context sweep.\nEach is listed here with a "
        "forward link to its replacement.\n\n"
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


def nav_placement_faults(repo_root: Path | None = None) -> list[str]:
    """Return one message per ADR placed wrongly with respect to the nav.

    Every ADR, archived ones included, must be absent from the ``nav:`` tree
    and matched by ``not_in_nav`` (MS-14-006, DF-11-003); ``docs/adr/index.md``
    routes to it instead. The nav tree is parsed as YAML and walked
    structurally, so a path that appears only in a comment or an unrelated key
    is not mistaken for a nav entry.
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    navved = nav_paths(root)
    not_in_nav = not_in_nav_spec(root)

    faults: list[str] = []
    for path in _iter_adr_paths(docs_dir / "adr"):
        rel_to_docs = path.relative_to(docs_dir).as_posix()
        fault = nav_exclusion_fault(rel_to_docs, navved, not_in_nav)
        if fault:
            faults.append(
                f"docs/{rel_to_docs} {fault}; an ADR is reached through "
                f"docs/adr/index.md, not the nav (MS-14-006)."
            )
    return faults


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
        help="Exit 1 if index.md is stale or any ADR is placed in the nav.",
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
    problems.extend(nav_placement_faults(root))

    if problems:
        for p in problems:
            print(f"[ERROR] {p}", file=sys.stderr)
        sys.exit(1)
    print("ADR index is in sync, and no ADR is in the nav.")


if __name__ == "__main__":
    main()


# Re-export for callers that only need the skip set / discovery.
__all__ = [
    "duplicate_numbers",
    "generate_index",
    "nav_placement_faults",
    "main",
    "SKIP_FILES",
]
