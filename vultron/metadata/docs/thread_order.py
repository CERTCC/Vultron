"""Check that no page on a thread depends on a page later on that thread.

Requirements: specs/diataxis-requirements.yaml DF-11-024 (the rule), DF-11-013
(a thread is a partial order of stages), DF-11-002 (the level rule whose
scan this reuses), DF-11-010 (a fragment renders on its hosts), DF-09-009
(an empty target set fails). Design rationale:
``notes/site-information-architecture.md`` § "Threads: staged data, rendered
at both ends" (ADR-0150).

A thread is a partial order (DF-11-013): every member of a stage comes before
every member of the stages after it, and a chain's members come in their
order, while a set's members are unordered among themselves. A reader
following the thread reaches the earlier page first, so that page must not
use a concept a later member introduces (``introduces:``, DF-11-002) unless
it links out for it. This makes a thread's order falsifiable in the same way
the level rule makes navigation order falsifiable.

The term-dependency scan is the one ``docs-level-order`` runs
(:class:`~vultron.metadata.docs.level_order.PageScanner`): a member's first
prose use of the term passes when the page links to the introducer before or
at the use, or when the use is itself the text of a link to the introducer or
the glossary (SG-11). An include fragment a member renders is checked as its
own page, as the level check does. Otherwise it is a finding at the use's
``path:line:col``. Start pages are not members, so they are not checked: their
listing links every member before describing it.

Violations that predate this check are listed with a reason in
:data:`BASELINE_PATH`, keyed by thread, page and term, since a page can come
before a term's introducer on one thread and after it on another. The list may
only shrink: an entry that no longer matches a violation fails until
``--prune-baseline`` removes it, and a test pins the exact set of baselined
keys, so an entry can be removed but never added or swapped for another.

Usage::

    uv run docs-thread-order                   # check (pre-commit, CI)
    uv run docs-thread-order --prune-baseline  # drop entries now satisfied
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.baseline_file import KeyedBaseline, prune_entries
from vultron.metadata.docs.concept_registry import REGISTRY
from vultron.metadata.docs.concept_scan import Position
from vultron.metadata.docs.level_order import (
    PageScanner,
    collect_declarations,
    fragment_hosts,
)
from vultron.metadata.docs.page_frontmatter import (
    DocsTree,
    classify_docs_tree,
)
from vultron.metadata.docs.page_schema import StageKind, ThreadMember
from vultron.metadata.docs.threads import StartThread, check_threads
from vultron.metadata.file_loading import FailureCollector, MetadataLoadError

#: Thread-order dependencies that predate the check, one per line as
#: ``thread | page | term | reason``. Kept outside ``docs/`` so it is never
#: published.
BASELINE_PATH = Path(__file__).with_name("thread_order_baseline.txt")

_BASELINE_HEADER = """\
# Thread-order dependencies in docs/ that predate the DF-11-024 check.
#
# Maintained by vultron.metadata.docs.thread_order. One entry per line:
#   <start page> | <docs/-relative page> | <glossary term> | <reason>
# This list may only shrink. Fix an entry by linking the term's first use to
# the page that introduces it (SG-11) or by reordering the thread, then run
# `uv run docs-thread-order --prune-baseline`. Do not add entries by hand;
# test_thread_order.py pins the exact set of entries.
"""

#: ``(start page, page, term)``: a violation, and its baseline key.
ThreadOrderKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class Violation:
    """A first use of a concept that a later member of a thread introduces.

    Attributes:
        thread: ``docs/``-relative path of the thread's start page.
        page: ``docs/``-relative path of the page or fragment using the term.
        term: The glossary term.
        used: The text that matched, as written.
        position: Where the use is.
        member: The earlier member that renders the use: *page* itself, or
            for a fragment, the member that includes it.
        introducer: The later member introducing the term.
    """

    thread: str
    page: str
    term: str
    used: str
    position: Position
    member: str
    introducer: str

    @property
    def key(self) -> ThreadOrderKey:
        return (self.thread, self.page, self.term)

    def error(self) -> MetadataLoadError:
        where = (
            "this page comes before it"
            if self.member == self.page
            else f"this fragment renders on docs/{self.member}, which comes "
            f"before it"
        )
        return MetadataLoadError(
            f'uses "{self.used}" ({self.term}), which docs/{self.introducer} '
            f"introduces later on the thread docs/{self.thread} opens, but "
            f"{where}; link this first use to that page or the glossary "
            f"(SG-11) or reorder the thread (DF-11-024)",
            path=f"docs/{self.page}",
            line=self.position.line,
            column=self.position.column,
        )


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    threads: int
    introductions: int
    baselined: list[ThreadOrderKey]


def later_members(
    thread: StartThread,
) -> Iterator[tuple[ThreadMember, tuple[ThreadMember, ...]]]:
    """Yield each member with every member that comes after it (DF-11-013).

    Every later stage's members come after a member, and so do the members
    after it in its own stage when that stage is a chain; a set's members are
    unordered among themselves.
    """
    stages = thread.stages
    for index, stage in enumerate(stages):
        after_stage = tuple(m for s in stages[index + 1 :] for m in s.members)
        for offset, member in enumerate(stage.members):
            in_chain = (
                tuple(stage.members[offset + 1 :])
                if stage.kind is StageKind.CHAIN
                else ()
            )
            yield member, in_chain + after_stage


def _summary(collector: FailureCollector) -> str:
    return (
        f"{len(collector.failures)} docs thread-order finding(s) (DF-11-024):"
    )


def _rendered_fragments(tree: DocsTree) -> dict[str, list[str]]:
    """Map each page to the include fragments it renders (DF-11-010)."""
    rendered: dict[str, list[str]] = {}
    for fragment in sorted(tree.fragments):
        seen = frozenset({fragment})
        for host in fragment_hosts(fragment, tree, tree.pages, seen):
            rendered.setdefault(host, []).append(fragment)
    return rendered


def _candidates(
    thread: StartThread,
    introduced: Mapping[str, list[str]],
    rendered: Mapping[str, list[str]],
) -> Iterator[tuple[str, str, str, str]]:
    """Yield ``(member, subject, introducer, term)`` for *thread* to scan.

    *subject* is the member's page or a fragment it renders, and *term* one
    that *introducer*, a member after it, introduces.
    """
    for member, later in later_members(thread):
        # The glossary defines every term it lists, so it cannot depend on a
        # later page for one; level_order exempts it the same way.
        own = () if member.path == REGISTRY else (member.path,)
        subjects = (*own, *rendered.get(member.path, ()))
        for introducer in dict.fromkeys(m.path for m in later):
            for term in introduced.get(introducer, ()):
                for subject in subjects:
                    yield member.path, subject, introducer, term


def analyse(
    repo_root: Path | None = None,
) -> tuple[tuple[StartThread, ...], dict[str, str], list[Violation]]:
    """Read the threads and find every violation, ignoring the baseline.

    Returns:
        The threads, the introducer of each introduced term, and every
        violation in thread, then reading, order.

    Raises:
        MetadataLoadError: If no start page declares a thread (DF-09-009).
        MetadataLoadErrors: Carrying every thread finding (DF-11-016) or every
            declaration fault (an unreadable page, a malformed or misplaced
            ``introduces``), since neither leaves an order to check.
    """
    root = repo_root or _find_repo_root()
    threads = check_threads(root)
    tree = classify_docs_tree(root)
    collector = FailureCollector()
    analysis = collect_declarations(root, tree, collector)
    collector.raise_if_any(summary=_summary(collector))

    introduced: dict[str, list[str]] = {}
    for term, introducer in sorted(analysis.introducers.items()):
        introduced.setdefault(introducer, []).append(term)
    pages = PageScanner(root / "docs", tree)
    rendered = _rendered_fragments(tree)

    violations: dict[ThreadOrderKey, Violation] = {}
    for thread in threads:
        for member, subject, introducer, term in _candidates(
            thread, introduced, rendered
        ):
            if (thread.path, subject, term) in violations:
                continue
            use = pages.unlinked_use(subject, analysis.terms[term], introducer)
            if use is None:
                continue
            violation = Violation(
                thread=thread.path,
                page=subject,
                term=term,
                used=use.text,
                position=use.position,
                member=member,
                introducer=introducer,
            )
            violations[violation.key] = violation
    return threads, analysis.introducers, list(violations.values())


#: The thread-order baseline, keyed by ``(thread, page, term)``.
THREAD_BASELINE = KeyedBaseline[ThreadOrderKey](
    BASELINE_PATH, _BASELINE_HEADER, ("thread", "page", "term")
)

read_baseline_entries = THREAD_BASELINE.entries
read_baseline = THREAD_BASELINE.read
write_baseline = THREAD_BASELINE.write


def check_thread_order(
    repo_root: Path | None = None,
    baseline: Mapping[ThreadOrderKey, str] | None = None,
) -> CheckResult:
    """Fail on every thread-order dependency that the baseline does not list.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        baseline: Violations tolerated, keyed by ``(thread, page, term)``.
            Defaults to the contents of :data:`BASELINE_PATH`.

    Raises:
        MetadataLoadError: If the target set is empty (DF-09-009).
        MetadataLoadErrors: Carrying every finding as ``path:line:col``: each
            unbaselined violation, and each baseline entry that no longer
            matches a violation.
    """
    threads, introducers, violations = analyse(repo_root)

    def stale(key: ThreadOrderKey) -> str:
        thread, page, term = key
        return (
            f"baselines docs/{thread} | docs/{page} | {term}, which is no "
            f"longer a violation; run `uv run docs-thread-order "
            f"--prune-baseline` and drop the key from _BASELINED in "
            f"test/metadata/docs/test_thread_order.py"
        )

    baselined, faults = THREAD_BASELINE.check(
        {v.key: v.error() for v in violations},
        baseline,
        path=BASELINE_PATH,
        stale_detail=stale,
    )
    collector = FailureCollector()
    collector.failures += faults
    collector.raise_if_any(summary=_summary(collector))
    return CheckResult(
        threads=len(threads),
        introductions=len(introducers),
        baselined=baselined,
    )


def prune_baseline(
    repo_root: Path | None = None, baseline_path: Path | None = None
) -> int:
    """Drop baseline entries that no longer match a violation.

    Never adds an entry, so it cannot be used to grow the baseline. The check
    refuses to run on a tree with an unreadable page, so every kept entry
    still matches a violation.

    Returns:
        How many entries were removed.
    """
    _threads, _introducers, violations = analyse(repo_root)
    baseline_path = baseline_path or BASELINE_PATH
    current = read_baseline(baseline_path)
    keep = prune_entries(
        current, (v.key for v in violations), (), page_of=lambda key: key[1]
    )
    write_baseline(keep, baseline_path)
    return len(current) - len(keep)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-thread-order`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that no page on a reading-path thread depends on a page "
            "later on that thread (DF-11-024)."
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
        result = check_thread_order()
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.threads} thread(s) against "
        f"{result.introductions} introduced concept(s); "
        f"{len(result.baselined)} baselined violation(s) remain."
    )


if __name__ == "__main__":
    main()
