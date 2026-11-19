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
requirement once.  These cover the edges around them: what the CASE_MANAGER
sends the removed actor, what a repeat removal leaves alone, what a removed
participant stops receiving, and what a replica does with the ``Announce``
and with the entry (ADR-0116, ADR-0199).
"""

import json
from typing import Any

import pytest
from py_trees.common import Status

from test.core.use_cases.received.actor.test_case_joining_replies import (
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
from test.support.ledger import with_genesis
from test.support.objects import authored_at
from test.support.received import peer_position
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_remove_case_participant_received_tree,
)
from vultron.core.behaviors.case.nodes.announce_admitted_act import (
    EmitAnnounceAdmittedActNode,
)
from vultron.core.behaviors.case.nodes.case_participant_received import (
    RecordParticipantRemovalNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case_participant import (
    RemoveParticipantFromCaseReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    announce_admitted_act_activity,
    reject_log_entry_activity,
    remove_participant_activity,
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


def _owner_removes(actor_id: str = VENDOR, *, by: str = OWNER) -> Any:
    return remove_participant_activity(
        actor_id,
        CASE_ID,
        actor=by,
        id_=_REMOVE_ACTIVITY_ID,
        to=[MANAGER],
        at=authored_at(),
    )


# ---------------------------------------------------------------------------
# At the CASE_MANAGER
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-31-005")
@pytest.mark.spec("CM-31-026")
@pytest.mark.spec("CM-24-001")
def test_the_removed_actor_is_announced_the_owners_act(
    removal: _RemovalCase,
) -> None:
    """The removed actor gets ``Announce(<the Owner's Remove>)`` (ADR-0199).

    The ``Announce`` is the CASE_MANAGER's own act, credits nobody else,
    carries the Owner's act inline and names it in ``inReplyTo`` too
    (ADR-0204); its id is derived from the act, and it is not ledgered.
    """
    removal.route(_owner_removes())

    (announce,) = removal.activities_to("Announce", VENDOR)
    assert _as_id(announce.actor) == MANAGER
    assert announce.attributed_to is None
    assert _as_id(announce.object_) == _REMOVE_ACTIVITY_ID
    assert _as_id(announce.in_reply_to) == _REMOVE_ACTIVITY_ID
    assert [_as_id(t) for t in announce.to] == [VENDOR]
    assert _as_id(announce.context) == CASE_ID
    assert announce.id_ == EmitAnnounceAdmittedActNode.announce_id(
        _REMOVE_ACTIVITY_ID
    )
    ledgered = {entry.log_object_id for entry in removal.ledger()}
    assert ledgered == {_REMOVE_ACTIVITY_ID}


@pytest.mark.spec("CM-31-025")
def test_the_case_manager_sends_no_accept_and_makes_no_act_of_its_own(
    removal: _RemovalCase,
) -> None:
    """The Owner's act is the one entry: no ``Accept``, no CASE_MANAGER
    ``Remove`` or ``Add`` of the actor (ADR-0199)."""
    removal.route(_owner_removes())

    for actor_id in (OWNER, VENDOR, OTHER):
        assert removal.activities_to("Accept", actor_id) == []
        assert removal.activities_to("Remove", actor_id) == []
        assert removal.activities_to("Add", actor_id) == []
    (entry,) = removal.ledger()
    assert entry.log_object_id == _REMOVE_ACTIVITY_ID


@pytest.mark.spec("CM-31-004")
def test_only_the_case_owner_may_send_the_removal() -> None:
    """The CASE_MANAGER admits a removal only from the Case Owner, and no
    other receiver acts on one (CM-31-004, HP-01-038)."""
    assert RemoveParticipantFromCaseReceivedUseCase.sender_entitlement == (
        SenderRule.at_case_manager_only(SenderEntitlementKind.CASE_OWNER)
    )


@pytest.mark.spec("CM-31-001")
def test_removal_fact_is_the_owners_activity_id(
    removal: _RemovalCase,
) -> None:
    removal.route(_owner_removes())

    assert removal.participant(VENDOR).removal_activity == (
        _REMOVE_ACTIVITY_ID
    )
    assert not removal.participant(OTHER).removed


@pytest.mark.spec("CM-31-022")
@pytest.mark.spec("CLP-13-001")
def test_second_removal_commits_nothing_and_sends_no_second_announce(
    removal: _RemovalCase,
) -> None:
    removal.remove(VENDOR)
    entries = len(removal.ledger())

    second = removal.remove(VENDOR)

    assert second.disposition is HandlerDisposition.SKIPPED
    assert len(removal.ledger()) == entries
    assert len(removal.activities_to("Announce", VENDOR)) == 1


@pytest.mark.spec("HP-01-014")
def test_a_redelivered_removal_changes_nothing(removal: _RemovalCase) -> None:
    """The same act delivered again is answered by the seen-before door."""
    removal.route(_owner_removes())
    entries = len(removal.ledger())

    again = removal.route(_owner_removes())

    assert again.disposition is HandlerDisposition.SKIPPED
    assert len(removal.ledger()) == entries
    assert len(removal.activities_to("Announce", VENDOR)) == 1


@pytest.mark.spec("CM-31-004")
def test_refused_removal_writes_nothing_but_the_archive(
    removal: _RemovalCase,
) -> None:
    """A non-owner's removal is archived (CLP-10-018) and changes nothing."""
    activity = _owner_removes(by=OTHER)

    result = removal.route(activity)

    assert result.disposition is HandlerDisposition.REFUSED
    assert not removal.participant(VENDOR).removed
    assert removal.ledger() == []
    assert removal.activities_to("Announce", VENDOR) == []
    assert removal.dl.read(ReceivedActivityRecord.build_id(activity.id_))


@pytest.mark.spec("CM-31-004")
@pytest.mark.spec("CLP-05-001")
@pytest.mark.parametrize("removed", [MANAGER, OWNER])
def test_a_refused_removal_is_answered_with_a_refusal_notice(
    removal: _RemovalCase, removed: str
) -> None:
    """A removal naming the CASE_MANAGER or the Owner is refused with a
    refusal notice to the Owner, and nothing is committed."""
    result = removal.route(_owner_removes(removed))

    assert result.disposition is HandlerDisposition.REFUSED
    (notice,) = removal.activities_to("Refuse", OWNER)
    assert _as_id(notice.in_reply_to) == _REMOVE_ACTIVITY_ID
    assert removal.ledger() == []
    assert removal.activities_to("Announce", removed) == []


@pytest.mark.spec("CM-31-028")
@pytest.mark.spec("CM-10-004")
def test_no_later_entry_reaches_the_removed_participant(
    removal: _RemovalCase,
) -> None:
    """After its removal entry, fan-out skips the removed participant."""
    removal.remove(VENDOR)
    to_vendor = len(removal.ledger_adds_to(VENDOR))

    removal.remove(OTHER)

    assert len(removal.ledger_adds_to(VENDOR)) == to_vendor
    assert removal.ledger_adds_to(OTHER)


@pytest.mark.spec("CM-31-028")
@pytest.mark.spec("CM-10-004")
def test_replay_does_not_answer_the_removed_participant(
    removal: _RemovalCase,
) -> None:
    """A removed participant's ``Reject(CaseLedgerEntry)`` gets no replay."""
    removal.remove(VENDOR)
    removal.remove(OTHER)
    first, _second = removal.ledger()
    to_vendor = len(removal.ledger_adds_to(VENDOR))

    result = removal.route(
        reject_log_entry_activity(
            first,
            ledger_position=peer_position(first.entry_hash),
            actor=VENDOR,
            to=[MANAGER],
            in_reply_to="https://example.org/activities/prompting-announce",
            at=authored_at(),
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert len(removal.ledger_adds_to(VENDOR)) == to_vendor


@pytest.mark.spec("OID-01-006")
@pytest.mark.spec("CM-31-007")
def test_removal_naming_the_actor_with_a_trailing_slash_is_applied(
    removal: _RemovalCase,
) -> None:
    """The named actor is read without its trailing slash, so a removal
    spelling the actor that way names its record."""
    result = removal.route(_owner_removes(VENDOR + "/"))

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert removal.participant(VENDOR).removed


class _AnnounceFailsAdapter(TriggerActivityAdapter):
    """A trigger-activity port whose announcement cannot be built."""

    def announce_admitted_act(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("outbox unavailable")


@pytest.mark.spec("BT-14-001")
@pytest.mark.spec("CLP-07-015")
def test_announce_failure_after_commit_is_an_internal_error(
    removal: _RemovalCase,
) -> None:
    """A failed announcement is our fault, never a refusal; it fails the act,
    which keeps no entry of the removal (CLP-07-015)."""
    with pytest.raises(VultronBTInternalError):
        route_received(
            removal.dl,
            _owner_removes(),
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(removal.dl),
            trigger_activity=_AnnounceFailsAdapter(removal.dl),
        )

    assert removal.ledger() == []


@pytest.mark.spec("CM-31-001")
def test_failed_fact_write_after_commit_is_an_internal_error(
    removal: _RemovalCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A removal fact that cannot be recorded is our fault, not the sender's."""
    monkeypatch.setattr(
        RecordParticipantRemovalNode, "update", lambda self: Status.FAILURE
    )

    with pytest.raises(VultronBTInternalError):
        removal.route(_owner_removes())

    # The fact and the removal's own entry are one act (CLP-07-015).
    assert removal.ledger() == []


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


@pytest.mark.spec("CM-31-029")
@pytest.mark.spec("RSH-08-003")
def test_replica_records_the_announce_and_writes_nothing(
    removal: _RemovalCase,
) -> None:
    removal.remove(VENDOR)
    (announce,) = removal.activities_to("Announce", VENDOR)
    replica = _vendor_replica()
    before = _replica_state(replica)

    result = _route_to_replica(replica, announce)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _replica_state(replica) == before
    assert replica.read(ReceivedActivityRecord.build_id(announce.id_))
    assert list(replica.list_objects("CaseLedgerEntry")) == []


@pytest.mark.spec("HP-01-014")
@pytest.mark.spec("ID-04-004")
def test_replica_skips_a_redelivered_announce(removal: _RemovalCase) -> None:
    """Only the Announce's first receipt is APPLIED; a repeat is a skip."""
    removal.remove(VENDOR)
    (announce,) = removal.activities_to("Announce", VENDOR)
    replica = _vendor_replica()
    _route_to_replica(replica, announce)
    before = _replica_state(replica)

    result = _route_to_replica(replica, announce)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _replica_state(replica) == before
    assert list(replica.list_objects("CaseLedgerEntry")) == []


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("PCR-03-001")
def test_replica_refuses_an_announce_not_from_the_case_manager() -> None:
    """Only the case's CASE_MANAGER announces an admitted act."""
    replica = _vendor_replica()
    before = _replica_state(replica)
    forged = announce_admitted_act_activity(
        _owner_removes(),
        CASE_ID,
        actor=OWNER,
        to=[VENDOR],
        at=authored_at(),
    )

    result = _route_to_replica(replica, forged)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _replica_state(replica) == before


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("HP-01-038")
def test_replica_refuses_the_owners_removal_itself() -> None:
    """The Owner sends its act to the CASE_MANAGER only; any other receiver
    refuses it at the path stage and writes nothing."""
    replica = _vendor_replica()
    before = _replica_state(replica)

    result = _route_to_replica(
        replica,
        remove_participant_activity(
            OTHER, CASE_ID, actor=OWNER, to=[VENDOR], at=authored_at()
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
    removal.route(_owner_removes())
    (announce,) = removal.ledger_adds_to(replica_actor)
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=replica_actor)
    _seed(replica)
    # The genesis hash is derived from the case's ``published``; a replica
    # seeded a clock tick later would not extend the manager's chain.
    seeded = replica.read(CASE_ID)
    assert isinstance(seeded, as_VulnerabilityCase)
    replica.save(with_genesis(seeded, removal.read_case().genesis_hash))

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
        sender_rule=RemoveParticipantFromCaseReceivedUseCase.sender_entitlement,
        case_id=CASE_ID,
        sender_id=OWNER,
    )
    (gate,) = [
        node
        for node in tree.iterate()
        if node.name == "GuardedRemoveParticipantBT"
    ]
    assert any(
        isinstance(node, RecordParticipantRemovalNode)
        for node in gate.iterate()
    )
