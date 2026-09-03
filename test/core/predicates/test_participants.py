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

"""Tests for vultron.core.predicates.participants."""

from vultron.core.models.case_participant import (
    CaseParticipant,
    CaseActorParticipant,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.predicates.participants import (
    all_participants_rm_closed,
    vendor_vf_invariant_ok,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

_CONTEXT = "urn:uuid:case-context"
_ACTOR = "urn:uuid:actor-1"


def _make_participant(
    rm_state: RM,
    roles: list[CVDRole] | None = None,
    actor_id: str = _ACTOR,
) -> CaseParticipant:
    """Return a CaseParticipant with one ParticipantStatus at *rm_state*."""
    p = CaseParticipant(
        attributed_to=actor_id,
        context=_CONTEXT,
        case_roles=roles or [],
    )
    # Clear auto-seeded status and add one at the desired RM state.
    p.participant_statuses = [
        ParticipantStatus(
            context=_CONTEXT,
            attributed_to=actor_id,
            rm=RmDimension(state=rm_state),
        )
    ]
    return p


class TestAllParticipantsRmClosed:
    def test_empty_list_returns_true(self):
        assert all_participants_rm_closed([]) is True

    def test_single_closed_participant_returns_true(self):
        p = _make_participant(RM.CLOSED)
        assert all_participants_rm_closed([p]) is True

    def test_single_open_participant_returns_false(self):
        p = _make_participant(RM.ACCEPTED)
        assert all_participants_rm_closed([p]) is False

    def test_all_closed_returns_true(self):
        participants = [
            _make_participant(RM.CLOSED, actor_id="urn:uuid:actor-1"),
            _make_participant(RM.CLOSED, actor_id="urn:uuid:actor-2"),
        ]
        assert all_participants_rm_closed(participants) is True

    def test_one_not_closed_returns_false(self):
        participants = [
            _make_participant(RM.CLOSED, actor_id="urn:uuid:actor-1"),
            _make_participant(RM.ACCEPTED, actor_id="urn:uuid:actor-2"),
        ]
        assert all_participants_rm_closed(participants) is False

    def test_case_manager_skipped(self):
        """CASE_MANAGER participants are excluded from the convergence check."""
        case_manager = _make_participant(
            RM.ACCEPTED, roles=[CVDRole.CASE_MANAGER]
        )
        regular = _make_participant(RM.CLOSED)
        assert all_participants_rm_closed([case_manager, regular]) is True

    def test_only_case_manager_returns_true(self):
        """A list containing only CASE_MANAGER participants is vacuously True."""
        case_manager = _make_participant(
            RM.ACCEPTED, roles=[CVDRole.CASE_MANAGER]
        )
        assert all_participants_rm_closed([case_manager]) is True

    def test_participant_no_status_returns_false(self):
        """A participant with no status records is treated as not converged."""
        p = CaseParticipant(
            attributed_to=_ACTOR,
            context=_CONTEXT,
        )
        p.participant_statuses = []
        assert all_participants_rm_closed([p]) is False

    def test_rm_start_returns_false(self):
        p = _make_participant(RM.START)
        assert all_participants_rm_closed([p]) is False

    def test_rm_received_returns_false(self):
        p = _make_participant(RM.RECEIVED)
        assert all_participants_rm_closed([p]) is False

    def test_rm_valid_returns_false(self):
        p = _make_participant(RM.VALID)
        assert all_participants_rm_closed([p]) is False

    def test_rm_deferred_returns_false(self):
        p = _make_participant(RM.DEFERRED)
        assert all_participants_rm_closed([p]) is False

    def test_rm_invalid_returns_false(self):
        p = _make_participant(RM.INVALID)
        assert all_participants_rm_closed([p]) is False

    def test_case_actor_participant_skipped(self):
        """CaseActorParticipant (COORDINATOR + CASE_MANAGER) is excluded."""
        ca = CaseActorParticipant(
            attributed_to="urn:uuid:case-actor",
            context=_CONTEXT,
        )
        regular = _make_participant(RM.CLOSED)
        assert all_participants_rm_closed([ca, regular]) is True

    def test_mixed_roles_including_case_manager_skipped(self):
        """Participant with CASE_MANAGER among multiple roles is still skipped."""
        p = _make_participant(
            RM.ACCEPTED,
            roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
        )
        assert all_participants_rm_closed([p]) is True


class TestVendorVfInvariantOk:
    """vendor_vf_invariant_ok: VENDOR participant cannot hold CS_vf.vf (ADR-0084, PRM-06-002)."""

    def test_none_vf_state_always_ok(self):
        assert vendor_vf_invariant_ok([CVDRole.VENDOR], None) is True

    def test_vendor_with_vf_fails(self):
        assert vendor_vf_invariant_ok([CVDRole.VENDOR], CS_vf.vf) is False

    def test_vendor_with_Vf_ok(self):
        assert vendor_vf_invariant_ok([CVDRole.VENDOR], CS_vf.Vf) is True

    def test_vendor_with_VF_ok(self):
        assert vendor_vf_invariant_ok([CVDRole.VENDOR], CS_vf.VF) is True

    def test_non_vendor_with_vf_ok(self):
        assert vendor_vf_invariant_ok([CVDRole.COORDINATOR], CS_vf.vf) is True

    def test_non_vendor_with_Vf_ok(self):
        assert vendor_vf_invariant_ok([CVDRole.COORDINATOR], CS_vf.Vf) is True

    def test_empty_roles_with_vf_ok(self):
        assert vendor_vf_invariant_ok([], CS_vf.vf) is True

    def test_vendor_plus_coordinator_with_vf_fails(self):
        assert (
            vendor_vf_invariant_ok(
                [CVDRole.VENDOR, CVDRole.COORDINATOR], CS_vf.vf
            )
            is False
        )
