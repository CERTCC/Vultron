"""Check that each normative-status banner marks exactly its declared pages.

Requirements: specs/diataxis-requirements.yaml DF-12-006, DF-12-016 to
DF-12-018, DF-12-007, DF-11-025, DF-09-009; attribution per MS-17 via
:mod:`vultron.metadata.file_loading`.

The banner ``docs/includes/normative.md`` says "This page is normative". It is
true of the **normative set** only: the Protocol Specification's body section
pages, including the Requirements Catalog pages that render the ``protocol``
and ``foundation`` requirement tiers (ADR-0136, ADR-0147). The
specification's landing page, its single-page edition, its annexes and its
open-questions page are not in the set. The set is declared once, here, in
:data:`NORMATIVE_PAGES`; no page frontmatter key carries it.

The banner ``docs/includes/specification_governs.md`` says a page is
informative and that the specification governs where they differ. It marks
the informative pages that explain the protocol's design, declared in
:data:`SPECIFICATION_GOVERNS_PAGES` (DF-12-007). ``subject: protocol``
(DF-11-025) is necessary but not sufficient: the protocol-floor companions are
protocol pages that carry the not-normative banner instead.

The check reads ``{% include-markdown %}`` directives, not plain-text mentions
of a file, and reports, for each banner, each as ``path:line`` where it has
one:

* a declared page that does not exist, so a list follows the pages when they
  move (as when the Requirements Catalog replaced the per-tier pages,
  ADR-0147);
* a declared page that does not include the banner in the page itself — a
  banner that arrives through a shared fragment is not counted;
* any other page or shared fragment that includes it, except the pages in
  :data:`BANNER_EXAMPLE_PAGES`, which show the banners as examples;
* an empty target set or an empty declared set (DF-09-009).

A page listed twice in one set, or in both sets, is reported as well: a page
is either normative or an informative protocol-design page.

A protocol-design page is also reported when it declares a ``subject`` other
than ``protocol``, or carries the not-normative banner as well.

Usage::

    uv run docs-normative-banner   # check (pre-commit, CI)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.docs.page_frontmatter import (
    frontmatter_key_lines,
    include_directives,
)
from vultron.metadata.docs.page_schema import Subject, declared_subject
from vultron.metadata.docs.requirement_catalog import (
    CATALOG_LANDING,
    CATALOG_PAGES,
)
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    load_frontmatter,
)

#: ``docs/``-relative path of the normative banner.
BANNER = "includes/normative.md"

#: ``docs/``-relative path of the "specification governs" banner (DF-12-007).
GOVERNS_BANNER = "includes/specification_governs.md"

#: ``docs/``-relative path of the not-normative banner, which a page carrying
#: :data:`GOVERNS_BANNER` carries instead of (DF-12-007).
NOT_NORMATIVE_BANNER = "includes/not_normative.md"

#: The normative set, ``docs/``-relative (DF-12-017): the body section pages,
#: the Requirements Catalog's among them. The catalog's landing and themed
#: pages come from its placement table, so a page added there joins the set.
NORMATIVE_PAGES: tuple[str, ...] = (
    "reference/vultron-spec/introduction.md",
    "reference/vultron-spec/layers.md",
    "reference/vultron-spec/tracking-models.md",
    "reference/vultron-spec/interactions.md",
    "reference/vultron-spec/conformance.md",
    CATALOG_LANDING,
    *(page.path for page in CATALOG_PAGES),
    "reference/vultron-spec/considerations.md",
)

#: The informative pages that explain the protocol's design, ``docs/``-relative
#: (DF-12-007): Formal Protocol, the process models, the case lifecycle, the
#: capability model, behavior logic, the Protocol Design pages and Future Work.
#: Declared here because ``subject: protocol`` does not single them out: the
#: Protocol Specification's own pages, the protocol-floor companions (Messages,
#: the Conformance Matrix, the Quick Reference), the ActivityStreams guides and
#: the tutorials are protocol pages too, and carry the normative or
#: not-normative banner, or none. A new page that explains the protocol's
#: design joins this list.
SPECIFICATION_GOVERNS_PAGES: tuple[str, ...] = (
    "reference/formal_protocol/conclusion.md",
    "reference/formal_protocol/index.md",
    "reference/formal_protocol/messages.md",
    "reference/formal_protocol/protocol_definition.md",
    "reference/formal_protocol/states.md",
    "reference/formal_protocol/transitions.md",
    "topics/activity_vocabulary_design.md",
    "topics/actor-knowledge-model.md",
    "topics/behavior_logic/bt_notation.md",
    "topics/behavior_logic/index.md",
    "topics/behavior_logic/use-cases/embargo-lifecycle.md",
    "topics/behavior_logic/use-cases/index.md",
    "topics/behavior_logic/use-cases/prioritize-report.md",
    "topics/behavior_logic/use-cases/propose-case.md",
    "topics/behavior_logic/use-cases/validate-report.md",
    "topics/capability_model/index.md",
    "topics/case_lifecycle/a_case_under_vultron.md",
    "topics/case_lifecycle/case_authority_and_trust.md",
    "topics/case_lifecycle/case_initialization.md",
    "topics/case_lifecycle/case_ledger_sync.md",
    "topics/case_lifecycle/case_manager_and_ledger.md",
    "topics/case_lifecycle/case_model.md",
    "topics/case_lifecycle/ownership_transfer.md",
    "topics/future_work/federation.md",
    "topics/future_work/index.md",
    "topics/future_work/open_questions.md",
    "topics/message_semantics.md",
    "topics/process_models/cs/cs_model.md",
    "topics/process_models/cs/index.md",
    "topics/process_models/cs/transitions.md",
    "topics/process_models/em/defaults.md",
    "topics/process_models/em/early_termination.md",
    "topics/process_models/em/formal_model.md",
    "topics/process_models/em/index.md",
    "topics/process_models/em/negotiating.md",
    "topics/process_models/em/principles.md",
    "topics/process_models/em/split_merge.md",
    "topics/process_models/em/working_with_others.md",
    "topics/process_models/index.md",
    "topics/process_models/model_interactions/index.md",
    "topics/process_models/model_interactions/rm_em.md",
    "topics/process_models/model_interactions/rm_em_cs.md",
    "topics/process_models/rm/formal_model.md",
    "topics/process_models/rm/index.md",
    "topics/process_models/rm/rm_interactions.md",
    "topics/protocol_flow.md",
)

#: Pages that document the banners and so include both as examples.
BANNER_EXAMPLE_PAGES: tuple[str, ...] = ("reference/conventions.md",)


@dataclass(frozen=True)
class CheckResult:
    """What a passing check saw, for its summary line."""

    scanned_files: int
    normative_pages: int
    governs_pages: int = 0


@dataclass(frozen=True)
class _BannerRule:
    """One banner and the exact set of pages that must carry it.

    Attributes:
        banner: ``docs/``-relative path of the banner fragment.
        pages: ``docs/``-relative pages that must include it in the page.
        list_name: The constant in this module that declares *pages*.
        requirement: The requirement ID the rule enforces.
        set_name: What the declared pages are called in a finding.
        elsewhere: What a finding on any other page tells it to use instead.
    """

    banner: str
    pages: tuple[str, ...]
    list_name: str
    requirement: str
    set_name: str
    elsewhere: str


def banner_include_lines(
    path: Path, docs_dir: Path, banner: str = BANNER
) -> list[int]:
    """1-based line of each directive in *path* that includes *banner*."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        text.count("\n", 0, offset) + 1
        for offset, target, _ in include_directives(
            path, docs_dir, existing=False
        )
        if target == banner
    ]


def _check_rule(
    rule: _BannerRule,
    files: list[Path],
    docs_dir: Path,
    examples: frozenset[str],
    collector: FailureCollector,
) -> None:
    """Report every page that breaks *rule*: a declared page without the
    banner in the page itself, or any other page or fragment with it."""
    if not (docs_dir / rule.banner).is_file():
        with collector.attempt():
            raise MetadataLoadError(
                f"the banner does not exist; the {rule.set_name} pages "
                f"include it ({rule.requirement})",
                path=f"docs/{rule.banner}",
            )
    present = {f.relative_to(docs_dir).as_posix() for f in files}
    for rel in sorted(set(rule.pages) - present):
        with collector.attempt():
            raise MetadataLoadError(
                f"is listed in {rule.list_name} in "
                "vultron/metadata/docs/normative_banner.py but does not exist; "
                f"name the pages that now hold the {rule.set_name} there "
                f"instead ({rule.requirement})",
                path=f"docs/{rel}",
            )
    for path in files:
        rel = path.relative_to(docs_dir).as_posix()
        lines = banner_include_lines(path, docs_dir, rule.banner)
        if rel in rule.pages:
            if not lines:
                with collector.attempt():
                    raise MetadataLoadError(
                        f"is in the {rule.set_name} but does not include "
                        f'"{rule.banner}" in the page itself; add the '
                        "include-markdown directive below the title — a "
                        "banner from a shared fragment does not count "
                        f"({rule.requirement})",
                        path=f"docs/{rel}",
                    )
            continue
        if rel in examples:
            continue
        for line in lines:
            with collector.attempt():
                raise MetadataLoadError(
                    f'includes "{rule.banner}" but is not in the '
                    f"{rule.set_name} ({rule.list_name}); {rule.elsewhere}",
                    path=f"docs/{rel}",
                    line=line,
                )


def _check_governs_pages(
    pages: tuple[str, ...],
    docs_dir: Path,
    root: Path,
    collector: FailureCollector,
) -> None:
    """Report a protocol-design page that is not ``subject: protocol`` or
    that also carries the not-normative banner (DF-12-007, DF-11-025).

    A page with no valid ``subject``, or whose frontmatter does not parse, is
    left to ``docs-frontmatter``, which reports it against the page, so one
    fault is not named by two tools.
    """
    for rel in pages:
        path = docs_dir / rel
        if not path.is_file():
            continue  # reported by _check_rule
        try:
            metadata = load_frontmatter(path, root=root).metadata
        except MetadataLoadError:
            metadata = {}
        subject = declared_subject(metadata.get("subject"))
        if subject is not None and subject != Subject.PROTOCOL:
            with collector.attempt():
                raise MetadataLoadError(
                    f"explains the protocol's design (listed in "
                    f"SPECIFICATION_GOVERNS_PAGES) but declares subject: "
                    f"{subject.value}; declare subject: protocol, or remove "
                    "it from the list (DF-12-007, DF-11-025)",
                    path=f"docs/{rel}",
                    line=frontmatter_key_lines(path).get("subject"),
                )
        for line in banner_include_lines(path, docs_dir, NOT_NORMATIVE_BANNER):
            with collector.attempt():
                raise MetadataLoadError(
                    f'includes "{NOT_NORMATIVE_BANNER}" but explains the '
                    f'protocol\'s design, so it carries "{GOVERNS_BANNER}" '
                    "instead; remove the not-normative banner (DF-12-007)",
                    path=f"docs/{rel}",
                    line=line,
                )


def _check_declared_sets(
    normative: tuple[str, ...],
    governs: tuple[str, ...],
    collector: FailureCollector,
) -> None:
    """Report a page listed twice in one set, or in both (DF-12-006/007).

    A page cannot be both normative and informative, and a repeated entry
    would report each of its faults twice.
    """
    for name, pages in (
        ("NORMATIVE_PAGES", normative),
        ("SPECIFICATION_GOVERNS_PAGES", governs),
    ):
        for rel in sorted({p for p in pages if pages.count(p) > 1}):
            with collector.attempt():
                raise MetadataLoadError(
                    f"is listed more than once in {name} in "
                    "vultron/metadata/docs/normative_banner.py; list it once",
                    path=f"docs/{rel}",
                )
    for rel in sorted(set(normative) & set(governs)):
        with collector.attempt():
            raise MetadataLoadError(
                "is listed in both NORMATIVE_PAGES and "
                "SPECIFICATION_GOVERNS_PAGES in "
                "vultron/metadata/docs/normative_banner.py; a page is either "
                "normative or an informative protocol-design page, so remove "
                "it from one (DF-12-006, DF-12-007)",
                path=f"docs/{rel}",
            )


def check_normative_banner(
    repo_root: Path | None = None,
    *,
    normative_pages: Iterable[str] = NORMATIVE_PAGES,
    governs_pages: Iterable[str] = SPECIFICATION_GOVERNS_PAGES,
    example_pages: Iterable[str] = BANNER_EXAMPLE_PAGES,
) -> CheckResult:
    """Check that each banner is on exactly its declared pages.

    The normative banner marks exactly the normative set (DF-12-006); the
    "specification governs" banner marks exactly the informative
    protocol-design pages, each ``subject: protocol`` and without the
    not-normative banner (DF-12-007).

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        normative_pages: ``docs/``-relative normative-set pages.
        governs_pages: ``docs/``-relative protocol-design pages.
        example_pages: ``docs/``-relative pages allowed to show both
            banners.

    Returns:
        Counts for a summary line.

    Raises:
        MetadataLoadError: If no file resolves under ``docs/``, or either
            declared set is empty (DF-09-009).
        MetadataLoadErrors: Carrying every finding, each attributed to its
            file as ``path:line`` where it has a position.
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    normative = tuple(normative_pages)
    governs = tuple(governs_pages)
    examples = frozenset(example_pages)
    files = sorted(docs_dir.rglob("*.md")) if docs_dir.is_dir() else []
    empty = (
        "pages to check"
        if not files
        else "normative-set pages"
        if not normative
        else "protocol-design pages"
        if not governs
        else None
    )
    if empty is not None:
        raise MetadataLoadError(
            f"resolved no {empty}; an empty target set is a failure, not a "
            "pass (DF-09-009)",
            path="docs",
        )

    collector = FailureCollector()
    _check_declared_sets(normative, governs, collector)
    present = {f.relative_to(docs_dir).as_posix() for f in files}
    for rel in sorted(examples - present):
        with collector.attempt():
            raise MetadataLoadError(
                "is listed in BANNER_EXAMPLE_PAGES in "
                "vultron/metadata/docs/normative_banner.py but does not "
                "exist; name the page that now documents the banners there "
                "instead (DF-12-016)",
                path=f"docs/{rel}",
            )
    rules = (
        _BannerRule(
            banner=BANNER,
            pages=normative,
            list_name="NORMATIVE_PAGES",
            requirement="DF-12-006",
            set_name="normative set",
            elsewhere=(
                f'use "{GOVERNS_BANNER}" on a page that explains the '
                f'protocol\'s design (DF-12-007) or "{NOT_NORMATIVE_BANNER}" '
                "(DF-12-016)"
            ),
        ),
        _BannerRule(
            banner=GOVERNS_BANNER,
            pages=governs,
            list_name="SPECIFICATION_GOVERNS_PAGES",
            requirement="DF-12-007",
            set_name="protocol-design pages",
            elsewhere=(
                "add the page to SPECIFICATION_GOVERNS_PAGES if it explains "
                "the protocol's design, or use "
                f'"{NOT_NORMATIVE_BANNER}" (DF-12-007)'
            ),
        ),
    )
    for rule in rules:
        _check_rule(rule, files, docs_dir, examples, collector)
    _check_governs_pages(governs, docs_dir, root, collector)

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} banner finding(s) (DF-12-006, "
            "DF-12-007):"
        )
    )
    return CheckResult(
        scanned_files=len(files),
        normative_pages=len(normative),
        governs_pages=len(governs),
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-normative-banner`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that docs/includes/normative.md is included by exactly the "
            "normative-set pages, and docs/includes/specification_governs.md "
            "by exactly the protocol-design pages."
        )
    )
    parser.parse_args(argv)

    try:
        result = check_normative_banner()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Checked {result.scanned_files} docs file(s); the normative banner "
        f"is on exactly the {result.normative_pages} normative-set page(s), "
        f"and the specification-governs banner on exactly the "
        f"{result.governs_pages} protocol-design page(s)."
    )


if __name__ == "__main__":
    main()
