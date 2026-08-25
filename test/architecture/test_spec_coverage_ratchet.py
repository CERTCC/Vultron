#!/usr/bin/env python

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
"""CI ratchet: @pytest.mark.spec coverage for protocol-kind requirements.

Asserts that at least PROTOCOL_COVERAGE_FLOOR_PCT percent of all
protocol-kind spec IDs are referenced by at least one @pytest.mark.spec
marker in the test suite, preventing marker adoption from drifting back
toward zero.

Spec: SR-05-005.
"""

import re

import pytest

from test.architecture import _corpus

# ---------------------------------------------------------------------------
# Minimum acceptable coverage for protocol-kind spec requirements.
# This floor was calibrated from the actual coverage achieved after issue
# #2116 (253/1200 = 21.1%). Raise this constant as coverage improves;
# never lower it.
# ---------------------------------------------------------------------------
PROTOCOL_COVERAGE_FLOOR_PCT = 21

_SPEC_MARKER_RE = re.compile(r'@pytest\.mark\.spec\(["\']([^"\']+)["\']\)')

_TEST_ROOT = _corpus.REPO_ROOT / "test"
_SPEC_DIR = _corpus.REPO_ROOT / "specs"


def _collect_marked_ids() -> frozenset[str]:
    """Return spec IDs referenced by @pytest.mark.spec markers in the test corpus.

    Uses the shared module-level corpus (TB-13-001) — no per-test I/O.
    """
    ids: set[str] = set()
    for _, source in _corpus.sources_mentioning(
        "pytest.mark.spec", under=_TEST_ROOT
    ):
        for m in _SPEC_MARKER_RE.finditer(source):
            ids.add(m.group(1))
    return frozenset(ids)


@pytest.mark.spec("SR-05-005")
def test_protocol_spec_coverage_floor():
    """At least PROTOCOL_COVERAGE_FLOOR_PCT% of protocol-kind specs have a marker.

    Raises the floor is the only allowed change — never lower
    PROTOCOL_COVERAGE_FLOOR_PCT or remove spec markers without adding new ones.

    Spec: SR-05-005.
    """
    from vultron.metadata.specs.registry import load_registry
    from vultron.metadata.specs.schema import SpecKind

    registry = load_registry(_SPEC_DIR)
    protocol_ids = frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if spec.kind == SpecKind.PROTOCOL
    )
    total = len(protocol_ids)
    if total == 0:
        return  # nothing to enforce

    marked_ids = _collect_marked_ids()
    covered = protocol_ids & marked_ids
    covered_count = len(covered)

    meets_floor = covered_count * 100 >= PROTOCOL_COVERAGE_FLOOR_PCT * total

    sample_uncovered = sorted(protocol_ids - covered)[:10]

    assert meets_floor, (
        f"Protocol-kind @pytest.mark.spec coverage fell below floor: "
        f"{covered_count}/{total} "
        f"({100 * covered_count / total:.1f}% < {PROTOCOL_COVERAGE_FLOOR_PCT}%). "
        f"Run `spec-coverage` to list all uncovered IDs. "
        f"First uncovered (up to 10): {sample_uncovered}"
    )
