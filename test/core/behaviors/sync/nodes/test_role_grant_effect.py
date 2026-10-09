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

"""Replay of ``accept_case_participant_role`` grants the role (#4404, CM-02-016).

An ``Offer(CaseParticipantRole)`` is a proposal; the CASE_MANAGER-committed
``accept_case_participant_role`` entry is the grant.  Every node applies it by
replaying the entry, so a participant learns a delegated role only from the
ledger (RSH-08-004, ADR-0039, ADR-0124).
"""

from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    ApplyCaseParticipantRoleGrantFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

MANAGER = OWNER_ACTOR_ID
TARGET = PARTICIPANT_ACTOR_ID


def _accept_snapshot(
    target: str = TARGET, role: str = CVDRole.COORDINATOR.value
) -> dict[str, Any]:
    """An ``Accept(Offer(CaseParticipantRole))`` payload snapshot (ADR-0039)."""
    return {
        "type": "Accept",
        "actor": target,
        "context": CASE_ID,
        "object": {
            "type": "Offer",
            "actor": MANAGER,
            "target": {"type": "Organization", "id": target},
            "context": CASE_ID,
            "object": {"type": "CaseParticipantRole", "role": role},
        },
    }


def _entry(snapshot: dict[str, Any]):
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/accept-role",
            event_type="accept_case_participant_role",
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )


def _seed_participant(
    datalayer, *, roles: list[CVDRole] | None = None
) -> None:
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    participant = CaseParticipant(
        id_=f"{CASE_ID}/participants/target",
        attributed_to=TARGET,
        context=CASE_ID,
        case_roles=roles or [],
    )
    case.add_participant(participant)
    datalayer.create(participant)
    datalayer.save(case)


def _target(datalayer) -> CaseParticipant:
    case = datalayer.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    pid = case.actor_participant_index[TARGET]
    p = datalayer.read(pid)
    assert isinstance(p, CaseParticipant)
    return p


def _apply_node(bridge, datalayer, snapshot: dict[str, Any]) -> Status:
    result = bridge.execute_with_setup(
        tree=ApplyCaseParticipantRoleGrantFromLedgerNode(
            name="ApplyRoleGrant"
        ),
        actor_id=datalayer.actor_id,
        activity=_make_event(_entry(snapshot), actor_id=MANAGER),
    )
    return cast(Status, result.status)


@pytest.mark.spec("CM-02-016")
def test_accept_grants_the_offered_role_to_the_target(bridge, datalayer):
    """The target participant gains the offered role from the ledger entry."""
    _seed_participant(datalayer, roles=[CVDRole.VENDOR])

    assert _apply_node(bridge, datalayer, _accept_snapshot()) == Status.SUCCESS

    target = _target(datalayer)
    assert target.has_role(CVDRole.COORDINATOR)
    assert target.has_role(CVDRole.VENDOR)  # pre-existing role untouched


@pytest.mark.spec("CM-02-016")
def test_redelivery_is_idempotent(bridge, datalayer):
    """A second delivery of the same grant adds no duplicate and still succeeds."""
    _seed_participant(datalayer)

    assert _apply_node(bridge, datalayer, _accept_snapshot()) == Status.SUCCESS
    assert _apply_node(bridge, datalayer, _accept_snapshot()) == Status.SUCCESS

    assert _target(datalayer).case_roles.count(CVDRole.COORDINATOR) == 1


@pytest.mark.spec("CM-02-016")
def test_missing_target_participant_is_a_non_fatal_skip(bridge, datalayer):
    """A replica that does not know the target writes nothing and does not fail."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    datalayer.save(case)  # no participant for TARGET on this replica

    assert _apply_node(bridge, datalayer, _accept_snapshot()) == Status.SUCCESS
    assert TARGET not in case.actor_participant_index


@pytest.mark.spec("CM-02-016")
def test_absent_case_replica_is_a_non_fatal_skip(bridge, datalayer):
    """With no case replica at all, the apply is a non-fatal skip (ADR-0087)."""
    assert _apply_node(bridge, datalayer, _accept_snapshot()) == Status.SUCCESS


@pytest.mark.spec("CM-02-016")
def test_a_different_role_is_granted_as_offered(bridge, datalayer):
    """The role granted is the one the offer names, not a fixed value."""
    _seed_participant(datalayer)

    snapshot = _accept_snapshot(role=CVDRole.COORDINATOR.value)
    assert _apply_node(bridge, datalayer, snapshot) == Status.SUCCESS
    assert _target(datalayer).has_role(CVDRole.COORDINATOR)
