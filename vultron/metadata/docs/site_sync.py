"""Generate and check the committed docs-site artifacts.

Requirements: DF-11-005, DF-11-008, DF-11-011, DF-11-014, DF-11-021 and
DF-11-023 in specs/diataxis-requirements.yaml.

Six kinds of artifact are generated and committed:

- each section **landing page** under ``docs/`` whose index declares
  ``contents: generated`` — only the contents listing between the markers, so
  the hand-written framing survives
  (:mod:`~vultron.metadata.docs.landing_pages`);
- each **start page** under ``docs/start/`` — only the reading-path listing
  between its markers, rendered from the page's ``thread:`` frontmatter
  (:mod:`~vultron.metadata.docs.threads`, DF-11-014); whether each thread's
  members are reader-facing pages is the separate ``docs-threads`` check;
- each **reading-path box** under ``docs/start/_paths/<thread>/`` — whole
  file, one per thread and member, rendered from the same ``thread:``
  frontmatter (DF-11-023); a fragment for a page no longer on its thread is
  stale, and ``--write`` deletes it;
- the **lookup page** ``docs/lookup.md`` — only the listing between its
  markers, of every ``page_type: reference`` page by top-level nav section
  (:mod:`~vultron.metadata.docs.lookup_page`, DF-11-021);
- ``docs/includes/stakeholder_types.md`` — whole file, from the schema
  (:mod:`~vultron.metadata.docs.stakeholder_fragment`);
- ``notes/site-coverage-matrix.md`` — whole file, from page frontmatter
  (:mod:`~vultron.metadata.docs.coverage_matrix`).

Two things are checked but never written: a section index that declares
``contents: routing`` must link every member of its section (DF-11-005's
routing-page exemption), and the home page and every start page must link the
lookup page (DF-11-021). A missing link is a fault the author fixes by hand
in the page's framing, so both modes report it and neither "repairs" it.

``--check`` is wired into pre-commit as ``docs-site-sync`` and runs in
``docs-build-check.yml`` on a pull request that changes ``docs/``
(DOCBW-03-013); ``test_committed_site_artifacts_are_in_sync`` enforces it on
one that changes ``vultron/`` and is the backstop for a deletion, which
pre-commit's staged-file list cannot match. Both
modes compare through :func:`_out_of_date`, so they cannot disagree about what
"stale" means.

CLI (``uv run docs-site``):
    --check   exit 1 if any committed artifact is stale
    --write   rewrite every committed artifact in place
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.coverage_matrix import (
    MATRIX_PATH,
    measure_coverage,
    render_matrix,
)
from vultron.metadata.docs.landing_pages import (
    WRITE_COMMAND,
    discover_section_indexes,
    routing_faults,
    splice_listing,
)
from vultron.metadata.docs.lookup_page import (
    HOME_PATH,
    LOOKUP_PATH,
    LookupSection,
    lookup_link_faults,
    lookup_sections,
    splice_lookup,
)
from vultron.metadata.docs.stakeholder_fragment import (
    FRAGMENT_PATH,
    render_fragment,
)
from vultron.metadata.docs.threads import (
    BOX_DIR,
    load_threads,
    page_titles,
    render_boxes,
    splice_thread_listing,
)
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors


def _read(target: Path) -> str:
    return target.read_text(encoding="utf-8") if target.is_file() else ""


def desired_contents(root: Path) -> dict[str, str]:
    """Return ``{repo-relative path: desired full contents}`` for every artifact.

    Raises:
        MetadataLoadError: If a listed page or a landing page is missing,
            empty, or unreadable (a landing page's hand-written prose cannot
            be regenerated), a page's declarations do not validate, a
            group-opening index declares no ``contents:``, or a target set is
            empty (DF-09-009).
        MetadataLoadErrors: If a routing index fails to link a member of its
            section, or the home page or a start page fails to link the
            lookup page, every missing link listed (DF-11-005, DF-11-021); if
            a start page's thread is missing or does not validate
            (DF-11-013); or if the lookup page cannot be built: a
            reference page cannot be placed or its entry has no description
            (DF-11-021), or any other fault ``lookup_sections`` raises,
            reported with the missing links (EH-07-001).
        ValueError: If a landing, start or lookup page's markers are missing
            or malformed.
    """
    contents = {
        FRAGMENT_PATH: render_fragment(),
        MATRIX_PATH: render_matrix(measure_coverage(root)),
    }
    indexes = discover_section_indexes(root)
    threads = load_threads(root)
    faults = [
        fault
        for page in indexes.routing
        for fault in routing_faults(root, page)
    ]
    # A host that is itself a routing index required to link the lookup page
    # (the home page, when the lookup page sits in its nav group) is already
    # checked above; checking it again would report one missing link twice.
    routed = {
        page.path for page in indexes.routing if LOOKUP_PATH in page.required
    }
    faults.extend(
        lookup_link_faults(
            root,
            [
                host
                for host in (HOME_PATH, *(t.path for t in threads))
                if host not in routed
            ],
        )
    )
    sections: tuple[LookupSection, ...] = ()
    try:
        sections = lookup_sections(root)
    except MetadataLoadErrors as exc:
        # Reported with the missing links, so one run names every
        # hand-fixable fault (EH-07-001).
        faults.extend(exc.failures)
    except MetadataLoadError as exc:
        faults.append(exc)
    if faults:
        raise MetadataLoadErrors(
            faults,
            summary=(
                f"{len(faults)} finding(s) to fix by hand; nothing is "
                "generated for a missing link or an unplaceable page "
                "(DF-11-005, DF-11-021):"
            ),
        )
    for page in indexes.generated:
        # A missing or empty landing page was already refused by
        # discover_section_indexes (landing_pages._page_facts), so the
        # source read here is non-empty.
        path = f"docs/{page.path}"
        contents[path] = splice_listing(_read(root / path), page)
    lookup = f"docs/{LOOKUP_PATH}"
    contents[lookup] = splice_lookup(_read(root / lookup), sections)
    titles = page_titles(root, threads)
    for thread in threads:
        path = f"docs/{thread.path}"
        contents[path] = splice_thread_listing(
            _read(root / path), thread, titles
        )
    for fragment, box in render_boxes(threads, titles).items():
        contents[f"docs/{fragment}"] = box
    return contents


def _committed_boxes(root: Path) -> set[str]:
    """Repo-relative paths of every committed box fragment (DF-11-023)."""
    base = root / "docs" / BOX_DIR
    if not base.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in base.rglob("*.md")}


def _out_of_date(root: Path) -> list[tuple[Path, str, str | None]]:
    """Return ``(target, path, desired)`` for each artifact whose contents differ.

    ``desired`` is ``None`` for a committed box fragment that no thread
    implies any more: it is stale, and writing deletes it (DF-11-023).
    """
    stale: list[tuple[Path, str, str | None]] = []
    desired_by_path = desired_contents(root)
    for path, desired in desired_by_path.items():
        target = root / path
        if _read(target) != desired:
            stale.append((target, path, desired))
    for path in sorted(_committed_boxes(root) - desired_by_path.keys()):
        stale.append((root / path, path, None))
    return stale


def stale_artifacts(root: Path | None = None) -> list[str]:
    """Return the repo-relative paths whose committed contents are stale."""
    return [path for _t, path, _d in _out_of_date(root or repo_root())]


def write_artifacts(root: Path | None = None) -> list[str]:
    """Rewrite every stale artifact in place; return the paths written.

    A box fragment no thread implies is deleted, and its path is returned
    too. One pass is enough: writing a page rewrites only the text between its
    markers, never its frontmatter, so it never changes what the coverage
    matrix counts.
    """
    written: list[str] = []
    for target, path, desired in _out_of_date(root or repo_root()):
        if desired is None:
            target.unlink()
            written.append(path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run docs-site [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any committed docs-site artifact is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite every committed docs-site artifact.",
    )
    args = parser.parse_args(argv)
    root = repo_root()
    try:
        if args.write:
            written = write_artifacts(root)
            for path in written:
                verb = "Wrote" if (root / path).is_file() else "Deleted"
                print(f"{verb} {path}")
            if not written:
                print("Docs-site artifacts already in sync.")
            return
        stale = stale_artifacts(root)
    except (MetadataLoadError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    if stale:
        for path in stale:
            print(
                f"[ERROR] {path} is stale — run '{WRITE_COMMAND}' "
                "(DF-11-005, DF-11-014, DF-11-021, DF-11-023).",
                file=sys.stderr,
            )
        sys.exit(1)
    print("Docs-site artifacts are in sync.")


if __name__ == "__main__":
    main()
