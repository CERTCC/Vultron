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

"""Regression tests for the RM triage causal gates (Bugs #2134, #2376, #2548).

``run_direct_path_rm_triage`` and ``run_invite_path_rm_triage`` must engage
the case (RM.VALID → RM.ACCEPTED) only *after* the receiver's own participant
status has committed RM.VALID.  ``validate-report`` is dispatched
asynchronously (HTTP 202), so engaging without this gate races the async
commit and yields ``TransitionParticipantRMtoAccepted`` (HTTP 422).

The direct path carries a second, earlier gate (#2548): ``validate-report``
itself must wait for the CaseActor's ``Create(VulnerabilityCase)`` replica to
reach the receiver's own store.  Under ADR-0041 the receiver never creates the
case, and under PCR-01-003 co-locating the CaseActor grants no access to its
store — so validating before the replica lands means validating against no case
at all.

These tests assert causal ordering (x happens THEREFORE y happens), not mere
sequence, so the fix cannot silently regress to a case-object-presence proxy.
"""

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


def test_validate_gated_on_local_case_replica(actors):
    """validate-report fires only AFTER the case replica is in the local store.

    Regression test for ISSUE-2548.  The old flow triggered validate-report
    first and only then checked that a case existed, which meant the receiver
    routinely validated with no case in its own store.  ``TransitionRMtoValid``
    wrote the report-phase RM.VALID latch anyway, permanently short-circuiting
    ``CheckRMStateValid`` while the case-scoped participant state stayed at
    RECEIVED.
    """
    receiver, receiver_client, offer, case = actors
    call_order: list[str] = []

    def _find_case(client, offer_id):
        call_order.append("find_case")
        assert client is receiver_client
        return case

    with (
        patch.object(
            workflow,
            "receiver_validates_report",
            side_effect=lambda **_kw: call_order.append("validate"),
        ),
        patch.object(workflow, "find_case_for_offer", side_effect=_find_case),
        patch.object(workflow, "wait_for_participant_rm_state"),
        patch.object(workflow, "receiver_engages_case"),
    ):
        result = workflow.run_direct_path_rm_triage(
            receiver_client=receiver_client,
            receiver=receiver,
            offer=offer,
        )

    assert result is case
    assert call_order.index("find_case") < call_order.index("validate"), (
        "the receiver's own case replica must be resolved BEFORE"
        " validate-report is triggered (ISSUE-2548)"
    )


def test_validate_not_called_when_case_replica_never_arrives(actors):
    """No replica in the local store → validate-report must never fire.

    Absence of the case is a legitimate transient state, not a condition to
    write through (ARCH-15-001, ID-04-005).  The gate raises rather than
    returning ``None``, because every caller dereferences the returned case.
    """
    receiver, receiver_client, offer, _case = actors
    validate_called = MagicMock()
    engage_called = MagicMock()

    with (
        patch.object(
            workflow, "receiver_validates_report", side_effect=validate_called
        ),
        patch.object(workflow, "find_case_for_offer", return_value=None),
        patch.object(workflow, "wait_for_participant_rm_state"),
        patch.object(
            workflow, "receiver_engages_case", side_effect=engage_called
        ),
        pytest.raises(AssertionError, match="never arrived"),
    ):
        workflow.run_direct_path_rm_triage(
            receiver_client=receiver_client,
            receiver=receiver,
            offer=offer,
            # Short timeout: the point is that the poll never resolves, not how
            # long the real demo is willing to wait.
            timeout_seconds=0.05,
        )

    validate_called.assert_not_called()
    engage_called.assert_not_called()


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
    ):
        workflow.run_direct_path_rm_triage(
            receiver_client=receiver_client,
            receiver=receiver,
            offer=offer,
        )

    engage_called.assert_not_called()


# ---------------------------------------------------------------------------
# Invite-path gate — Bug #2376
# ---------------------------------------------------------------------------


@pytest.fixture
def invite_actors():
    """Actors, clients, and objects needed by run_invite_path_rm_triage."""
    invited_client = MagicMock(name="invited_client")
    invited_actor = MagicMock()
    invited_actor.id_ = "http://vendor:7999/api/v2/actors/vendor"
    offer = MagicMock()
    offer.id_ = "urn:uuid:offer-invite-1"
    report = MagicMock()
    report.id_ = "urn:uuid:report-1"
    finder = MagicMock()
    auth_client = MagicMock(name="auth_client")
    case = MagicMock()
    case.id_ = "urn:uuid:case-invite-1"
    invited_obj = MagicMock()
    invited_obj.id_ = "http://vendor:7999/api/v2/actors/vendor"
    return (
        invited_client,
        invited_actor,
        offer,
        report,
        finder,
        auth_client,
        case,
        invited_obj,
    )


def test_invite_path_engage_gated_on_own_rm_valid(invite_actors):
    """engage-case fires only AFTER the invited actor's own RM.VALID commits."""
    (
        invited_client,
        invited_actor,
        offer,
        report,
        finder,
        auth_client,
        case,
        invited_obj,
    ) = invite_actors
    call_order: list[str] = []

    def _wait_rm(*, client, case_id, actor_id, expected_states, **_kwargs):
        if client is auth_client:
            call_order.append("wait_caseactor_valid")
        elif (
            RM.ACCEPTED in expected_states and RM.VALID not in expected_states
        ):
            # own RM.ACCEPTED check
            call_order.append("wait_own_accepted")
        else:
            # own RM.VALID gate
            call_order.append("wait_own_valid")
            # Gate must poll the invited actor's OWN container.
            assert client is invited_client
            assert actor_id == invited_obj.id_

    def _engage(**_kwargs):
        call_order.append("engage")
        return {}

    with (
        patch.object(workflow, "wait_for_event_type_in_ledger"),
        patch.object(workflow, "receiver_validates_report"),
        patch.object(
            workflow, "wait_for_participant_rm_state", side_effect=_wait_rm
        ),
        patch.object(workflow, "receiver_engages_case", side_effect=_engage),
    ):
        workflow.run_invite_path_rm_triage(
            invited_client=invited_client,
            invited_actor=invited_actor,
            offer=offer,
            report=report,
            finder=finder,
            auth_client=auth_client,
            case=case,
            invited_obj=invited_obj,
        )

    # Causal invariant: own RM.VALID gate precedes engagement.
    assert "wait_own_valid" in call_order
    assert "engage" in call_order
    assert call_order.index("wait_own_valid") < call_order.index("engage")


def test_invite_path_caseactor_checks_read_the_case_actors_own_store(
    invite_actors,
):
    """The "CaseActor reflects …" checks must read the CaseActor's own store.

    ``auth_client`` addresses the *container* that hosts the CaseActor, and its
    own ``actor_id`` is the host actor — not the CaseActor.  Under ADR-0072
    decision 5 those are separate stores: the CaseActor writes the participant's
    RM transition to its own replica and emits no
    ``add_participant_status_to_participant`` ledger entry for it, so nothing
    ever advances the host's copy.  Reading the host's replica therefore reports
    ``RM.START`` until the timeout expires, no matter how healthy the run is
    (observed in fcvcv for both the RM.VALID and RM.ACCEPTED checks).
    """
    (
        invited_client,
        invited_actor,
        offer,
        report,
        finder,
        auth_client,
        case,
        invited_obj,
    ) = invite_actors
    case_actor_id = "http://coordinator:7999/api/v2/actors/case-actor"
    scopes: list[str | None] = []

    def _wait_rm(*, client, dl_actor_id=None, **_kwargs):
        if client is auth_client:
            scopes.append(dl_actor_id)

    with (
        patch.object(workflow, "wait_for_event_type_in_ledger"),
        patch.object(workflow, "receiver_validates_report"),
        patch.object(
            workflow, "resolve_case_actor_store_id", return_value=case_actor_id
        ),
        patch.object(
            workflow, "wait_for_participant_rm_state", side_effect=_wait_rm
        ),
        patch.object(workflow, "receiver_engages_case"),
    ):
        workflow.run_invite_path_rm_triage(
            invited_client=invited_client,
            invited_actor=invited_actor,
            offer=offer,
            report=report,
            finder=finder,
            auth_client=auth_client,
            case=case,
            invited_obj=invited_obj,
        )

    assert scopes == [case_actor_id, case_actor_id], (
        "both CaseActor checks must be scoped to the CaseActor's store; "
        f"got {scopes!r}"
    )


def test_invite_path_engage_not_called_when_own_rm_valid_never_commits(
    invite_actors,
):
    """If the invited actor's own RM.VALID never commits, engage-case must not fire."""
    (
        invited_client,
        invited_actor,
        offer,
        report,
        finder,
        auth_client,
        case,
        invited_obj,
    ) = invite_actors
    engage_called = MagicMock()

    def _wait_rm(*, client, expected_states, **_kwargs):
        # Simulate own-container RM.VALID never landing on the invited client.
        if client is invited_client and RM.VALID in expected_states:
            raise AssertionError("timed out waiting for own RM.VALID")

    with (
        patch.object(workflow, "wait_for_event_type_in_ledger"),
        patch.object(workflow, "receiver_validates_report"),
        patch.object(
            workflow, "wait_for_participant_rm_state", side_effect=_wait_rm
        ),
        patch.object(
            workflow, "receiver_engages_case", side_effect=engage_called
        ),
    ):
        workflow.run_invite_path_rm_triage(
            invited_client=invited_client,
            invited_actor=invited_actor,
            offer=offer,
            report=report,
            finder=finder,
            auth_client=auth_client,
            case=case,
            invited_obj=invited_obj,
        )

    engage_called.assert_not_called()
