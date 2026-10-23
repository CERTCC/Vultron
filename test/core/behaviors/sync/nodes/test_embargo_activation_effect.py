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
"""Replay of the case owner's embargo decisions on a participant replica.

``activate_embargo_on_case`` (the owner's ``Accept(EmbargoEvent,
target=Case)``) is copied through the one apply function: the ``ACTIVATE``
step and the owner's agreement it states (ADR-0124).
``reject_embargo_proposal_on_case`` (its ``Reject``) is copied the same way,
as the ``REJECT`` step (CM-23-016).  Either way the register moves and EM
derives from it.
"""

from datetime import timedelta
from typing import Any

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from test.support.embargo_register import activate, propose
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    RegisterChange,
    rejection_changes,
    termination_changes,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)

MANAGER = "https://example.org/actors/case-manager"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"
PRIOR_EMBARGO_ID = f"{CASE_ID}/embargo_events/e0"


def _embargo_snapshot() -> dict[str, Any]:
    return {
        "type": "EmbargoEvent",
        "id": EMBARGO_ID,
        "context": CASE_ID,
        "endTime": (now_utc() + timedelta(days=60)).isoformat(),
    }


def _seed(
    datalayer, em: EM, *, owner_participant: bool = False
) -> VulnerabilityCase:
    """A replica whose register has the entry's embargo open as a proposal.

    ``REVISE`` adds an earlier embargo in force, which the activation
    supersedes.  EM is derived from the register (ADR-0122).
    """
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    if em is EM.REVISE:
        # The activation reads the embargo it replaces (EMB-18-003).
        datalayer.save(
            EmbargoEvent(
                id_=PRIOR_EMBARGO_ID,
                context=CASE_ID,
                end_time=now_utc() + timedelta(days=90),
            )
        )
        activate(case, PRIOR_EMBARGO_ID)
    propose(case, EMBARGO_ID)
    assert case.em_state == em
    if owner_participant:
        participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/owner",
            attributed_to=OWNER_ACTOR_ID,
            context=CASE_ID,
        )
        # Attached first, so it takes a row per register entry (ADR-0122).
        case.add_participant(participant)
        datalayer.save(participant)
    datalayer.save(case)
    return case


def _apply(bridge, embargo: Any, *, accept: bool = True):
    """Replay the owner's Accept (or Reject) of *embargo* on the replica."""
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/owner-decision",
            semantic_type=(
                "activate_embargo_on_case"
                if accept
                else "reject_embargo_proposal_on_case"
            ),
            payload_snapshot={
                "type": "Accept" if accept else "Reject",
                "actor": OWNER_ACTOR_ID,
                "context": CASE_ID,
                "object": embargo,
                "target": CASE_ID,
            },
            prev_log_hash="0" * 64,
        )
    )
    node = (
        ApplyEmbargoActivationFromLedgerNode(name="ApplyActivation")
        if accept
        else ApplyEmbargoProposalRejectionFromLedgerNode(name="ApplyRejection")
    )
    return bridge.execute_with_setup(
        tree=node,
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER),
    )


def _case(datalayer) -> VulnerabilityCase:
    case = datalayer.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.spec("EMB-02-001")
@pytest.mark.parametrize("em_before", [EM.PROPOSED, EM.REVISE])
def test_the_entry_activates_the_embargo_on_the_replica(
    bridge, datalayer, em_before
):
    _seed(datalayer, em_before)

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS

    case = _case(datalayer)
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == EMBARGO_ID
    # Stored from the inline copy the entry carries (EMB-18-003).
    assert isinstance(datalayer.read(EMBARGO_ID), EmbargoEvent)


@pytest.mark.spec("SYNC-12-003")
def test_an_embargo_already_in_force_is_a_no_op(bridge, datalayer):
    _seed(datalayer, EM.PROPOSED)
    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    before = _case(datalayer).model_dump()

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    assert _case(datalayer).model_dump() == before


@pytest.mark.spec("SYNC-12-001")
def test_a_replica_without_the_case_skips(bridge, datalayer):
    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS
    assert datalayer.read(EMBARGO_ID) is None


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("EMB-18-003")
def test_an_embargo_the_replica_cannot_reconstruct_fails(bridge, datalayer):
    """A bare id the replica does not hold blocks persisting the entry."""
    _seed(datalayer, EM.PROPOSED)

    assert _apply(bridge, EMBARGO_ID).status == Status.FAILURE
    assert _case(datalayer).current_status.em.state == EM.PROPOSED


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("MSM-07-005")
def test_the_activation_records_the_owners_agreement_on_the_replica(
    bridge, datalayer
):
    """Activating is the owner's agreement (ADR-0122), replayed too."""
    _seed(datalayer, EM.PROPOSED, owner_participant=True)

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS

    owner = datalayer.read(f"{CASE_ID}/participants/owner")
    assert isinstance(owner, CaseParticipant)
    assert owner.consent_for(EMBARGO_ID) == EmbargoConsentState.AGREED


@pytest.mark.spec("MSM-07-008")
@pytest.mark.spec("CM-23-016")
def test_a_declined_owner_agrees_on_the_replica(bridge, datalayer):
    """The Accept states the owner's agreement, a DECLINED row included."""
    _seed(datalayer, EM.PROPOSED, owner_participant=True)
    owner = datalayer.read(f"{CASE_ID}/participants/owner")
    assert isinstance(owner, CaseParticipant)
    datalayer.save(
        owner.model_copy(
            update={
                "embargo_consents": [
                    EmbargoConsent(
                        embargo_id=EMBARGO_ID,
                        state=EmbargoConsentState.DECLINED,
                        attributed_to=OWNER_ACTOR_ID,
                    )
                ]
            }
        )
    )

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS

    owner = datalayer.read(f"{CASE_ID}/participants/owner")
    assert isinstance(owner, CaseParticipant)
    assert owner.consent_for(EMBARGO_ID) == EmbargoConsentState.AGREED


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("EP-05-001")
def test_the_replica_carries_nobody_over_from_the_accept_alone(
    bridge, datalayer
):
    """Each CARRY_OVER row is its own CASE_MANAGER entry (ADR-0124).

    A signatory of the replaced embargo keeps its row for the revision as
    it is until that entry arrives; the replica runs no EP-05-001 logic.
    """
    _seed(datalayer, EM.REVISE)
    signatory = CaseParticipant(
        id_=f"{CASE_ID}/participants/signatory",
        attributed_to=PARTICIPANT_ACTOR_ID,
        context=CASE_ID,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=PRIOR_EMBARGO_ID,
                state=EmbargoConsentState.AGREED,
            ),
            EmbargoConsent(
                embargo_id=EMBARGO_ID, state=EmbargoConsentState.UNINVITED
            ),
        ],
    )
    case = _case(datalayer)
    case.actor_participant_index[PARTICIPANT_ACTOR_ID] = signatory.id_
    datalayer.save(case)
    datalayer.save(signatory)

    assert _apply(bridge, _embargo_snapshot()).status == Status.SUCCESS

    held = datalayer.read(signatory.id_)
    assert isinstance(held, CaseParticipant)
    assert held.consent_for(EMBARGO_ID) is EmbargoConsentState.UNINVITED


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("SYNC-12-001")
def test_an_activation_of_an_embargo_not_open_here_is_refused(
    bridge, datalayer
):
    """The register here never saw the proposal: the step does not apply,
    so the entry is refused, never patched over (ADR-0124)."""
    datalayer.save(
        VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    )

    assert _apply(bridge, _embargo_snapshot()).status == Status.FAILURE

    case = _case(datalayer)
    assert case.em_state is EM.NONE
    assert case.embargo_register == []
    # A refused entry stores nothing, the carried embargo included.
    assert datalayer.read(EMBARGO_ID) is None


@pytest.mark.spec("EMB-18-003")
def test_a_carried_embargo_of_another_case_is_refused(bridge, datalayer):
    """An inline copy is stored only when it belongs to this case."""
    _seed(datalayer, EM.PROPOSED)

    foreign = {**_embargo_snapshot(), "context": "https://example.org/cases/x"}
    assert _apply(bridge, foreign).status == Status.FAILURE

    assert datalayer.read(EMBARGO_ID) is None
    assert _case(datalayer).em_state is EM.PROPOSED


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EP-08-001")
@pytest.mark.parametrize(
    "em_before, em_after", [(EM.PROPOSED, EM.NONE), (EM.REVISE, EM.ACTIVE)]
)
def test_the_rejection_entry_rejects_the_proposal_on_the_replica(
    bridge, datalayer, em_before, em_after
):
    _seed(datalayer, em_before, owner_participant=True)

    result = _apply(bridge, _embargo_snapshot(), accept=False)

    assert result.status == Status.SUCCESS
    case = _case(datalayer)
    assert case.em_state == em_after
    assert case.proposed_embargo_ids == []
    # The owner's decision writes no consent (ADR-0122).
    owner = datalayer.read(f"{CASE_ID}/participants/owner")
    assert isinstance(owner, CaseParticipant)
    assert owner.consent_for(EMBARGO_ID) is EmbargoConsentState.UNINVITED


@pytest.mark.spec("SYNC-12-003")
def test_a_redelivered_rejection_is_a_no_op(bridge, datalayer):
    _seed(datalayer, EM.PROPOSED)
    assert _apply(bridge, _embargo_snapshot(), accept=False).status == (
        Status.SUCCESS
    )
    before = _case(datalayer).model_dump()

    assert _apply(bridge, _embargo_snapshot(), accept=False).status == (
        Status.SUCCESS
    )
    assert _case(datalayer).model_dump() == before


@pytest.mark.spec("SYNC-12-001")
def test_a_replica_without_the_case_skips_the_rejection(bridge, datalayer):
    assert _apply(bridge, _embargo_snapshot(), accept=False).status == (
        Status.SUCCESS
    )
    assert datalayer.read(EMBARGO_ID) is None


@pytest.mark.spec("CM-23-016")
def test_a_rejection_naming_a_bare_id_copies_the_step(bridge, datalayer):
    """The step needs only the register entry, never the embargo's record."""
    _seed(datalayer, EM.PROPOSED)

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.SUCCESS
    case = _case(datalayer)
    assert case.em_state == EM.NONE
    assert case.embargo_register_status(EMBARGO_ID) is (
        EmbargoRegisterStatus.REJECTED
    )


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("SYNC-12-001")
def test_a_rejection_of_an_embargo_not_open_here_is_refused(bridge, datalayer):
    """The register here never saw the proposal: refused, never patched."""
    datalayer.save(
        VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    )

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.FAILURE
    case = _case(datalayer)
    assert case.em_state is EM.NONE
    assert case.embargo_register == []


@pytest.mark.spec("SYNC-12-001")
def test_a_rejection_naming_no_embargo_fails(bridge, datalayer):
    _seed(datalayer, EM.PROPOSED)

    assert _apply(bridge, None, accept=False).status == Status.FAILURE
    assert _case(datalayer).em_state == EM.PROPOSED


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("CM-23-016")
def test_the_rejection_of_the_last_revision_after_disclosure_is_copied(
    bridge, datalayer
):
    """The ``Reject`` entry is the REJECT step, after disclosure as before.

    The replica decides nothing: the revision ends ``REJECTED`` and the prior
    terms stand until the CASE_MANAGER's ``Remove`` entry that follows
    carries the ``TERMINATE`` step (MSM-07-009).
    """
    case = _seed(datalayer, EM.REVISE)
    case.append_case_status(pxa=CS_pxa.Pxa)
    datalayer.save(case)

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.SUCCESS
    held = _case(datalayer)
    assert held.embargo_register_status(EMBARGO_ID) is (
        EmbargoRegisterStatus.REJECTED
    )
    assert held.em_state == EM.ACTIVE


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("CM-23-016")
def test_a_rejection_after_another_open_proposal_with_pxa_set_applies(
    bridge, datalayer
):
    """Only the *last* revision is answered with ET (EP-08-001)."""
    case = _seed(datalayer, EM.REVISE)
    other = f"{CASE_ID}/embargo_events/e2"
    propose(case, other)
    case.append_case_status(pxa=CS_pxa.Pxa)
    datalayer.save(case)

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.SUCCESS
    held = _case(datalayer)
    assert held.embargo_register_status(EMBARGO_ID) is (
        EmbargoRegisterStatus.REJECTED
    )
    assert held.proposed_embargo_ids == [other]
    assert held.em_state == EM.REVISE


def _ended_embargo(datalayer, *, reject_first: bool) -> VulnerabilityCase:
    """A replica whose embargo in force ended after P was set.

    With *reject_first* the revision was rejected before the termination,
    as the CASE_MANAGER's ET-answered rejection leaves it (MSM-07-009);
    otherwise the termination cancelled it (EP-08-004).
    """
    case = _seed(datalayer, EM.REVISE)
    case.append_case_status(pxa=CS_pxa.Pxa)
    if reject_first:
        case.apply_embargo_register_step(rejection_changes(EMBARGO_ID))
    case.apply_embargo_register_step(
        termination_changes(case.embargo_register, EmbargoTermination.early())
    )
    datalayer.save(case)
    assert _case(datalayer).embargo_register_status(EMBARGO_ID) is (
        EmbargoRegisterStatus.REJECTED
        if reject_first
        else EmbargoRegisterStatus.CANCELLED
    )
    return case


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("EMB-04-002")
def test_a_seed_past_the_termination_replays_the_rejection_forward_only(
    bridge, datalayer
):
    """A seed taken after the ET-answered rejection holds the revision
    ``REJECTED``: the entry is in place, so it is a no-op, not a refusal
    whose Announce is held (ADR-0114)."""
    _ended_embargo(datalayer, reject_first=True)
    before = _case(datalayer).model_dump()

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.SUCCESS
    assert _case(datalayer).model_dump() == before


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("SYNC-12-001")
def test_a_revision_cancelled_by_a_termination_refuses_the_rejection(
    bridge, datalayer
):
    """The CASE_MANAGER never commits a Reject of a revision a termination
    cancelled, with P/X/A set or not, so this replica has diverged and the
    entry is refused (ADR-0124).  No slot decides the case away (CM-23-016).
    """
    _ended_embargo(datalayer, reject_first=False)
    before = _case(datalayer).model_dump()

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.FAILURE
    assert _case(datalayer).model_dump() == before


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("EMB-16-001")
def test_an_abandoned_proposal_refuses_the_rejection(bridge, datalayer):
    """A proposal a threat signal abandoned (no embargo in force) is not one
    the CASE_MANAGER could still reject: the entry is refused."""
    case = _seed(datalayer, EM.PROPOSED)
    case.append_case_status(pxa=CS_pxa.Pxa)
    case.apply_embargo_register_step(
        [
            RegisterChange(
                embargo_id=EMBARGO_ID, trigger=RegisterTrigger.CANCEL
            )
        ],
        threat_signal=True,
    )
    datalayer.save(case)
    before = _case(datalayer).model_dump()

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.FAILURE
    assert _case(datalayer).model_dump() == before
