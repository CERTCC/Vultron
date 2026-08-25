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
coverage for protocol-kind requirements loaded from the spec registry.

Runnable locally::

    spec-coverage
    spec-coverage specs/ test/

Coverage reporter requirements: specs/spec-registry.yaml SR-05-004, SR-05-005.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.specs.registry import (
    SpecRegistry,
    _find_repo_root,
    load_registry,
)
from vultron.metadata.specs.schema import SpecKind

_SPEC_MARKER_RE = re.compile(r'@pytest\.mark\.spec\(["\']([^"\']+)["\']\)')


@dataclass
class ProtocolCoverageReport:
    """Coverage of @pytest.mark.spec markers for protocol-kind requirements."""

    total: int
    covered_count: int
    uncovered: list[str] = field(default_factory=list)

    @property
    def covered_pct(self) -> float:
        """Percentage of protocol specs with at least one marker (0–100)."""
        if self.total == 0:
            return 0.0
        return 100.0 * self.covered_count / self.total


def collect_marked_ids(test_root: Path) -> frozenset[str]:
    """Scan ``*.py`` files under *test_root* and return referenced spec IDs.

    Uses a plain regex pass over each file; does not parse ASTs.

    Args:
        test_root: Directory to scan recursively for ``*.py`` files.

    Returns:
        Frozen set of all spec ID strings referenced by ``@pytest.mark.spec``
        markers found under *test_root*.
    """
    ids: set[str] = set()
    for py_file in sorted(test_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _SPEC_MARKER_RE.finditer(source):
            ids.add(m.group(1))
    return frozenset(ids)


def compute_protocol_coverage(
    registry: SpecRegistry,
    test_root: Path,
) -> ProtocolCoverageReport:
    """Compute @pytest.mark.spec coverage for protocol-kind requirements.

    Args:
        registry: Loaded :class:`~vultron.metadata.specs.registry.SpecRegistry`.
        test_root: Directory to scan for test files.

    Returns:
        :class:`ProtocolCoverageReport` with covered/uncovered counts and the
        sorted list of uncovered protocol-kind spec IDs.
    """
    protocol_ids = frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if spec.kind == SpecKind.PROTOCOL
    )
    marked_ids = collect_marked_ids(test_root)
    covered_ids = protocol_ids & marked_ids
    uncovered = sorted(protocol_ids - covered_ids)
    return ProtocolCoverageReport(
        total=len(protocol_ids),
        covered_count=len(covered_ids),
        uncovered=uncovered,
    )


def main() -> None:
    """CLI entry point: print uncovered protocol-kind spec IDs to stdout."""
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Report @pytest.mark.spec coverage for protocol-kind requirements."
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
        test_root = _find_repo_root() / "test"

    report = compute_protocol_coverage(registry, test_root)
    pct = report.covered_pct

    print(
        f"Protocol-kind spec coverage: "
        f"{report.covered_count}/{report.total} ({pct:.1f}%)"
    )
    if report.uncovered:
        print(
            f"\nUncovered protocol-kind requirements ({len(report.uncovered)}):"
        )
        for spec_id in report.uncovered:
            print(f"  {spec_id}")


if __name__ == "__main__":  # pragma: no cover
    main()
