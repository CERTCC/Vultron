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
"""The Case Owner's reinstatement of a participant, and what follows it.

The goal tests in ``test_participant_removal_planned.py`` pin CM-31-011
through CM-31-013 once.  These cover the edges around them (ADR-0116, #4081,
#4084):

- ``Add(CaseParticipant)`` reinstates, and only reinstates: one ledger entry,
  a delegated notice, no new acceptance, and a refusal for anything else;
- the reinstated participant is backfilled from the first entry withheld
  after its removal entry, and its hash chain joins with no gap (CM-10-006);
- a reinstated participant that is not ``SIGNATORY`` to the active embargo is
  sent that embargo's Invite and no case content until it consents
  (CM-31-013);
- a removed participant is sent no Invite of any kind (CM-31-013);
- replicas apply a reinstatement from its ledger entry, and learn of a new
  member from the ``Accept(Invite)`` entry alone (CM-31-012).
"""

from itertools import pairwise
from typing import Any

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.actor.test_case_joining_replies import (
    route_received,
)
from test.core.use_cases.received.conftest import seed_inert_invitee
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
from test.support.embargo_register import terminate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.case.case_participant_received_tree import (
    create_add_case_participant_received_tree,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    ReinstateCaseParticipantReceivedNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    SuggestedActorIsNotRemovedNode,
)
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_accept_actor_recommendation_received_tree,
    create_recommend_actor_to_case_received_tree,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    InviteReinstatedParticipantToEmbargoNode,
    ReinviteStaleAccepterNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.rsvp_deadline import EMBARGO_REINVITE_EVENT_TYPE
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    em_accept_embargo_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ADD_ACTIVITY_ID = "https://example.org/activities/reinstate-vendor"
NEWBIE = "https://example.org/actors/newbie-removal"


@pytest.fixture
def case() -> _RemovalCase:
    """The CASE_MANAGER store the goal tests start from."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    return _RemovalCase(dl=dl, case=_seed(dl))


def _owner_reinstates(
    case: _RemovalCase, actor_id: str = VENDOR, *, by: str = OWNER
) -> Any:
    return add_participant_to_case_activity(
        case.participant(actor_id),
        target=CASE_ID,
        actor=by,
        id_=_ADD_ACTIVITY_ID,
    )


def _entry_ids_announced_to(case: _RemovalCase, actor_id: str) -> list[str]:
    """Ledger entries the manager announced to *actor_id*, in queue order."""
    return [
        entry_id
        for announce in case.activities_to("Announce", actor_id)
        if (entry_id := _as_id(getattr(announce, "object_", None)))
        and isinstance(case.dl.read(entry_id), CaseLedgerEntry)
    ]


def _entries_announced_to(
    case: _RemovalCase, actor_id: str
) -> list[CaseLedgerEntry]:
    """The entries announced to *actor_id*, in log order, each once."""
    entries = {
        entry.log_index: entry
        for entry_id in _entry_ids_announced_to(case, actor_id)
        if isinstance(entry := case.dl.read(entry_id), CaseLedgerEntry)
    }
    return [entries[index] for index in sorted(entries)]


def _replica(case: _RemovalCase, actor_id: str) -> SqliteDataLayer:
    """*actor_id*'s replica, seeded as the manager's store was.

    The genesis hash is derived from the case's ``published``; a replica
    seeded a clock tick later would not extend the manager's chain.
    """
    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    _seed(replica)
    seeded = replica.read(CASE_ID)
    assert isinstance(seeded, as_VulnerabilityCase)
    seeded.genesis_hash = case.read_case().genesis_hash
    replica.save(seeded)
    return replica


def _announce_to_replica(
    replica: SqliteDataLayer, case: _RemovalCase, actor_id: str
) -> None:
    """Deliver every ``Announce(CaseLedgerEntry)`` the manager sent *actor_id*."""
    for announce in case.activities_to("Announce", actor_id):
        if not isinstance(
            case.dl.read(_as_id(announce.object_) or ""), CaseLedgerEntry
        ):
            continue
        result = route_received(
            replica,
            announce,
            receiving_actor_id=actor_id,
            sync_port=SyncActivityAdapter(replica),
        )
        assert result.disposition in (
            HandlerDisposition.APPLIED,
            HandlerDisposition.SKIPPED,
        ), result.reason


# ---------------------------------------------------------------------------
# #4081 — Add(CaseParticipant) reinstates, and only reinstates
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CM-24-002")
def test_reinstatement_is_one_entry_and_a_delegated_notice(
    case: _RemovalCase,
) -> None:
    """The owner's ``Add`` is the one entry; the notice is the manager's."""
    case.remove(VENDOR)
    before = len(case.ledger())

    result = case.route(_owner_reinstates(case))

    assert result.disposition is HandlerDisposition.APPLIED
    added = case.ledger()[before:]
    assert [entry.log_object_id for entry in added] == [_ADD_ACTIVITY_ID]
    assert added[0].payload_snapshot.get("actor") == OWNER
    (notice,) = case.activities_to("Add", VENDOR)
    assert _as_id(notice.actor) == MANAGER
    assert notice.attributed_to == OWNER
    assert [_as_id(t) for t in notice.to] == [VENDOR]
    assert _as_id(notice.object_) == _participant_id(VENDOR)
    assert notice.id_ not in {e.log_object_id for e in case.ledger()}


@pytest.mark.spec("CM-31-011")
def test_reinstatement_asks_for_no_new_acceptance(
    case: _RemovalCase,
) -> None:
    """The record keeps its roster seat, statuses and consent rows."""
    case.remove(VENDOR)
    removed = case.participant(VENDOR)

    case.route(_owner_reinstates(case))

    record = case.participant(VENDOR)
    assert record.removal_activity is None
    assert record.joined
    assert record.embargo_consents == removed.embargo_consents
    assert record.participant_statuses == removed.participant_statuses
    assert case.activities_to("Invite", VENDOR) == []
    assert _participant_id(VENDOR) in case.active_ids()


@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("CM-31-004")
def test_add_from_a_non_owner_is_refused(case: _RemovalCase) -> None:
    case.remove(VENDOR)
    before = len(case.ledger())

    result = case.route(_owner_reinstates(case, by=OTHER))

    assert result.disposition is HandlerDisposition.REFUSED
    assert case.participant(VENDOR).removed
    assert len(case.ledger()) == before
    assert case.activities_to("Add", VENDOR) == []


@pytest.mark.spec("CM-31-011")
def test_add_naming_an_invitee_that_never_joined_is_refused(
    case: _RemovalCase,
) -> None:
    """``Add`` is not a way around accepting the stub Invite (ADR-0114)."""
    record = case.participant(OTHER).model_copy(
        update={"joined": False, "removal_activity": "urn:uuid:removal"}
    )
    case.dl.save(record)

    result = case.route(_owner_reinstates(case, OTHER))

    assert result.disposition is HandlerDisposition.REFUSED
    assert "never joined" in (result.reason or "")
    assert case.participant(OTHER).removed
    assert case.ledger() == []


@pytest.mark.spec("CM-31-011")
def test_refused_add_writes_nothing_but_the_archive(
    case: _RemovalCase,
) -> None:
    activity = _owner_reinstates(case, OTHER)

    result = case.route(activity)

    assert result.disposition is HandlerDisposition.REFUSED
    assert case.ledger() == []
    assert case.activities_to("Add", OTHER) == []
    assert case.dl.read(ReceivedActivityRecord.build_id(activity.id_))


@pytest.mark.spec("CM-31-011")
def test_add_naming_another_actor_than_the_record_is_refused(
    case: _RemovalCase,
) -> None:
    """The inline ``attributedTo`` must name the record's own actor."""
    case.remove(VENDOR)
    forged = case.participant(VENDOR).model_copy(
        update={"attributed_to": OTHER}
    )

    result = case.route(
        add_participant_to_case_activity(forged, target=CASE_ID, actor=OWNER)
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert case.participant(VENDOR).removed


class _NoticeFailsAdapter(TriggerActivityAdapter):
    """A trigger-activity port whose reinstatement notice cannot be built."""

    def add_participant_to_case(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("outbox unavailable")


@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("BT-14-001")
def test_notice_failure_after_commit_is_an_internal_error(
    case: _RemovalCase,
) -> None:
    case.remove(VENDOR)
    with pytest.raises(VultronBTInternalError):
        route_received(
            case.dl,
            _owner_reinstates(case),
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(case.dl),
            trigger_activity=_NoticeFailsAdapter(case.dl),
        )

    assert case.ledger()[-1].log_object_id == _ADD_ACTIVITY_ID


@pytest.mark.spec("CM-31-011")
def test_failed_fact_write_after_commit_is_an_internal_error(
    case: _RemovalCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case.remove(VENDOR)
    monkeypatch.setattr(
        ReinstateCaseParticipantReceivedNode,
        "update",
        lambda self: Status.FAILURE,
    )

    with pytest.raises(VultronBTInternalError):
        case.route(_owner_reinstates(case))


@pytest.mark.spec("RSH-08-003")
def test_every_write_in_the_received_tree_is_case_manager_gated() -> None:
    tree = create_add_case_participant_received_tree(
        participant_id=_participant_id(VENDOR),
        case_id=CASE_ID,
        sender_id=OWNER,
    )
    (gate,) = [
        node
        for node in tree.iterate()
        if node.name == "GuardedReinstateParticipantBT"
    ]
    assert any(
        isinstance(node, ReinstateCaseParticipantReceivedNode)
        for node in gate.iterate()
    )


# ---------------------------------------------------------------------------
# #4084 — backfill on reinstatement, and no Invite while removed
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-10-006")
@pytest.mark.spec("CM-31-011")
@pytest.mark.spec("SYNC-10-004")
def test_reinstated_participant_is_backfilled_with_a_gap_free_chain(
    case: _RemovalCase,
) -> None:
    """Every entry after the removal entry, in log order, chained to it."""
    case.remove(VENDOR)
    removal_entry = case.ledger()[-1]
    case.remove(OTHER)  # committed while the vendor's stream is paused
    assert _entries_announced_to(case, VENDOR)[-1] == removal_entry

    case.route(_owner_reinstates(case))

    ledger = sorted(case.ledger(), key=lambda e: e.log_index)
    after_removal = [
        e for e in ledger if e.log_index > removal_entry.log_index
    ]
    assert after_removal, "no entry was committed after the removal"
    sent = _entries_announced_to(case, VENDOR)
    backfilled = [e for e in sent if e.log_index > removal_entry.log_index]
    assert [e.entry_hash for e in backfilled] == [
        e.entry_hash for e in after_removal
    ]
    assert backfilled[-1].log_object_id == _ADD_ACTIVITY_ID
    chain = [removal_entry, *backfilled]
    for previous, entry in pairwise(chain):
        assert entry.log_index == previous.log_index + 1
        assert entry.prev_log_hash == previous.entry_hash


@pytest.mark.spec("CM-10-006")
@pytest.mark.spec("SYNC-10-004")
@pytest.mark.spec("CM-31-007")
@pytest.mark.spec("CM-31-011")
def test_reinstated_replica_applies_the_backfill_and_holds_a_full_chain(
    case: _RemovalCase,
) -> None:
    """The vendor's own replica takes the removal, then the catch-up.

    Delivered as sent, the entries apply in order with no forward gap, and
    the last one clears the removal fact on the vendor's own record.
    """
    case.remove(VENDOR)
    case.remove(OTHER)
    case.route(_owner_reinstates(case))
    replica = _replica(case, VENDOR)

    _announce_to_replica(replica, case, VENDOR)

    held = sorted(
        (
            e
            for e in replica.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ),
        key=lambda e: e.log_index,
    )
    assert [e.entry_hash for e in held] == [
        e.entry_hash for e in sorted(case.ledger(), key=lambda e: e.log_index)
    ]
    record = replica.read(_participant_id(VENDOR))
    assert isinstance(record, CaseParticipant)
    assert not record.removed
    other = replica.read(_participant_id(OTHER))
    assert isinstance(other, CaseParticipant)
    assert other.removed


@pytest.mark.spec("CM-31-007")
@pytest.mark.spec("RSH-08-004")
def test_bystander_replica_applies_the_reinstatement_from_its_entry(
    case: _RemovalCase,
) -> None:
    case.remove(VENDOR)
    case.route(_owner_reinstates(case))
    replica = _replica(case, OTHER)

    _announce_to_replica(replica, case, OTHER)

    record = replica.read(_participant_id(VENDOR))
    assert isinstance(record, CaseParticipant)
    assert not record.removed
    assert record.is_signatory(EMBARGO_ID)


@pytest.mark.spec("RSH-08-003")
def test_replica_stores_the_managers_notice_and_writes_nothing(
    case: _RemovalCase,
) -> None:
    case.remove(VENDOR)
    case.route(_owner_reinstates(case))
    (notice,) = case.activities_to("Add", VENDOR)
    replica = _replica(case, VENDOR)
    record = replica.read(_participant_id(VENDOR))
    assert isinstance(record, CaseParticipant)
    replica.save(record.model_copy(update={"removal_activity": "urn:x:rm"}))

    result = route_received(
        replica,
        notice,
        receiving_actor_id=VENDOR,
        sync_port=SyncActivityAdapter(replica),
    )

    assert result.disposition is HandlerDisposition.SKIPPED
    stored = replica.read(_participant_id(VENDOR))
    assert isinstance(stored, CaseParticipant)
    assert stored.removed, "the notice must not apply the reinstatement"


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("PCR-03-001")
def test_replica_refuses_an_add_not_from_the_case_manager(
    case: _RemovalCase,
) -> None:
    replica = _replica(case, VENDOR)
    record = replica.read(_participant_id(OTHER))
    assert isinstance(record, CaseParticipant)

    result = route_received(
        replica,
        add_participant_to_case_activity(
            record, target=CASE_ID, actor=OWNER, to=[VENDOR]
        ),
        receiving_actor_id=VENDOR,
        sync_port=SyncActivityAdapter(replica),
    )

    assert result.disposition is HandlerDisposition.REFUSED


def _make_other_a_non_signatory(case: _RemovalCase) -> None:
    """OTHER is joined but has not accepted the active embargo."""
    record = case.participant(OTHER)
    case.dl.save(
        record.model_copy(
            update={
                "embargo_consents": [
                    EmbargoConsent(
                        embargo_id=EMBARGO_ID,
                        state=EmbargoConsentState.DECLINED,
                    )
                ]
            }
        )
    )


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("CM-10-005")
def test_reinstated_non_signatory_gets_the_embargo_invite_and_no_content(
    case: _RemovalCase,
) -> None:
    _make_other_a_non_signatory(case)
    case.remove(OTHER)
    case.remove(VENDOR)
    announced = len(_entry_ids_announced_to(case, OTHER))

    result = case.route(_owner_reinstates(case, OTHER))

    assert result.disposition is HandlerDisposition.APPLIED
    assert not case.participant(OTHER).removed
    assert _participant_id(OTHER) not in case.active_ids()
    invites = [
        invite
        for invite in case.activities_to("Invite", OTHER)
        if _as_id(getattr(invite, "object_", None)) == EMBARGO_ID
    ]
    assert len(invites) == 1
    assert len(_entry_ids_announced_to(case, OTHER)) == announced
    assert EMBARGO_REINVITE_EVENT_TYPE in {e.event_type for e in case.ledger()}
    assert case.activities_to("Add", OTHER), "the notice still reaches it"


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("CM-10-006")
def test_reinstated_non_signatory_is_backfilled_once_it_consents(
    case: _RemovalCase,
) -> None:
    _make_other_a_non_signatory(case)
    case.remove(OTHER)
    removal_entry = case.ledger()[-1]
    case.remove(VENDOR)
    case.route(_owner_reinstates(case, OTHER))
    (invite,) = [
        invite
        for invite in case.activities_to("Invite", OTHER)
        if _as_id(getattr(invite, "object_", None)) == EMBARGO_ID
    ]

    result = case.route(
        em_accept_embargo_activity(
            invite, context=CASE_ID, actor=OTHER, to=[MANAGER]
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _participant_id(OTHER) in case.active_ids()
    ledger = sorted(case.ledger(), key=lambda e: e.log_index)
    sent = [
        e
        for e in _entries_announced_to(case, OTHER)
        if e.log_index > removal_entry.log_index
    ]
    assert [e.log_index for e in sent] == [
        e.log_index for e in ledger if e.log_index > removal_entry.log_index
    ]


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("EP-09-002")
def test_invitation_recipients_leave_out_a_removed_participant(
    case: _RemovalCase,
) -> None:
    case.remove(VENDOR)

    recipients = invitation_recipients(
        case.read_case(), case.dl, excluding={MANAGER}
    )

    assert OTHER in recipients
    assert VENDOR not in recipients


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("CM-11-010")
def test_a_removed_participant_replaying_its_accept_is_sent_nothing(
    case: _RemovalCase,
) -> None:
    """No full-case Invite, case seed or backfill reaches it (CLP-13-001)."""
    stub_invite = rm_invite_to_case_activity(
        VENDOR,
        target=CASE_ID,
        actor=MANAGER,
        to=[VENDOR],
        roles=[CVDRole.VENDOR],
        id_=f"{CASE_ID}/invitations/vendor",
    )
    case.dl.create(stub_invite)
    case.remove(VENDOR)
    entries = len(case.ledger())
    sent_before = len(case.activities_to("Invite", VENDOR))
    announced_before = len(case.activities_to("Announce", VENDOR))

    result = case.route(
        rm_accept_invite_to_case_activity(
            stub_invite, actor=VENDOR, to=[MANAGER]
        )
    )

    assert result.disposition is HandlerDisposition.SKIPPED
    assert len(case.ledger()) == entries
    assert len(case.activities_to("Invite", VENDOR)) == sent_before
    assert len(case.activities_to("Announce", VENDOR)) == announced_before


# ---------------------------------------------------------------------------
# #4081 AC-5 — replicas learn of a new member from the Accept(Invite) alone
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("CM-17-004")
def test_replicas_add_a_new_member_from_the_accept_entry_alone(
    case: _RemovalCase,
) -> None:
    """Per-actor stores: the manager's, and an existing participant's replica.

    The invitee's stub-Invite acceptance commits no ``add_case_participant``
    entry and enqueues no ``Add(CaseParticipant)``; the existing
    participant's replica seats the new member from the ``Accept(Invite)``
    entry it was sent.
    """
    case.dl.create(as_Organization(id_=NEWBIE))
    stub_invite = rm_invite_to_case_activity(
        NEWBIE,
        target=CASE_ID,
        actor=MANAGER,
        to=[NEWBIE],
        roles=[CVDRole.VENDOR],
        id_=f"{CASE_ID}/invitations/newbie",
    )
    case.dl.create(stub_invite)
    manager_case = case.read_case()
    seed_inert_invitee(case.dl, manager_case, NEWBIE)
    case.dl.save(manager_case)
    replica = _replica(case, OTHER)

    result = case.route(
        rm_accept_invite_to_case_activity(
            stub_invite, actor=NEWBIE, to=[MANAGER]
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert NEWBIE in case.read_case().actor_participant_index
    assert "add_case_participant" not in {e.event_type for e in case.ledger()}
    assert [
        add
        for add in case.dl.list_objects("Add")
        if _as_id(getattr(add, "actor", None)) == MANAGER
    ] == []

    _announce_to_replica(replica, case, OTHER)

    seated = replica.read(CASE_ID)
    assert isinstance(seated, as_VulnerabilityCase)
    assert NEWBIE in seated.actor_participant_index


# ---------------------------------------------------------------------------
# #4084 — who the reinstatement and re-invite Invites may reach (CM-31-013)
# ---------------------------------------------------------------------------


def _embargo_invites_to(case: _RemovalCase, actor_id: str) -> list[Any]:
    return [
        invite
        for invite in case.activities_to("Invite", actor_id)
        if _as_id(getattr(invite, "object_", None)) == EMBARGO_ID
    ]


def _run_as_manager(case: _RemovalCase, node: Any) -> Any:
    return BTTestScenario(actor_id=MANAGER, dl=case.dl).run(
        node, actor_id=MANAGER, case_id=CASE_ID
    )


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("CM-10-006")
def test_reinstatement_into_a_case_with_no_active_embargo_sends_no_invite(
    case: _RemovalCase,
) -> None:
    """No embargo binds it, so it is active at once and only backfilled."""
    _make_other_a_non_signatory(case)
    case.remove(OTHER)
    stored = case.read_case()
    terminate(stored)
    case.dl.save(stored)

    result = case.route(_owner_reinstates(case, OTHER))

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _participant_id(OTHER) in case.active_ids()
    assert _embargo_invites_to(case, OTHER) == []
    assert EMBARGO_REINVITE_EVENT_TYPE not in {
        e.event_type for e in case.ledger()
    }


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("CM-10-007")
def test_reinstated_participant_at_rm_closed_is_sent_no_embargo_invite() -> (
    None
):
    """An RM ``CLOSED`` participant is not an invitation recipient (EP-09-002)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    case = _RemovalCase(dl=dl, case=_seed(dl, vendor_rm=RM.CLOSED))
    record = case.participant(VENDOR)
    case.dl.save(
        record.model_copy(
            update={
                "embargo_consents": [
                    EmbargoConsent(
                        embargo_id=EMBARGO_ID,
                        state=EmbargoConsentState.DECLINED,
                    )
                ]
            }
        )
    )
    case.remove(VENDOR)

    result = case.route(_owner_reinstates(case))

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert not case.participant(VENDOR).removed
    assert _embargo_invites_to(case, VENDOR) == []


@pytest.mark.spec("CM-31-011")
def test_reinstatement_invite_fails_when_the_record_is_gone(
    case: _RemovalCase,
) -> None:
    """Regime 1: the guards just found the record, so its loss is a fault."""
    result = _run_as_manager(
        case,
        InviteReinstatedParticipantToEmbargoNode(
            case_id=CASE_ID,
            participant_id=f"{CASE_ID}/participants/nobody",
        ),
    )

    assert result.status == Status.FAILURE
    assert "names no actor" in (result.feedback_message or "")


@pytest.mark.spec("CM-31-013")
@pytest.mark.spec("EMB-17-003")
def test_stale_accepter_re_invite_skips_a_removed_participant(
    case: _RemovalCase,
) -> None:
    case.remove(VENDOR)

    result = _run_as_manager(
        case,
        ReinviteStaleAccepterNode(
            case_id=CASE_ID, embargo_id=EMBARGO_ID, invitee_id=VENDOR
        ),
    )

    assert result.status == Status.SUCCESS
    assert _embargo_invites_to(case, VENDOR) == []


@pytest.mark.spec("EMB-17-003")
def test_stale_accepter_re_invite_reaches_an_invitation_recipient(
    case: _RemovalCase,
) -> None:
    """Control: the same node sends the Invite to a participant that may get one."""
    result = _run_as_manager(
        case,
        ReinviteStaleAccepterNode(
            case_id=CASE_ID, embargo_id=EMBARGO_ID, invitee_id=OTHER
        ),
    )

    assert result.status == Status.SUCCESS
    assert len(_embargo_invites_to(case, OTHER)) == 1


@pytest.mark.spec("CM-31-013")
@pytest.mark.parametrize(
    ("removed", "expected"),
    [(True, Status.FAILURE), (False, Status.SUCCESS)],
)
def test_suggested_actor_guard_refuses_only_a_removed_participant(
    case: _RemovalCase, removed: bool, expected: Status
) -> None:
    if removed:
        case.remove(VENDOR)

    result = _run_as_manager(
        case,
        SuggestedActorIsNotRemovedNode(recommended_id=VENDOR, case_id=CASE_ID),
    )

    assert result.status == expected
    if removed:
        assert "CM-31-013" in (result.feedback_message or "")


@pytest.mark.spec("CM-31-013")
def test_suggested_actor_guard_admits_an_actor_the_case_does_not_list(
    case: _RemovalCase,
) -> None:
    result = _run_as_manager(
        case,
        SuggestedActorIsNotRemovedNode(recommended_id=NEWBIE, case_id=CASE_ID),
    )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CM-31-013")
@pytest.mark.parametrize(
    "factory",
    [
        create_recommend_actor_to_case_received_tree,
        create_accept_actor_recommendation_received_tree,
    ],
)
def test_suggest_actor_trees_guard_a_removed_actor_before_the_commit(
    factory: Any,
) -> None:
    """Both stub-Invite trees refuse a removed actor ahead of any commit."""
    kwargs: dict[str, Any] = {
        "recommendation_id": "https://example.org/activities/offer-1",
        "recommender_id": OWNER,
        "case_id": CASE_ID,
    }
    if factory is create_recommend_actor_to_case_received_tree:
        kwargs["recommended_id"] = VENDOR
    else:
        kwargs |= {"invitee_id": VENDOR, "sender_id": OWNER}
    names = [node.name for node in factory(**kwargs).children]

    # The Accept tree's guard also refuses a joined or closed actor
    # (CM-16-006), so it is a different composite from the recommend tree's.
    guard_name = (
        "SuggestedActorNotRemovedIfCaseManager"
        if factory is create_recommend_actor_to_case_received_tree
        else "AcceptedInviteeAdmittedIfCaseManager"
    )
    guard = names.index(guard_name)
    assert guard < names.index("GuardedCommitCaseLedgerEntryBT")
