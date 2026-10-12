#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Protocol-tier @pytest.mark.spec coverage reporter.

Scans the test suite for ``@pytest.mark.spec("ID")`` markers and reports
coverage for the requirements every implementation must obey — ``protocol``
and ``foundation`` kind (:data:`~vultron.metadata.specs.schema.IMPLEMENTER_KINDS`)
— loaded from the spec registry.

Runnable locally::

    spec-coverage
    spec-coverage specs/ test/

Coverage reporter requirements: specs/spec-registry.yaml SR-05-004, SR-05-005.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.specs.registry import (
    SpecRegistry,
    find_repo_root,
    load_registry,
)
from vultron.metadata.specs.schema import IMPLEMENTER_KINDS

SPEC_MARKER_RE = re.compile(r'@pytest\.mark\.spec\(["\']([^"\']+)["\']\)')


@dataclass
class ImplementerCoverageReport:
    """Coverage of @pytest.mark.spec markers for implementer-kind requirements."""

    total: int
    covered_count: int
    uncovered: list[str] = field(default_factory=list)

    @property
    def covered_pct(self) -> float:
        """Percentage of implementer-kind specs with a marker (0–100)."""
        if self.total == 0:
            return 0.0
        return 100.0 * self.covered_count / self.total


def marked_ids_in(sources: Iterable[str]) -> frozenset[str]:
    """Spec IDs referenced by ``@pytest.mark.spec`` markers in *sources*.

    Each item of *sources* is one file's text. A plain regex pass; no AST.
    """
    return frozenset(
        m.group(1)
        for source in sources
        for m in SPEC_MARKER_RE.finditer(source)
    )


def _read_sources(test_root: Path) -> Iterator[str]:
    for py_file in sorted(test_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        try:
            yield py_file.read_text(encoding="utf-8")
        except OSError:
            continue


def collect_marked_ids(test_root: Path) -> frozenset[str]:
    """Scan ``*.py`` files under *test_root* and return referenced spec IDs.

    Uses a plain regex pass over each file; does not parse ASTs.

    Args:
        test_root: Directory to scan recursively for ``*.py`` files.

    Returns:
        Frozen set of all spec ID strings referenced by ``@pytest.mark.spec``
        markers found under *test_root*.
    """
    return marked_ids_in(_read_sources(test_root))


def _coverage_report(
    registry: SpecRegistry, marked_ids: frozenset[str]
) -> ImplementerCoverageReport:
    implementer_ids = frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if spec.kind in IMPLEMENTER_KINDS
    )
    covered_ids = implementer_ids & marked_ids
    return ImplementerCoverageReport(
        total=len(implementer_ids),
        covered_count=len(covered_ids),
        uncovered=sorted(implementer_ids - covered_ids),
    )


def compute_implementer_coverage(
    registry: SpecRegistry,
    test_root: Path,
) -> ImplementerCoverageReport:
    """Compute @pytest.mark.spec coverage for implementer-kind requirements.

    Args:
        registry: Loaded :class:`~vultron.metadata.specs.registry.SpecRegistry`.
        test_root: Directory to scan for test files.

    Returns:
        :class:`ImplementerCoverageReport` with covered/uncovered counts and the
        sorted list of uncovered ``protocol`` and ``foundation`` spec IDs.
    """
    return _coverage_report(registry, collect_marked_ids(test_root))


def uncovered_implementer_ids(
    repo_root: Path, *, test_sources: Iterable[str] | None = None
) -> frozenset[str]:
    """``protocol`` and ``foundation`` IDs under *repo_root* no marker covers.

    The per-item extractor behind the SR-05-005 growth guard
    (:func:`vultron.metadata.specs.growth_guard.added_since_base`): it reads
    ``specs/`` and ``test/`` under *repo_root*, so the same function runs on
    the working tree and on a materialized base tree.

    Args:
        repo_root: Tree holding ``specs/`` (and ``test/`` unless
            *test_sources* is given).
        test_sources: Test file texts already in memory, used instead of
            reading ``test/`` — the architecture suite passes its shared
            ``test/architecture/_corpus.py`` sources here.
    """
    if test_sources is None:
        test_sources = _read_sources(repo_root / "test")
    report = _coverage_report(
        load_registry(repo_root / "specs"), marked_ids_in(test_sources)
    )
    return frozenset(report.uncovered)


def main() -> None:
    """CLI entry point: print uncovered implementer-kind spec IDs to stdout."""
    parser = argparse.ArgumentParser(
        description=(
            "Report @pytest.mark.spec coverage for protocol- and "
            "foundation-kind requirements."
        )
    )
    parser.add_argument(
        "spec_dir",
        nargs="?",
        default=None,
        help="Directory containing spec YAML files (default: auto-detect specs/)",
    )
    parser.add_argument(
        "test_dir",
        nargs="?",
        default=None,
        help="Directory containing test files (default: test/ at repo root)",
    )
    args = parser.parse_args()

    spec_dir = Path(args.spec_dir) if args.spec_dir else None
    registry = load_registry(spec_dir)

    if args.test_dir:
        test_root = Path(args.test_dir)
    else:
        test_root = find_repo_root() / "test"

    report = compute_implementer_coverage(registry, test_root)
    pct = report.covered_pct

    print(
        f"Protocol and foundation spec coverage: "
        f"{report.covered_count}/{report.total} ({pct:.1f}%)"
    )
    if report.uncovered:
        print(
            "\nUncovered protocol and foundation requirements "
            f"({len(report.uncovered)}):"
        )
        for spec_id in report.uncovered:
            print(f"  {spec_id}")


if __name__ == "__main__":  # pragma: no cover
    main()
