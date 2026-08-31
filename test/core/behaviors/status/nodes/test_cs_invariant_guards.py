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

"""Unit tests for CS invariant precondition guards.

Covers issue #2524 AC-1, AC-2, AC-3:
  (a) A-event rejected from pX state      — CheckCsEphemeralStateNode
  (b) P-event accepted from pX state      — CheckCsEphemeralStateNode
  (c) History-prefix rejection on invalid sequence — CheckCsHistoryPrefixNode
  (d) Valid partial history accepted       — CheckCsHistoryPrefixNode

Per CSB-17-012 (ephemeral pX→P) and CSB-17-005 (history prefix).
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.cs_invariant_guards import (
    CheckCsEphemeralStateNode,
    CheckCsHistoryPrefixNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.cs import CS_pxa
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/inv-guards-01"
STATUS_ID = "https://example.org/cases/inv-guards-01/statuses/asserted"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


def _make_case_with_pxa(pxa_state: CS_pxa) -> VulnerabilityCase:
    """Return a core VulnerabilityCase whose current PXA state is *pxa_state*."""
    case = VulnerabilityCase(
        id_=CASE_ID, name="Invariant Guard Test", attributed_to=ACTOR_ID
    )
    if pxa_state != CS_pxa.pxa:
        case.append_case_status(pxa_state=pxa_state)
    return case


def _run(bridge: BTBridge, node: py_trees.behaviour.Behaviour) -> Status:
    result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
    return result.status


# ---------------------------------------------------------------------------
# CheckCsEphemeralStateNode
# ---------------------------------------------------------------------------


class TestCheckCsEphemeralStateNode:
    """AC-1: ephemeral pX state requires P next (CSB-17-012)."""

    @pytest.mark.spec("CSB-17-012")
    def test_a_event_rejected_from_pX_state(self, dl, bridge):
        """AC-3a: A-event from pXa → FAILURE (pX is ephemeral, P required)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXA
        )
        dl.create(asserted)

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.FAILURE

    @pytest.mark.spec("CSB-17-012")
    def test_p_event_accepted_from_pX_state(self, dl, bridge):
        """AC-3b: P-event from pXa → SUCCESS (satisfies ephemeral requirement)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXa
        )
        dl.create(asserted)

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_p_and_a_together_from_pX_state(self, dl, bridge):
        """P+A together from pXa → SUCCESS (P advances regardless of A)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXA
        )
        dl.create(asserted)

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_non_ephemeral_state_passes(self, dl, bridge):
        """Non-pX current state → SUCCESS (no ephemeral constraint)."""
        case = _make_case_with_pxa(CS_pxa.Pxa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXa
        )
        dl.create(asserted)

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_first_ever_status_succeeds(self, dl, bridge):
        """No current status (first ever) → SUCCESS; no constraint applies."""
        # Bare case with no materialized CaseStatus objects
        bare_case = VulnerabilityCase(id_=CASE_ID, context=ACTOR_ID)
        dl.create(bare_case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXA
        )
        dl.create(asserted)

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_case_not_found_succeeds(self, bridge):
        """Case not in DataLayer → SUCCESS (cannot evaluate constraint)."""
        node = CheckCsEphemeralStateNode(
            case_id="https://example.org/cases/nonexistent",
            status_id=STATUS_ID,
        )
        assert _run(bridge, node) == Status.SUCCESS

    def test_unresolvable_asserted_defers(self, dl, bridge):
        """Status not in DL and no fallback → SUCCESS (deferred to FilterCsEm)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        # Do NOT create the asserted status in DL

        node = CheckCsEphemeralStateNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_fallback_used_when_not_in_dl(self, dl, bridge):
        """Core CaseStatus fallback used when status not in DL; ephemeral check runs."""
        from vultron.core.models.case_status import CaseStatus
        from vultron.core.models.dimensions import PxaDimension

        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        # Core CaseStatus (not wire as_CaseStatus) is recognised by _resolve_asserted.
        fallback = CaseStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            pxa=PxaDimension(state=CS_pxa.pXA),
        )
        # Do NOT put fallback in DL; pass as status_obj_fallback.

        node = CheckCsEphemeralStateNode(
            case_id=CASE_ID,
            status_id=STATUS_ID,
            status_obj_fallback=fallback,
        )
        # pXA asserted from pXa (A-event, P not advancing) → FAILURE
        assert _run(bridge, node) == Status.FAILURE


# ---------------------------------------------------------------------------
# CheckCsHistoryPrefixNode
# ---------------------------------------------------------------------------


class TestCheckCsHistoryPrefixNode:
    """AC-2: proposed CS transition must yield a valid history prefix (CSB-17-005)."""

    @pytest.mark.spec("CSB-17-005")
    def test_invalid_prefix_rejected(self, dl, bridge):
        """AC-3c: A-event from pXa → FAILURE (pX→A violates CSB-17-005)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXA
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.FAILURE

    @pytest.mark.spec("CSB-17-005")
    def test_valid_partial_history_accepted(self, dl, bridge):
        """AC-3d: P-event from pXa → SUCCESS (pX→P is a valid prefix step)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXa
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_x_event_from_pxa_accepted(self, dl, bridge):
        """X-event from baseline pxa → SUCCESS (pX state is valid prefix)."""
        case = _make_case_with_pxa(CS_pxa.pxa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXa
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_no_pxa_change_passes(self, dl, bridge):
        """Identical PXA state → SUCCESS (no event to validate)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXa
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_multi_event_skip_deferred(self, dl, bridge):
        """Multi-event advance (pxa→PXA) → SUCCESS (deferred to monotone filter)."""
        case = _make_case_with_pxa(CS_pxa.pxa)
        dl.create(case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.PXA
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_case_not_found_succeeds(self, bridge):
        """Case not in DataLayer → SUCCESS."""
        node = CheckCsHistoryPrefixNode(
            case_id="https://example.org/cases/nonexistent",
            status_id=STATUS_ID,
        )
        assert _run(bridge, node) == Status.SUCCESS

    def test_first_ever_status_succeeds(self, dl, bridge):
        """No current status (first ever) → SUCCESS."""
        from vultron.core.models.case import VulnerabilityCase

        bare_case = VulnerabilityCase(id_=CASE_ID, context=ACTOR_ID)
        dl.create(bare_case)
        asserted = as_CaseStatus(
            id_=STATUS_ID, context=CASE_ID, pxa_state=CS_pxa.pXA
        )
        dl.create(asserted)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS

    def test_unresolvable_asserted_defers(self, dl, bridge):
        """Status not in DL and no fallback → SUCCESS (deferred to FilterCsEm)."""
        case = _make_case_with_pxa(CS_pxa.pXa)
        dl.create(case)

        node = CheckCsHistoryPrefixNode(case_id=CASE_ID, status_id=STATUS_ID)
        assert _run(bridge, node) == Status.SUCCESS
