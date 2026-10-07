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
"""The Case Owner's removal of a participant, beyond the CM-31 goal tests.

The goal tests in ``test_participant_removal_planned.py`` pin each CM-31
requirement once.  These cover the edges around them: what the notice
carries, what a repeat removal leaves alone, what a removed participant
stops receiving, and what a replica does with each of the two channels a
removal arrives on (ADR-0116, #4080).
"""

import json
from typing import Any

import pytest
from py_trees.common import Status

from test.core.use_cases.received.actor.test_case_joining_planned import (
    route_received,
)
from test.core.use_cases.received.test_participant_removal_planned import (
    CASE_ID,
    EMBARGO_ID,
    MANAGER,
    OTHER,
    OWNER,
    VENDOR,
    _participant_id,
    _RemovalCase,
    _seed,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_remove_case_participant_received_tree,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    RemoveCaseParticipantFromCaseReceivedNode,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _CASE_AUTHORED_SIGNATURES,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    reject_log_entry_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_REMOVE_ACTIVITY_ID = "https://example.org/activities/remove-vendor"


@pytest.fixture
def removal() -> _RemovalCase:
    """The CASE_MANAGER store the goal tests start from."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    return _RemovalCase(dl=dl, case=_seed(dl))


def _owner_removes_vendor(case: _RemovalCase) -> Any:
    return remove_participant_from_case_activity(
        case.participant(VENDOR),
        target=CASE_ID,
        actor=OWNER,
        id_=_REMOVE_ACTIVITY_ID,
    )


# ---------------------------------------------------------------------------
# At the CASE_MANAGER
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-31-006")
@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CM-24-002")
def test_notice_is_delegated_names_the_participant_and_is_not_ledgered(
    removal: _RemovalCase,
) -> None:
    removal.route(_owner_removes_vendor(removal))

    (notice,) = removal.activities_to("Remove", VENDOR)
    assert _as_id(notice.actor) == MANAGER
    assert notice.attributed_to == OWNER
    assert [_as_id(t) for t in notice.to] == [VENDOR]
    assert _as_id(notice.object_) == _participant_id(VENDOR)
    assert _as_id(notice.target) == CASE_ID
    ledgered = {entry.log_object_id for entry in removal.ledger()}
    assert notice.id_ not in ledgered
    assert ledgered == {_REMOVE_ACTIVITY_ID}


@pytest.mark.spec("CM-31-005")
def test_removal_signature_is_not_case_authored() -> None:
    """The Case Owner authors the entry; the CASE_MANAGER only commits it."""
    assert ("Remove", "CaseParticipant") not in _CASE_AUTHORED_SIGNATURES


@pytest.mark.spec("CM-31-001")
def test_removal_fact_is_the_owners_activity_id(
    removal: _RemovalCase,
) -> None:
    removal.route(_owner_removes_vendor(removal))

    assert removal.participant(VENDOR).removal_activity == (
        _REMOVE_ACTIVITY_ID
    )
    assert not removal.participant(OTHER).removed


@pytest.mark.spec("CM-31-004")
@pytest.mark.spec("CLP-13-001")
def test_second_removal_commits_nothing_and_sends_no_second_notice(
    removal: _RemovalCase,
) -> None:
    removal.remove(VENDOR)
    entries = len(removal.ledger())

    second = removal.remove(VENDOR)

    assert second.disposition is HandlerDisposition.SKIPPED
    assert len(removal.ledger()) == entries
    assert len(removal.activities_to("Remove", VENDOR)) == 1


@pytest.mark.spec("CM-31-004")
def test_refused_removal_writes_nothing_but_the_archive(
    removal: _RemovalCase,
) -> None:
    """A non-owner's removal is archived (CLP-10-018) and changes nothing."""
    activity = remove_participant_from_case_activity(
        removal.participant(VENDOR), target=CASE_ID, actor=OTHER
    )

    result = removal.route(activity)

    assert result.disposition is HandlerDisposition.REFUSED
    assert not removal.participant(VENDOR).removed
    assert removal.ledger() == []
    assert removal.activities_to("Remove", VENDOR) == []
    assert removal.dl.read(ReceivedActivityRecord.build_id(activity.id_))


@pytest.mark.spec("CM-31-006")
@pytest.mark.spec("CM-10-004")
def test_no_later_entry_reaches_the_removed_participant(
    removal: _RemovalCase,
) -> None:
    """After its removal entry, fan-out skips the removed participant."""
    removal.remove(VENDOR)
    to_vendor = len(removal.activities_to("Announce", VENDOR))

    removal.remove(OTHER)

    assert len(removal.activities_to("Announce", VENDOR)) == to_vendor
    assert removal.activities_to("Announce", OTHER)


@pytest.mark.spec("CM-31-006")
@pytest.mark.spec("CM-10-004")
def test_replay_does_not_answer_the_removed_participant(
    removal: _RemovalCase,
) -> None:
    """A removed participant's ``Reject(CaseLedgerEntry)`` gets no replay."""
    removal.remove(VENDOR)
    removal.remove(OTHER)
    first, _second = removal.ledger()
    to_vendor = len(removal.activities_to("Announce", VENDOR))

    result = removal.route(
        reject_log_entry_activity(
            first, context=first.entry_hash, actor=VENDOR, to=[MANAGER]
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert len(removal.activities_to("Announce", VENDOR)) == to_vendor


@pytest.mark.spec("CM-31-004")
@pytest.mark.spec("CM-31-007")
def test_removal_naming_another_actor_than_the_record_is_refused(
    removal: _RemovalCase,
) -> None:
    """The inline ``attributedTo`` must name the record's own actor.

    A replica resolves its copy of the record by that actor, so a mismatch
    would remove a different participant there — here the CASE_MANAGER —
    than the one judged at the CASE_MANAGER.
    """
    forged = removal.participant(VENDOR).model_copy(
        update={"attributed_to": MANAGER}
    )
    activity = remove_participant_from_case_activity(
        forged, target=CASE_ID, actor=OWNER
    )

    result = removal.route(activity)

    assert result.disposition is HandlerDisposition.REFUSED
    assert not removal.participant(VENDOR).removed
    manager_record = removal.dl.read(
        removal.read_case().actor_participant_index[MANAGER]
    )
    assert isinstance(manager_record, CaseParticipant)
    assert not manager_record.removed
    assert removal.ledger() == []


class _NoticeFailsAdapter(TriggerActivityAdapter):
    """A trigger-activity port whose removal notice cannot be built."""

    def remove_participant_from_case(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("outbox unavailable")


@pytest.mark.spec("CM-31-006")
@pytest.mark.spec("BT-14-001")
def test_notice_failure_after_commit_is_an_internal_error(
    removal: _RemovalCase,
) -> None:
    """The entry is committed, so a failed notice is never a refusal."""
    with pytest.raises(VultronBTInternalError):
        route_received(
            removal.dl,
            _owner_removes_vendor(removal),
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(removal.dl),
            trigger_activity=_NoticeFailsAdapter(removal.dl),
        )

    assert [entry.log_object_id for entry in removal.ledger()] == [
        _REMOVE_ACTIVITY_ID
    ]


@pytest.mark.spec("CM-31-001")
def test_failed_fact_write_after_commit_is_an_internal_error(
    removal: _RemovalCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A removal fact that cannot be recorded is our fault, not the sender's."""
    monkeypatch.setattr(
        RemoveCaseParticipantFromCaseReceivedNode,
        "update",
        lambda self: Status.FAILURE,
    )

    with pytest.raises(VultronBTInternalError):
        removal.route(_owner_removes_vendor(removal))

    assert len(removal.ledger()) == 1


@pytest.mark.spec("CM-24-006")
def test_removal_on_a_case_without_a_case_manager_is_refused() -> None:
    """With no CASE_MANAGER on the roster, nobody may apply the removal."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    _seed(dl)
    case = dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    manager_record = case.actor_participant_index[MANAGER]
    case.case_participants = [
        p for p in case.case_participants if _as_id(p) != manager_record
    ]
    case.actor_participant_index = {
        actor: record
        for actor, record in case.actor_participant_index.items()
        if actor != MANAGER
    }
    dl.save(case)
    record = dl.read(_participant_id(OTHER))
    assert isinstance(record, CaseParticipant)

    result = route_received(
        dl,
        remove_participant_from_case_activity(
            record, target=CASE_ID, actor=OWNER
        ),
        receiving_actor_id=VENDOR,
        sync_port=SyncActivityAdapter(dl),
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "no CASE_MANAGER" in (result.reason or "")
    stored = dl.read(_participant_id(OTHER))
    assert isinstance(stored, CaseParticipant)
    assert not stored.removed


# ---------------------------------------------------------------------------
# At a replica
# ---------------------------------------------------------------------------


def _vendor_replica() -> SqliteDataLayer:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    _seed(dl)
    return dl


def _route_to_replica(dl: SqliteDataLayer, activity: Any) -> Any:
    return route_received(
        dl,
        activity,
        receiving_actor_id=VENDOR,
        sync_port=SyncActivityAdapter(dl),
    )


def _replica_state(dl: SqliteDataLayer) -> tuple[str, str]:
    case = dl.read(CASE_ID)
    record = dl.read(_participant_id(VENDOR))
    assert isinstance(case, as_VulnerabilityCase)
    assert isinstance(record, CaseParticipant)
    return (
        json.dumps(case.model_dump(mode="json"), sort_keys=True),
        json.dumps(record.model_dump(mode="json"), sort_keys=True),
    )


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("CM-31-007")
def test_replica_stores_the_managers_notice_and_writes_nothing(
    removal: _RemovalCase,
) -> None:
    removal.remove(VENDOR)
    (notice,) = removal.activities_to("Remove", VENDOR)
    replica = _vendor_replica()
    before = _replica_state(replica)

    result = _route_to_replica(replica, notice)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _replica_state(replica) == before
    assert replica.read(ReceivedActivityRecord.build_id(notice.id_))
    assert list(replica.list_objects("CaseLedgerEntry")) == []


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("PCR-03-001")
def test_replica_refuses_a_removal_not_from_the_case_manager() -> None:
    replica = _vendor_replica()
    record = replica.read(_participant_id(OTHER))
    assert isinstance(record, CaseParticipant)
    before = _replica_state(replica)

    result = _route_to_replica(
        replica,
        remove_participant_from_case_activity(
            record, target=CASE_ID, actor=OWNER, to=[VENDOR]
        ),
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _replica_state(replica) == before


@pytest.mark.spec("CM-31-007")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.parametrize("replica_actor", [VENDOR, OTHER])
def test_replica_applies_the_removal_from_its_ledger_entry(
    removal: _RemovalCase, replica_actor: str
) -> None:
    """Both the removed party and a bystander replay the entry they were sent.

    The removed participant's replica applies its own removal, the same
    fact the CASE_MANAGER recorded; its consent rows stay (CM-31-008).
    """
    removal.route(_owner_removes_vendor(removal))
    (announce,) = removal.activities_to("Announce", replica_actor)
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=replica_actor)
    _seed(replica)
    # The genesis hash is derived from the case's ``published``; a replica
    # seeded a clock tick later would not extend the manager's chain.
    seeded = replica.read(CASE_ID)
    assert isinstance(seeded, as_VulnerabilityCase)
    seeded.genesis_hash = removal.read_case().genesis_hash
    replica.save(seeded)

    result = route_received(
        replica,
        announce,
        receiving_actor_id=replica_actor,
        sync_port=SyncActivityAdapter(replica),
    )

    assert result.disposition is HandlerDisposition.APPLIED
    record = replica.read(_participant_id(VENDOR))
    assert isinstance(record, CaseParticipant)
    assert record.removal_activity == _REMOVE_ACTIVITY_ID
    assert record.is_signatory(EMBARGO_ID)
    case = replica.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    assert case.actor_participant_index[VENDOR] == _participant_id(VENDOR)


@pytest.mark.spec("RSH-08-003")
def test_every_write_in_the_received_tree_is_case_manager_gated() -> None:
    """Structurally: the effect node sits under the CASE_MANAGER gate."""
    tree = create_remove_case_participant_received_tree(
        participant_id=_participant_id(VENDOR),
        case_id=CASE_ID,
        sender_id=OWNER,
        removal_activity_id=_REMOVE_ACTIVITY_ID,
    )
    (gate,) = [
        node
        for node in tree.iterate()
        if node.name == "GuardedRemoveParticipantBT"
    ]
    assert any(
        isinstance(node, RemoveCaseParticipantFromCaseReceivedNode)
        for node in gate.iterate()
    )
