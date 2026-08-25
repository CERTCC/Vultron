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

Asserts that the number of *uncovered* protocol-kind spec IDs stays at or
below MAX_UNCOVERED_PROTOCOL_SPECS, preventing coverage from regressing and
making the goal (zero uncovered) concrete. Lower the constant as more markers
are added; never raise it.

Spec: SR-05-005.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.coverage import SPEC_MARKER_RE

# ---------------------------------------------------------------------------
# Maximum uncovered protocol-kind spec requirements allowed by the ratchet.
# Set from the actual uncovered count after issue #2116 (1200 - 253 = 947).
# Lower this constant as more @pytest.mark.spec markers are added;
# never raise it.
# ---------------------------------------------------------------------------
MAX_UNCOVERED_PROTOCOL_SPECS = 947

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
        for m in SPEC_MARKER_RE.finditer(source):
            ids.add(m.group(1))
    return frozenset(ids)


@pytest.mark.spec("SR-05-005")
def test_protocol_spec_coverage_floor():
    """Uncovered protocol-kind specs must not exceed MAX_UNCOVERED_PROTOCOL_SPECS.

    Lowering the constant is the only allowed change — never raise
    MAX_UNCOVERED_PROTOCOL_SPECS or remove spec markers without adding new ones.

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
    if not protocol_ids:
        return  # nothing to enforce

    marked_ids = _collect_marked_ids()
    uncovered = sorted(protocol_ids - marked_ids)
    uncovered_count = len(uncovered)

    assert uncovered_count <= MAX_UNCOVERED_PROTOCOL_SPECS, (
        f"Uncovered protocol-kind specs ({uncovered_count}) exceeds ratchet "
        f"ceiling ({MAX_UNCOVERED_PROTOCOL_SPECS}). "
        f"Run `spec-coverage` to list all uncovered IDs. "
        f"First uncovered (up to 10): {uncovered[:10]}"
    )
