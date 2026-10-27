"""Check that no nav section holds both protocol and implementation pages.

Requirements: specs/diataxis-requirements.yaml DF-11-020 (a nav section never
holds both a page about the protocol and a page about the reference
implementation), DF-11-025 (the ``subject`` key the check reads), DF-09-009
(an empty target set fails); attribution per MS-17 via
:mod:`vultron.metadata.file_loading`. Design rationale:
``notes/site-information-architecture.md`` § "The front desk and the floors"
(ADR-0136).

A **section** is any labeled group in the ``mkdocs.yml`` nav, at any depth;
the top-level list of tabs is not one. A section mixes when the pages under
it, at any depth, include both a ``subject: protocol`` page and a
``subject: implementation`` page; ``neutral`` pages sit anywhere. Every
section that mixes is reported, innermost first, so one misplaced page is
named once per section it sits in, starting with the group it was put in. The
finding names the section by its label trail and lists the pages of whichever
subject is fewer in it, which are the likely misplacements; on a tie it lists
both.

A page with no valid ``subject`` counts as neither, because ``docs-frontmatter``
already reports it against the page; failing here too would name one fault
from two tools. A nav entry naming a file that does not exist is reported.

Usage::

    uv run docs-nav-subjects   # check (pre-commit, CI)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.base import mkdocs_config, repo_root as _find_repo_root
from vultron.metadata.docs.landing_pages import (
    is_url,
    split_nav_item,
    unreadable_nav_item,
)
from vultron.metadata.docs.page_schema import Subject
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    load_frontmatter,
)

#: The two subjects that must not share a section (DF-11-020).
_SEPARATED: tuple[Subject, Subject] = (
    Subject.PROTOCOL,
    Subject.IMPLEMENTATION,
)


@dataclass
class CheckResult:
    """What a passing check saw, for its summary line."""

    sections: int = 0
    pages: int = 0


@dataclass
class _Held:
    """The separated-subject pages under one nav item, in nav order."""

    pages: dict[Subject, list[str]] = field(
        default_factory=lambda: {subject: [] for subject in _SEPARATED}
    )

    def add(self, other: _Held) -> None:
        for subject in _SEPARATED:
            self.pages[subject].extend(other.pages[subject])

    def has(self, subject: Subject) -> bool:
        return bool(self.pages[subject])


class _Walk:
    """One pass over the nav, reading each page's ``subject`` once."""

    def __init__(self, root: Path, collector: FailureCollector) -> None:
        self.docs_dir = root / "docs"
        self.root = root
        self.collector = collector
        self.result = CheckResult()
        self._subjects: dict[str, Subject | None] = {}

    def subject_of(self, rel: str) -> Subject | None:
        """The page's declared subject, or ``None`` when it has no valid one.

        Raises:
            MetadataLoadError: If the page does not exist.
        """
        if rel not in self._subjects:
            path = self.docs_dir / rel
            if not path.is_file():
                self._subjects[rel] = None
                raise MetadataLoadError(
                    "is listed in the mkdocs.yml nav but does not exist",
                    path=f"docs/{rel}",
                )
            self.result.pages += 1
            raw = load_frontmatter(path, root=self.root).metadata.get(
                "subject"
            )
            valid = {member.value for member in Subject}
            self._subjects[rel] = (
                Subject(raw) if isinstance(raw, str) and raw in valid else None
            )
        return self._subjects[rel]

    def item(self, item: object, trail: tuple[str, ...]) -> _Held:
        """The separated-subject pages one nav *item* holds."""
        held = _Held()
        label, value = split_nav_item(item)
        if isinstance(value, str):
            if is_url(value):
                return held
            subject: Subject | None = None
            with self.collector.attempt():
                subject = self.subject_of(value)
            if subject is not None and subject in _SEPARATED:
                held.pages[subject].append(value)
            return held
        if not isinstance(value, list) or label is None:
            with self.collector.attempt():
                raise unreadable_nav_item(item)
            return held
        return self.section(value, (*trail, label))

    def section(self, items: list[object], trail: tuple[str, ...]) -> _Held:
        """Walk one section, reporting it if the pages under it mix."""
        self.result.sections += 1
        held = _Held()
        for child in items:
            held.add(self.item(child, trail))
        if all(held.has(subject) for subject in _SEPARATED):
            with self.collector.attempt():
                raise _mix_finding(trail, held)
        return held


def _mix_finding(trail: tuple[str, ...], held: _Held) -> MetadataLoadError:
    """The finding for a section that mixes, naming its likely misplacements."""
    counts: Mapping[Subject, int] = {
        subject: len(held.pages[subject]) for subject in _SEPARATED
    }
    fewest = min(counts.values())
    named = [s for s in _SEPARATED if counts[s] == fewest]
    parts = [
        f"{subject.value} page(s) "
        + ", ".join(f"docs/{p}" for p in held.pages[subject])
        for subject in named
    ]
    if len(named) == 1:
        (other,) = (s for s in _SEPARATED if s not in named)
        parts.append(
            f"beside {counts[other]} {other.value} page(s) "
            f"(first: docs/{held.pages[other][0]})"
        )
    return MetadataLoadError(
        f"nav section '{' > '.join(trail)}' holds "
        + " ".join(parts)
        + "; the protocol and the reference implementation never share a "
        "section, so move the page(s) to a section of their own subject, or "
        "correct a wrong subject: key (DF-11-020)",
        path="mkdocs.yml",
    )


def check_nav_subjects(repo_root: Path | None = None) -> CheckResult:
    """Check every nav section for a protocol/implementation mix.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.

    Returns:
        Counts for a summary line.

    Raises:
        MetadataLoadError: If the nav resolves no section or no page
            (DF-09-009).
        MetadataLoadErrors: Carrying every finding.
    """
    root = repo_root or _find_repo_root()
    nav = mkdocs_config(root).get("nav")
    collector = FailureCollector()
    walk = _Walk(root, collector)
    for item in nav if isinstance(nav, list) else []:
        label, value = split_nav_item(item)
        if isinstance(value, list) and label is not None:
            walk.section(value, (label,))
        else:
            # A top-level page or link is not in a section; read it only so
            # a missing file is still reported.
            walk.item(item, ())
    if not walk.result.sections or not walk.result.pages:
        raise MetadataLoadError(
            "the nav resolved no "
            + ("sections" if not walk.result.sections else "pages")
            + " to check; an empty target set is a failure, not a pass "
            "(DF-09-009)",
            path="mkdocs.yml",
        )
    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} nav subject finding(s) (DF-11-020):"
        )
    )
    return walk.result


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-nav-subjects`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that no mkdocs.yml nav section holds both a "
            "subject: protocol page and a subject: implementation page."
        )
    )
    parser.parse_args(argv)

    try:
        result = check_nav_subjects()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.sections} nav section(s) over {result.pages} "
        "page(s); none mixes protocol and implementation pages."
    )


if __name__ == "__main__":
    main()
