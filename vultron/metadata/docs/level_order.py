"""Check that no ``docs/`` page depends on a page above its own level.

Requirements: specs/diataxis-requirements.yaml DF-11-002 (the rule), DF-11-003
and DF-11-012 (working record has no level), DF-11-010 (fragments take their
hosts' declarations), DF-09-009 (an empty target set fails); the cross-page
concept edge is SG-11 in ``.agents/skills/shared/docs-style-guide.md``. Design
rationale: ``notes/site-information-architecture.md`` (ADR-0102).

A page *depends on* another when it uses a concept that page introduces
without introducing, defining, or linking out for it (DF-11-002). The glossary
is the concept registry (SG-11), so a concept is a glossary term, and the page
that introduces it says so in its own frontmatter::

    level: 400
    introduces: [Case Ledger Entry, Participant Case Replica]

Each term has at most one introducer. For every leveled page, and every
include fragment at its lowest host's level, the check finds the first prose
use of each term whose introducer sits at a higher level — code, link targets,
comments and directives are not prose (:mod:`.concept_scan`). The use is
compliant when the page links to the introducer on that line or earlier, or
when the use is itself the text of a link to the glossary: linking out to a
canonical introduction satisfies the rule (SG-11). Otherwise it is a finding at
the use's
``path:line:col``. The comparison is site-wide: one ladder, never one per
``stakeholder_type``. Pages with no ``level`` — the working record, and pages
not yet declared — are skipped rather than read as level 0.

Violations that predate this check are listed with a reason in
:data:`BASELINE_PATH`. The list may only shrink: an entry that no longer
matches a violation fails until ``--prune-baseline`` removes it, and a test
pins the entry count to a ceiling that may only be lowered.

Usage::

    uv run docs-level-order                   # check (pre-commit, CI)
    uv run docs-level-order --prune-baseline  # drop entries now satisfied
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.concept_registry import (
    INTRODUCES_KEY,
    REGISTRY,
    glossary_terms,
    introductions,
)
from vultron.metadata.docs.concept_scan import Position, first_use, read_page
from vultron.metadata.docs.level_baseline import (
    BASELINE_PATH,
    read_baseline,
    read_baseline_entries,
    write_baseline,
)
from vultron.metadata.docs.page_frontmatter import DocsTree, classify_docs_tree
from vultron.metadata.docs.page_schema import LEVELS, is_working_record
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    load_frontmatter,
)


@dataclass(frozen=True, slots=True)
class Violation:
    """A first use of a concept introduced above the using page's level.

    Attributes:
        page: ``docs/``-relative path of the page or fragment using the term.
        term: The glossary term.
        used: The text that matched, as written.
        position: Where the use is.
        level: The using page's level (a fragment's lowest host level).
        introducer: ``docs/``-relative path of the introducing page.
        introducer_level: The introducing page's level.
        hosts: For a fragment, the leveled pages including it.
    """

    page: str
    term: str
    used: str
    position: Position
    level: int
    introducer: str
    introducer_level: int
    hosts: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return (self.page, self.term)

    def error(self) -> MetadataLoadError:
        where = (
            f"this fragment's lowest host ({', '.join(self.hosts)}) is at "
            f"{self.level}"
            if self.hosts
            else f"this page is at {self.level}"
        )
        return MetadataLoadError(
            f'uses "{self.used}" ({self.term}), which docs/{self.introducer} '
            f"introduces at level {self.introducer_level}, but {where}; link "
            f"this first use to that page (SG-11) or move the page "
            f"(DF-11-002)",
            path=f"docs/{self.page}",
            line=self.position.line,
            column=self.position.column,
        )


@dataclass
class Analysis:
    """What the tree declares and where it breaks the rule."""

    terms: dict[str, tuple[str, ...]]
    levels: dict[str, int] = field(default_factory=dict)
    unleveled: int = 0
    introducers: dict[str, str] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    leveled_pages: int
    unleveled_pages: int
    introductions: int
    baselined: list[tuple[str, str]]


def _declared_level(metadata: dict[str, object]) -> int | None:
    """The page's level, or ``None`` when it declares none on the ladder.

    An off-ladder value is ``docs-frontmatter``'s finding, not this check's.
    """
    level = metadata.get("level")
    return level if type(level) is int and level in LEVELS else None


def _collect(
    root: Path, tree: DocsTree, collector: FailureCollector
) -> Analysis:
    """Read every page's level and introductions."""
    docs_dir = root / "docs"
    terms = glossary_terms(root)
    analysis = Analysis(terms=terms)
    for rel in (*tree.pages, *sorted(tree.fragments)):
        with collector.attempt():
            path = docs_dir / rel
            metadata = dict(load_frontmatter(path, root=root).metadata)
            fragment = rel in tree.fragments
            level = None if fragment else _declared_level(metadata)
            if fragment:
                why_not = "an include fragment takes its hosts' declarations"
                why_not += " and introduces nothing of its own (DF-11-010)"
            elif is_working_record(rel):
                analysis.unleveled += 1
                why_not = (
                    "a working-record page has no level (DF-11-012), so "
                    "nothing can be ordered against its concepts"
                )
            elif level is None:
                analysis.unleveled += 1
                why_not = "declare this page's level before its concepts"
            else:
                analysis.levels[rel] = level
                why_not = None
            collector.failures += introductions(
                rel,
                metadata,
                path=path,
                terms=terms,
                introducers=analysis.introducers,
                can_introduce=why_not,
            )
    return analysis


def _scan(root: Path, tree: DocsTree, analysis: Analysis) -> None:
    """Append every unlinked first use of a higher-level concept."""
    docs_dir = root / "docs"
    subjects: list[tuple[str, int, tuple[str, ...]]] = [
        (rel, level, ())
        for rel, level in analysis.levels.items()
        if rel != REGISTRY
    ]
    for rel, hosts in sorted(tree.fragments.items()):
        leveled = sorted(
            (analysis.levels[h], h) for h in hosts if h in analysis.levels
        )
        if leveled:
            lowest = leveled[0][0]
            subjects.append(
                (rel, lowest, tuple(h for lvl, h in leveled if lvl == lowest))
            )

    for rel, level, hosts in subjects:
        scanned = read_page(docs_dir, rel)
        for term, introducer in sorted(analysis.introducers.items()):
            introducer_level = analysis.levels[introducer]
            if introducer == rel or introducer_level <= level:
                continue
            use = first_use(scanned, analysis.terms[term])
            if use is None:
                continue
            # Linked out earlier, or at the use to either canonical
            # introduction SG-11 names: the introducing page or the glossary.
            link = scanned.first_link(introducer)
            if link is not None and link.line <= use.position.line:
                continue
            if scanned.link_around(use.offset) in (introducer, REGISTRY):
                continue
            analysis.violations.append(
                Violation(
                    page=rel,
                    term=term,
                    used=use.text,
                    position=use.position,
                    level=level,
                    introducer=introducer,
                    introducer_level=introducer_level,
                    hosts=hosts,
                )
            )


def _summary(collector: FailureCollector) -> str:
    return (
        f"{len(collector.failures)} docs level-order finding(s) (DF-11-002):"
    )


def analyse(
    repo_root: Path | None = None,
) -> tuple[Analysis, FailureCollector]:
    """Read the tree and find every violation, ignoring the baseline.

    Returns:
        The analysis, and a collector holding each declaration fault (an
        unreadable page, a malformed or misplaced ``introduces``).

    Raises:
        MetadataLoadError: If the glossary is missing or empty, or the tree
            resolves no leveled page or no introduced concept (DF-09-009).
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    tree = (
        classify_docs_tree(root) if docs_dir.is_dir() else DocsTree((), {}, {})
    )
    collector = FailureCollector()
    analysis = _collect(root, tree, collector)
    if not (analysis.levels and analysis.introducers):
        # A malformed declaration can be why the set is empty; name it first.
        collector.raise_if_any(summary=_summary(collector))
    if not analysis.levels:
        raise MetadataLoadError(
            "resolved no leveled page to check; an empty target set is a "
            "failure, not a pass (DF-09-009)",
            path="docs",
        )
    if not analysis.introducers:
        raise MetadataLoadError(
            f"no page declares {INTRODUCES_KEY}:, so there is no concept to "
            f"order pages by; an empty target set is a failure, not a pass "
            f"(DF-09-009)",
            path="docs",
        )
    _scan(root, tree, analysis)
    return analysis, collector


def check_level_order(
    repo_root: Path | None = None,
    baseline: dict[tuple[str, str], str] | None = None,
) -> CheckResult:
    """Fail on every upward dependency that the baseline does not list.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        baseline: Violations tolerated, keyed by ``(page, term)``. Defaults
            to the contents of :data:`BASELINE_PATH`.

    Raises:
        MetadataLoadError: If the target set is empty (DF-09-009).
        MetadataLoadErrors: Carrying every finding as ``path:line:col``: each
            unbaselined violation, each declaration fault, and each baseline
            entry that no longer matches a violation.
    """
    analysis, collector = analyse(repo_root)
    entries = read_baseline_entries(BASELINE_PATH) if baseline is None else {}
    allowed = (
        {key: entry.reason for key, entry in entries.items()}
        if baseline is None
        else baseline
    )
    found = {v.key for v in analysis.violations}
    baselined = []
    for violation in analysis.violations:
        if violation.key in allowed:
            baselined.append(violation.key)
        else:
            collector.failures.append(violation.error())
    for page, term in sorted(set(allowed) - found):
        collector.failures.append(
            MetadataLoadError(
                f"baselines docs/{page} | {term}, which is no longer a "
                f"violation; run `uv run docs-level-order --prune-baseline` "
                f"and drop the key from _BASELINED in "
                f"test/metadata/docs/test_level_order.py",
                path=BASELINE_PATH.name,
                line=entries[(page, term)].line if entries else None,
            )
        )
    collector.raise_if_any(summary=_summary(collector))
    return CheckResult(
        leveled_pages=len(analysis.levels),
        unleveled_pages=analysis.unleveled,
        introductions=len(analysis.introducers),
        baselined=sorted(baselined),
    )


def prune_baseline(
    repo_root: Path | None = None, baseline_path: Path | None = None
) -> int:
    """Drop baseline entries that no longer match a violation.

    Never adds an entry, so it cannot be used to grow the baseline. An entry
    for a page the check could not read is kept: its violation is unknown,
    not fixed.

    Returns:
        How many entries were removed.
    """
    analysis, collector = analyse(repo_root)
    baseline_path = baseline_path or BASELINE_PATH
    current = read_baseline(baseline_path)
    found = {v.key for v in analysis.violations}
    unread = {f.path for f in collector.failures}
    keep = {
        key: reason
        for key, reason in current.items()
        if key in found or f"docs/{key[0]}" in unread
    }
    write_baseline(keep, baseline_path)
    return len(current) - len(keep)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-level-order`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that no docs/ page depends on a page above its own level "
            "(DF-11-002)."
        )
    )
    parser.add_argument(
        "--prune-baseline",
        action="store_true",
        help="Remove baseline entries that are no longer violations.",
    )
    args = parser.parse_args(argv)

    try:
        if args.prune_baseline:
            removed = prune_baseline()
            print(f"Removed {removed} entry(ies) from {BASELINE_PATH.name}.")
            return
        result = check_level_order()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.leveled_pages} leveled page(s) against "
        f"{result.introductions} introduced concept(s); "
        f"{result.unleveled_pages} unleveled page(s) skipped; "
        f"{len(result.baselined)} baselined violation(s) remain."
    )


if __name__ == "__main__":
    main()
