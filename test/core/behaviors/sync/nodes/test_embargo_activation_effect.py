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
target=Case)``) and ``reject_embargo_proposal_on_case`` (its ``Reject``) are
replayed through ``EmbargoLifecycle`` in ``OBSERVED`` mode (EMB-18-001,
ADR-0122): the register activates or rejects the embargo and EM derives from
it.
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
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
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
        datalayer.save(participant)
        case.case_participants.append(participant.id_)
        case.actor_participant_index[OWNER_ACTOR_ID] = participant.id_
    datalayer.save(case)
    return case


def _apply(bridge, embargo: Any, *, accept: bool = True):
    """Replay the owner's Accept (or Reject) of *embargo* on the replica."""
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/owner-decision",
            event_type=(
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
    assert owner.consent_for(EMBARGO_ID) == EmbargoConsentState.ACCEPTED


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
    assert owner.consent_for(EMBARGO_ID) is None


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


@pytest.mark.spec("SYNC-12-001")
@pytest.mark.spec("EMB-18-003")
def test_a_rejection_naming_an_unreconstructable_embargo_fails(
    bridge, datalayer
):
    """A bare id the replica does not hold blocks persisting the entry."""
    _seed(datalayer, EM.PROPOSED)

    assert _apply(bridge, EMBARGO_ID, accept=False).status == Status.FAILURE
    assert _case(datalayer).em_state == EM.PROPOSED
