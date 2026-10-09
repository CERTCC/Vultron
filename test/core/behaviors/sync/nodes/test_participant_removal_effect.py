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
"""Tests for the replica replay of a participant removal (CM-31-007) and reinstatement (CM-31-011)."""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.participant_removal_effect import (
    REINSTATE_CASE_PARTICIPANT_EVENT_TYPE,
    REMOVE_CASE_PARTICIPANT_EVENT_TYPE,
    ApplyReinstateCaseParticipantFromLedgerNode,
    ApplyRemoveCaseParticipantFromLedgerNode,
    IsReinstateCaseParticipantEventNode,
    IsRemoveCaseParticipantEventNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

REMOVED_ACTOR_ID = "https://example.org/actors/removed"
REMOVE_ID = "https://example.org/activities/remove-1"
# The replica's own id for the record may differ from the one the CASE_MANAGER
# put in the snapshot; the apply node resolves it by actor.
REPLICA_PARTICIPANT_ID = f"{CASE_ID}/participants/removed-replica"
SNAPSHOT_PARTICIPANT_ID = f"{CASE_ID}/participants/removed"


def _entry(
    *,
    event_type: str = REMOVE_CASE_PARTICIPANT_EVENT_TYPE,
    participant: dict | None = None,
):
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=REMOVE_ID,
            event_type=event_type,
            payload_snapshot={
                "id": REMOVE_ID,
                "type": "Remove",
                "actor": OWNER_ACTOR_ID,
                "object": participant
                or {
                    "id": SNAPSHOT_PARTICIPANT_ID,
                    "type": "CaseParticipant",
                    "attributedTo": REMOVED_ACTOR_ID,
                },
                "target": CASE_ID,
            },
            prev_log_hash="0" * 64,
        )
    )


@pytest.fixture
def replica_record(datalayer) -> CaseParticipant:
    record = CaseParticipant(
        id_=REPLICA_PARTICIPANT_ID,
        attributed_to=REMOVED_ACTOR_ID,
        context=CASE_ID,
    )
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Removal replay", attributed_to=OWNER_ACTOR_ID
    )
    case.add_participant(record)
    datalayer.create(record)
    datalayer.save(case)
    return record


def _apply(bridge, case_actor, entry):
    return bridge.execute_with_setup(
        tree=ApplyRemoveCaseParticipantFromLedgerNode(name="ApplyRemoval"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )


@pytest.mark.spec("CM-31-007")
def test_records_the_removal_fact_on_the_replicas_own_record(
    bridge, datalayer, case_actor, replica_record
) -> None:
    result = _apply(bridge, case_actor, _entry())

    assert result.status == Status.SUCCESS
    record = datalayer.read(REPLICA_PARTICIPANT_ID)
    assert isinstance(record, CaseParticipant)
    assert record.removal_activity == REMOVE_ID
    case = datalayer.read(CASE_ID)
    assert REPLICA_PARTICIPANT_ID in [
        getattr(p, "id_", p) for p in case.case_participants
    ]


@pytest.mark.spec("CM-31-007")
@pytest.mark.spec("SYNC-12-003")
def test_replay_keeps_the_first_removal(
    bridge, datalayer, case_actor, replica_record
) -> None:
    replica_record.removal_activity = "https://example.org/activities/first"
    datalayer.save(replica_record)

    assert _apply(bridge, case_actor, _entry()).status == Status.SUCCESS

    record = datalayer.read(REPLICA_PARTICIPANT_ID)
    assert isinstance(record, CaseParticipant)
    assert record.removal_activity == "https://example.org/activities/first"


@pytest.mark.spec("CM-31-007")
def test_falls_back_to_the_snapshot_record_id_on_the_roster(
    bridge, datalayer, case_actor, replica_record
) -> None:
    """With no actor to resolve by, the record id the snapshot names is used."""
    entry = _entry(
        participant={"id": REPLICA_PARTICIPANT_ID, "type": "CaseParticipant"}
    )

    assert _apply(bridge, case_actor, entry).status == Status.SUCCESS

    record = datalayer.read(REPLICA_PARTICIPANT_ID)
    assert isinstance(record, CaseParticipant)
    assert record.removal_activity == REMOVE_ID


@pytest.mark.spec("SYNC-12-001")
def test_skips_a_replica_without_the_case(bridge, case_actor) -> None:
    assert _apply(bridge, case_actor, _entry()).status == Status.SUCCESS


@pytest.mark.spec("SYNC-12-001")
def test_skips_a_participant_the_replica_does_not_hold(
    bridge, datalayer, case_actor, replica_record
) -> None:
    entry = _entry(
        participant={
            "id": f"{CASE_ID}/participants/unknown",
            "type": "CaseParticipant",
            "attributedTo": "https://example.org/actors/unknown",
        }
    )

    assert _apply(bridge, case_actor, entry).status == Status.SUCCESS

    record = datalayer.read(REPLICA_PARTICIPANT_ID)
    assert isinstance(record, CaseParticipant)
    assert not record.removed


@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        (REMOVE_CASE_PARTICIPANT_EVENT_TYPE, Status.SUCCESS),
        ("remove_note_from_case", Status.FAILURE),
    ],
)
def test_condition_matches_only_the_removal_event(
    bridge, case_actor, event_type: str, expected: Status
) -> None:
    result = bridge.execute_with_setup(
        tree=IsRemoveCaseParticipantEventNode(name="IsRemoval"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(
            _entry(event_type=event_type), actor_id=case_actor.id_
        ),
    )

    assert result.status == expected


# ---------------------------------------------------------------------------
# Reinstatement replay (CM-31-011, RSH-08-004)
# ---------------------------------------------------------------------------


def _reinstate(bridge, case_actor, entry):
    return bridge.execute_with_setup(
        tree=ApplyReinstateCaseParticipantFromLedgerNode(
            name="ApplyReinstate"
        ),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=case_actor.id_),
    )


def _replica_record_state(datalayer) -> CaseParticipant:
    record = datalayer.read(REPLICA_PARTICIPANT_ID)
    assert isinstance(record, CaseParticipant)
    return record


@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("RSH-08-004")
def test_reinstatement_clears_the_removal_fact_on_the_replicas_record(
    bridge, datalayer, case_actor, replica_record
) -> None:
    replica_record.removal_activity = REMOVE_ID
    datalayer.save(replica_record)

    entry = _entry(event_type=REINSTATE_CASE_PARTICIPANT_EVENT_TYPE)
    assert _reinstate(bridge, case_actor, entry).status == Status.SUCCESS

    assert not _replica_record_state(datalayer).removed


@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("SYNC-12-003")
def test_reinstatement_of_a_record_that_is_not_removed_is_a_no_op(
    bridge, datalayer, case_actor, replica_record
) -> None:
    entry = _entry(event_type=REINSTATE_CASE_PARTICIPANT_EVENT_TYPE)

    assert _reinstate(bridge, case_actor, entry).status == Status.SUCCESS

    record = _replica_record_state(datalayer)
    assert not record.removed
    assert record == replica_record


@pytest.mark.spec("SYNC-12-001")
def test_reinstatement_skips_a_snapshot_with_no_participant(
    bridge, datalayer, case_actor, replica_record
) -> None:
    replica_record.removal_activity = REMOVE_ID
    datalayer.save(replica_record)
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=REMOVE_ID,
            event_type=REINSTATE_CASE_PARTICIPANT_EVENT_TYPE,
            payload_snapshot={
                "id": REMOVE_ID,
                "type": "Add",
                "actor": OWNER_ACTOR_ID,
                "target": CASE_ID,
            },
            prev_log_hash="0" * 64,
        )
    )

    assert _reinstate(bridge, case_actor, entry).status == Status.SUCCESS

    assert _replica_record_state(datalayer).removed


@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        (REINSTATE_CASE_PARTICIPANT_EVENT_TYPE, Status.SUCCESS),
        (REMOVE_CASE_PARTICIPANT_EVENT_TYPE, Status.FAILURE),
    ],
)
def test_condition_matches_only_the_reinstatement_event(
    bridge, case_actor, event_type: str, expected: Status
) -> None:
    result = bridge.execute_with_setup(
        tree=IsReinstateCaseParticipantEventNode(name="IsReinstatement"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(
            _entry(event_type=event_type), actor_id=case_actor.id_
        ),
    )

    assert result.status == expected
