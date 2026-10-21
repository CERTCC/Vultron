"""Check that the normative banner marks exactly the normative set.

Requirements: specs/diataxis-requirements.yaml DF-12-006, DF-09-009;
attribution per MS-17 via :mod:`vultron.metadata.file_loading`.

The banner ``docs/includes/normative.md`` says "This page is normative". It is
true of the **normative set** only: the Protocol Specification's body section
pages and the ``protocol`` and ``foundation`` requirement-tier pages
(ADR-0136, ADR-0147). The specification's landing page, its single-page
edition, its annexes and its open-questions page are not in the set. The set is
declared once, here, in :data:`NORMATIVE_PAGES`; no page frontmatter key
carries it.

The check reads ``{% include-markdown %}`` directives, not plain-text mentions
of the file, and reports, each as ``path:line`` where it has one:

* a declared page that does not exist, so the list follows the Requirements
  Catalog when it replaces the per-tier pages;
* a declared page that does not include the banner in the page itself — a
  banner that arrives through a shared fragment is not counted;
* any other page or shared fragment that includes it, except the pages in
  :data:`BANNER_EXAMPLE_PAGES`, which show the banner as an example;
* an empty target set (DF-09-009).

Informative pages that explain the protocol's design carry
``docs/includes/specification_governs.md`` instead (DF-12-007).

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
from vultron.metadata.docs.page_frontmatter import include_directives
from vultron.metadata.file_loading import FailureCollector, MetadataLoadError

#: ``docs/``-relative path of the normative banner.
BANNER = "includes/normative.md"

#: The normative set, ``docs/``-relative (DF-12-006). Replace the two tier
#: pages with the Requirements Catalog pages when the catalog lands (ADR-0147).
NORMATIVE_PAGES: tuple[str, ...] = (
    "reference/vultron-spec/introduction.md",
    "reference/vultron-spec/layers.md",
    "reference/vultron-spec/tracking-models.md",
    "reference/vultron-spec/interactions.md",
    "reference/vultron-spec/conformance.md",
    "reference/vultron-spec/considerations.md",
    "reference/specs/protocol.md",
    "reference/specs/foundation.md",
)

#: Pages that document the banners and so include this one as an example.
BANNER_EXAMPLE_PAGES: tuple[str, ...] = ("reference/conventions.md",)


@dataclass(frozen=True)
class CheckResult:
    """What a passing check saw, for its summary line."""

    scanned_files: int
    normative_pages: int


def banner_include_lines(path: Path, docs_dir: Path) -> list[int]:
    """1-based line of each directive in *path* that includes the banner."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        text.count("\n", 0, offset) + 1
        for offset, target, _ in include_directives(
            path, docs_dir, existing=False
        )
        if target == BANNER
    ]


def check_normative_banner(
    repo_root: Path | None = None,
    *,
    normative_pages: Iterable[str] = NORMATIVE_PAGES,
    example_pages: Iterable[str] = BANNER_EXAMPLE_PAGES,
) -> CheckResult:
    """Check that the banner is on every normative-set page and nowhere else.

    Args:
        repo_root: Repository root. Defaults to the enclosing checkout.
        normative_pages: ``docs/``-relative normative-set pages.
        example_pages: ``docs/``-relative pages allowed to show the banner.

    Returns:
        Counts for a summary line.

    Raises:
        MetadataLoadError: If no file resolves under ``docs/``, or the
            normative set is empty (DF-09-009).
        MetadataLoadErrors: Carrying every finding, each attributed to its
            file as ``path:line`` where it has a position.
    """
    root = repo_root or _find_repo_root()
    docs_dir = root / "docs"
    declared = tuple(normative_pages)
    examples = frozenset(example_pages)
    files = sorted(docs_dir.rglob("*.md")) if docs_dir.is_dir() else []
    if not files or not declared:
        raise MetadataLoadError(
            "resolved no "
            + ("pages to check" if not files else "normative-set pages")
            + "; an empty target set is a failure, not a pass (DF-09-009)",
            path="docs",
        )

    collector = FailureCollector()
    if not (docs_dir / BANNER).is_file():
        with collector.attempt():
            raise MetadataLoadError(
                "the normative banner does not exist; the normative-set "
                "pages include it (DF-12-006)",
                path=f"docs/{BANNER}",
            )

    present = {f.relative_to(docs_dir).as_posix() for f in files}
    for rel in sorted({*declared, *examples} - present):
        with collector.attempt():
            listed = (
                "NORMATIVE_PAGES"
                if rel in declared
                else "BANNER_EXAMPLE_PAGES"
            )
            raise MetadataLoadError(
                f"is listed in {listed} in "
                "vultron/metadata/docs/normative_banner.py but does not exist; "
                "name the pages that now hold the normative set there instead "
                "(DF-12-006, ADR-0147)",
                path=f"docs/{rel}",
            )

    for path in files:
        rel = path.relative_to(docs_dir).as_posix()
        lines = banner_include_lines(path, docs_dir)
        if rel in declared:
            if not lines:
                with collector.attempt():
                    raise MetadataLoadError(
                        f'is in the normative set but does not include "{BANNER}" '
                        "in the page itself; add the include-markdown directive "
                        "below the title — a banner from a shared fragment does "
                        "not count (DF-12-006)",
                        path=f"docs/{rel}",
                    )
            continue
        if rel in examples:
            continue
        for line in lines:
            with collector.attempt():
                raise MetadataLoadError(
                    f'includes "{BANNER}" but is not in the normative set; use '
                    '"includes/specification_governs.md" on a page that '
                    "explains the protocol's design (DF-12-007) or "
                    '"includes/not_normative.md" (DF-12-006)',
                    path=f"docs/{rel}",
                    line=line,
                )

    collector.raise_if_any(
        summary=(
            f"{len(collector.failures)} normative banner finding(s) (DF-12-006):"
        )
    )
    return CheckResult(scanned_files=len(files), normative_pages=len(declared))


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``docs-normative-banner`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that docs/includes/normative.md is included by exactly the "
            "normative-set pages."
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
        f"is on exactly the {result.normative_pages} normative-set page(s)."
    )


if __name__ == "__main__":
    main()
