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

"""Regression tests for _SignEmbargoConsentLeafNode (ADR-0048, CM-10-001).

AC-4: The invitee MUST reach PEC.SIGNATORY after signing embargo consent.
This test MUST fail on main before the fix and pass after.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.accept_invite_tree import (
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import PEC
from test.core.behaviors.bt_harness import BTTestScenario

_ACTOR_ID = "https://example.org/actors/invitee"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"


def _run_sign_node(
    bt_scenario: BTTestScenario,
    starting_pec: PEC,
) -> tuple[Status, CaseParticipant]:
    """Create a CaseParticipant at ``starting_pec``, run the sign node, return result."""
    participant = CaseParticipant(
        id_=_ACTOR_ID,
        attributed_to=_ACTOR_ID,
        embargo_consent_state=starting_pec,
    )

    node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)

    result = bt_scenario.run(
        node,
        actor_id=_ACTOR_ID,
        new_invite_participant=participant,
        active_embargo_id=_EMBARGO_ID,
    )
    return result.status, participant


class TestSignEmbargoConsentLeafNode:
    """_SignEmbargoConsentLeafNode must set invitee to SIGNATORY (CM-10-001)."""

    def test_invitee_reaches_signatory_from_no_embargo(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Regression: invitee starting at NO_EMBARGO must reach SIGNATORY.

        Before the ADR-0048 fix, apply_pec_trigger(NO_EMBARGO, ACCEPT)
        returned NO_EMBARGO unchanged and the node logged success while
        leaving consent unrecorded — CM-10-001 violated.
        """
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.NO_EMBARGO
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_invitee_reaches_signatory_from_invited(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who was formally INVITED also reaches SIGNATORY."""
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.INVITED
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_invitee_reaches_signatory_from_lapsed(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who LAPSED (embargo revised) can re-consent without a new invite."""
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.LAPSED
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_already_signatory_is_no_op(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Participant already SIGNATORY: ACCEPT is invalid, state unchanged."""
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.SIGNATORY
        )
        # apply_pec_trigger returns the state unchanged on an invalid trigger
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_embargo_id_recorded_on_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The active embargo ID is appended to accepted_embargo_ids."""
        _, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.NO_EMBARGO
        )
        assert _EMBARGO_ID in participant.accepted_embargo_ids

    def test_failure_when_participant_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """FAILURE returned when new_invite_participant is absent."""
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            active_embargo_id=_EMBARGO_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_embargo_id_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """FAILURE returned when active_embargo_id is absent."""
        participant = CaseParticipant(
            id_=_ACTOR_ID,
            attributed_to=_ACTOR_ID,
            embargo_consent_state=PEC.NO_EMBARGO,
        )
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            new_invite_participant=participant,
        )
        assert result.status == Status.FAILURE
