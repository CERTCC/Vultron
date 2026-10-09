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
# Advanced to 948 when CSB-15-004 (DEPLOYER-only VFD causal gate) was added
# on main without a @pytest.mark.spec marker (merged into this branch).
# Lowered to 946 after xfail test with @pytest.mark.spec("CSB-15-004") was
# added, reducing the uncovered count from 948 to 946 (Bug #2607).
# Lowered to 937 — the actual uncovered count — when ADR-0080 added 28
# kind=protocol requirements (ASK-01..ASK-08, CP-05-007, OX-14-002, RSH-07-004,
# RSH-07-005) and covered all 28 in test_protocol_asks_specs.py, closing the
# 9-ID slack that had accumulated between the count and the ceiling (#2880).
# Re-pinned to the live count when #3827 marked the HP-09/HP-10 Offer
# addressing tests, closing the slack that had accumulated above the count.
# Lowered to 744 — the actual uncovered count — when #3600 enforced the MS-12
# decision tree (MS-12-006) and relabeled 215 story-less protocol specs that
# named code to kind=project or kind=process; a spec that leaves the protocol
# tier leaves this population, covered or not.
# Lowered to 712 — the live count — when PR #4174 marked CS-13-005 and the
# CM-23-015 strict xfail (#4163), closing slack left by earlier relabels.
# Lowered to 703 — the live count — when #4241 marked VP-10-002, VP-10-003
# and VP-10-005 alongside the new CM-32 strict xfails, closing slack left by
# PRs merged since.
# Held at 703 when BTND-05-003 was relabeled kind=protocol -> kind=project
# (#4346): it named a reference-implementation node (`CreateCaseParticipantNode`)
# and fails the "another protocol implementation would notice" gate, so it leaves
# the protocol tier. That relabel removes one uncovered protocol spec, pulling the
# live count back down to the pinned 703 after it had drifted to 704 (a concurrent
# count-pin race, #3984) — so the pin is unchanged but once again tight.
# Lowered to 702 — the live count — when #4371 restored CP-04-001's lost marker.
# CP-04-001 (a wire-observable protocol obligation: the report receiver sends
# Create(as_CaseProposal) with its own URI as actor) is verified by
# test/demo/test_case_proposal_round_trip.py — exactly the test its verification:
# field names — but #4355 deleted the dead-code create_create_case_tree test that
# had carried its only @pytest.mark.spec marker, dropping it into the uncovered
# set. #4346's BTND-05-003 relabel masked the net count but not the regression;
# restoring the marker on the test that actually verifies CP-04-001 removes it
# from the uncovered population for real.
# Held at 702 through #4353 (deleted ~17 orphaned case-construction nodes and
# their dead-code unit tests). Those tests had carried the only markers for four
# protocol specs — CM-02-004, CM-06-003, CM-12-003, CM-14-009 — but each
# obligation still lives in a surviving tree and is verified by a live test, so
# the markers were restored there rather than raising the ceiling (the exact
# #4371 lesson): CM-02-004 on the round-trip's attributed_to==owner assertion,
# CM-14-009 on TestADR0041OwnerParticipant (CASE_OWNER + RM.RECEIVED), CM-12-003
# on the queued Create(Case) whose `to` carries the reporter, and CM-06-003 on
# the case-update Announce whose actor is the CASE_MANAGER's URL. (CM-06-001 was
# already covered by test_update*.py and never regressed.) A dead-code deletion
# must not drop protocol coverage; the live count stays 702.
# Held at 702 through #4367 (deleted the dead CreateCaseParticipantNode chain
# and its test). That test had carried the only marker for CM-14-012 (reporter
# seated at RM.ACCEPTED as REPORTER and seeded SIGNATORY); the live seating is
# AddReporterParticipantNode, so the marker moved to the reporter tests in
# test_case_proposal_received_tree.py that assert exactly that.
# Lower this constant as more @pytest.mark.spec markers are added;
# never raise it to hide regressions in your own PR. Keep it pinned to the
# actual count — slack between the two is room for uncovered specs to grow
# unnoticed, which is the regression this ratchet exists to prevent.
# ---------------------------------------------------------------------------
MAX_UNCOVERED_PROTOCOL_SPECS = 702

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


@pytest.mark.spec_corpus
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
