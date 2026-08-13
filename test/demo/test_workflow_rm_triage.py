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

"""Regression tests for the direct-path RM triage causal gate (Bug #2134).

``run_direct_path_rm_triage`` must engage the case (RM.VALID → RM.ACCEPTED)
only *after* the receiver's own participant status has committed RM.VALID.
``validate-report`` is dispatched asynchronously (HTTP 202), so gating
``engage-case`` on the mere presence of the case object — which appears
synchronously during validation — races the async RM.VALID commit and yields
``TransitionParticipantRMtoAccepted`` (HTTP 422).

These tests assert causal ordering (x happens THEREFORE y happens), not mere
sequence, so the fix cannot silently regress to a case-object-presence proxy.
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.workflow as workflow
from vultron.core.states.rm import RM


@pytest.fixture
def actors():
    """A receiver actor, its client, and the submit-report offer."""
    receiver = MagicMock()
    receiver.id_ = "http://coordinator:7999/api/v2/actors/coordinator"
    receiver_client = MagicMock(name="receiver_client")
    offer = MagicMock()
    offer.id_ = "urn:uuid:offer-1"
    case = MagicMock()
    case.id_ = "urn:uuid:case-1"
    return receiver, receiver_client, offer, case


def _nullcontext(_msg):
    return contextlib.nullcontext()


def test_engage_gated_on_receivers_own_rm_valid(actors):
    """engage-case fires only AFTER a wait for the receiver's own RM.VALID."""
    receiver, receiver_client, offer, case = actors
    call_order: list[str] = []

    def _validate(**_kwargs):
        call_order.append("validate")
        return {}

    def _wait_rm(*, client, case_id, actor_id, expected_states, **_kwargs):
        # Record each RM-state wait with the state set it gated on.
        if RM.ACCEPTED in expected_states and RM.VALID not in expected_states:
            call_order.append("wait_accepted")
        else:
            call_order.append("wait_valid")
        # The gate must poll the receiver's OWN status on its OWN container —
        # not the CaseActor via a third-party client.
        assert client is receiver_client
        assert actor_id == receiver.id_

    def _engage(**_kwargs):
        call_order.append("engage")
        return {}

    with (
        patch.object(
            workflow, "receiver_validates_report", side_effect=_validate
        ),
        patch.object(workflow, "find_case_for_offer", return_value=case),
        patch.object(
            workflow, "wait_for_participant_rm_state", side_effect=_wait_rm
        ),
        patch.object(workflow, "receiver_engages_case", side_effect=_engage),
        patch.object(workflow, "demo_check", side_effect=_nullcontext),
    ):
        result = workflow.run_direct_path_rm_triage(
            receiver_client=receiver_client,
            receiver=receiver,
            offer=offer,
        )

    assert result is case
    # Causal order: validate → wait(own RM.VALID) → engage → wait(own RM.ACCEPTED).
    assert call_order == ["validate", "wait_valid", "engage", "wait_accepted"]
    # The load-bearing invariant: the VALID gate precedes engagement.
    assert call_order.index("wait_valid") < call_order.index("engage")


def test_engage_not_called_when_rm_valid_never_commits(actors):
    """If the receiver's RM.VALID never commits, engage-case must never fire."""
    receiver, receiver_client, offer, case = actors
    engage_called = MagicMock()

    def _wait_rm(*, expected_states, **_kwargs):
        # Simulate the async RM.VALID commit never landing: the VALID gate
        # times out.  engage-case must not be reached.
        if RM.VALID in expected_states:
            raise AssertionError("timed out waiting for RM.VALID")

    with (
        patch.object(workflow, "receiver_validates_report"),
        patch.object(workflow, "find_case_for_offer", return_value=case),
        patch.object(
            workflow, "wait_for_participant_rm_state", side_effect=_wait_rm
        ),
        patch.object(
            workflow, "receiver_engages_case", side_effect=engage_called
        ),
        patch.object(workflow, "demo_check", side_effect=_nullcontext),
    ):
        with pytest.raises(AssertionError, match="RM.VALID"):
            workflow.run_direct_path_rm_triage(
                receiver_client=receiver_client,
                receiver=receiver,
                offer=offer,
            )

    engage_called.assert_not_called()
