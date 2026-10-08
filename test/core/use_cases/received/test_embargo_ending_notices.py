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
"""Embargo-ending notices to bound signatories the ledger no longer reaches.

CM-31-009: when the active embargo is terminated or replaced by a revision
that ends no later, the CASE_MANAGER sends each ``SIGNATORY`` it no longer
fans the ledger out to — removed (CM-31-001), or at RM ``CLOSED``
(CM-23-004) — a direct notice, outside the ledger stream.  CM-31-010: that
participant's paused replica applies the notice when the CASE_MANAGER sent
it, and ignores it from anyone else; replaying the ledger entry later
changes nothing.

The CASE_MANAGER's store holds the manager, a Case Owner, and five vendors:

- ``REMOVED`` — signatory, removed by the owner in the test;
- ``DEPARTED`` — signatory at RM ``CLOSED`` (it left, CM-23);
- ``ACTIVE`` — signatory, still reached by the ledger;
- ``DECLINER`` — joined, declined the embargo;
- ``INVITEE`` — accepted the embargo but never joined the case.
"""

from collections.abc import Callable
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.use_cases.received.actor.test_case_joining_planned import (
    route_received,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from test.support import embargo_register
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.ending_notice import (
    EmbargoEndingKind,
    embargo_ending_notice,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.behaviors.sync.nodes.participant_removal_effect import (
    REINSTATE_CASE_PARTICIPANT_EVENT_TYPE,
)
from vultron.core.models._helpers import _as_id, days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.models.participant_status import (
    ParticipantStatus,
    RmDimension,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.participants.recipients import (
    awaits_embargo_ending_notice,
    embargo_ending_notice_recipients,
    ledger_stream_paused,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    add_participant_to_case_activity,
    announce_embargo_activity,
    announce_log_entry_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Service,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/case-ending-notice"
MANAGER = "https://example.org/actors/case-actor-ending"
OWNER = "https://example.org/actors/owner-ending"
REMOVED = "https://example.org/actors/removed-ending"
DEPARTED = "https://example.org/actors/departed-ending"
ACTIVE = "https://example.org/actors/active-ending"
DECLINER = "https://example.org/actors/decliner-ending"
INVITEE = "https://example.org/actors/invitee-ending"
EMBARGO_ID = f"{CASE_ID}/embargo_events/active"
REVISION_ID = f"{CASE_ID}/embargo_events/revision"

_VENDORS = (REMOVED, DEPARTED, ACTIVE, DECLINER, INVITEE)


def _participant_id(actor_id: str) -> str:
    return f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}"


def _record(actor_id: str, roles: list[CVDRole]) -> CaseParticipant:
    consent = (
        EmbargoConsentState.DECLINED
        if actor_id == DECLINER
        else EmbargoConsentState.AGREED
    )
    record = CaseParticipant(
        id_=_participant_id(actor_id),
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=roles,
        joined=actor_id != INVITEE,
        embargo_consents=[
            EmbargoConsent(embargo_id=EMBARGO_ID, state=consent)
        ],
    )
    if actor_id != DEPARTED:
        return record
    closed = ParticipantStatus(
        context=CASE_ID,
        attributed_to=actor_id,
        rm=RmDimension(state=RM.CLOSED),
        cvd_role=roles,
    )
    return record.model_copy(update={"participant_statuses": [closed]})


def _seed(dl: SqliteDataLayer, *, end_in_days: int = 60) -> None:
    """Seed *dl* with the case, its roster and its active embargo."""
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="CASE-ENDING-NOTICE", attributed_to=OWNER
    )
    dl.create(as_Service(id_=MANAGER, context=CASE_ID))
    for actor_id in (OWNER, *_VENDORS):
        dl.create(as_Organization(id_=actor_id))
    seed_case_manager_participant(dl, case, MANAGER)
    for actor_id in (OWNER, *_VENDORS):
        roles = [CVDRole.VENDOR]
        if actor_id == OWNER:
            roles = [CVDRole.CASE_OWNER, CVDRole.VENDOR]
        record = _record(actor_id, roles)
        dl.create(record)
        case.case_participants.append(record.id_)
        case.actor_participant_index[actor_id] = record.id_
    dl.create(
        as_EmbargoEvent(
            id_=EMBARGO_ID,
            context=CASE_ID,
            end_time=days_from_now_utc(end_in_days),
        )
    )
    embargo_register.activate(case, EMBARGO_ID)
    dl.create(case)
    # A proposal writes an UNINVITED row for every participant (ADR-0122); the
    # register helper above only touches the case, so backfill the rows here.
    embargo_register.write_consent_rows(dl, case)


def _embargo(dl: SqliteDataLayer, embargo_id: str = EMBARGO_ID) -> Any:
    embargo = dl.read(embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    return embargo


class _Manager:
    """The CASE_MANAGER's store, after the owner removed ``REMOVED``."""

    def __init__(self, *, end_in_days: int = 60) -> None:
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
        _seed(self.dl, end_in_days=end_in_days)
        record = self.dl.read(_participant_id(REMOVED))
        assert isinstance(record, CaseParticipant)
        removal = self.route(
            remove_participant_from_case_activity(
                record, target=CASE_ID, actor=OWNER
            )
        )
        assert removal.disposition is HandlerDisposition.APPLIED

    def route(self, activity: Any) -> HandlerResult:
        return route_received(
            self.dl,
            activity,
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(self.dl),
            trigger_activity=TriggerActivityAdapter(self.dl),
        )

    def notices(self, type_: str, embargo_id: str) -> dict[str, list[Any]]:
        """The manager's *type_* activities naming *embargo_id*, by recipient."""
        found: dict[str, list[Any]] = {}
        for obj in self.dl.list_objects(type_):
            if _as_id(getattr(obj, "actor", None)) != MANAGER:
                continue
            if _as_id(getattr(obj, "object_", None)) != embargo_id:
                continue
            for recipient in getattr(obj, "to", None) or []:
                found.setdefault(cast(str, _as_id(recipient)), []).append(obj)
        return found

    def ledger_object_ids(self) -> set[str]:
        return {
            entry.log_object_id
            for entry in self.dl.list_objects("CaseLedgerEntry")
            if isinstance(entry, CaseLedgerEntry) and entry.case_id == CASE_ID
        }

    def terminate_as_owner(self) -> None:
        result = self.route(
            remove_embargo_from_case_activity(
                _embargo(self.dl), origin=CASE_ID, actor=OWNER, to=[MANAGER]
            )
        )
        assert result.disposition is HandlerDisposition.APPLIED

    def stage_revision(self, *, end_in_days: int) -> Any:
        revision = as_EmbargoEvent(
            id_=REVISION_ID,
            context=CASE_ID,
            end_time=days_from_now_utc(end_in_days),
        )
        self.dl.create(revision)
        case = self.dl.read(CASE_ID)
        assert isinstance(case, as_VulnerabilityCase)
        embargo_register.propose(case, REVISION_ID)
        self.dl.save(case)
        embargo_register.write_consent_rows(self.dl, case)
        return revision


def _unreached_signatories() -> set[str]:
    return {REMOVED, DEPARTED}


# ---------------------------------------------------------------------------
# AC-1, AC-3: termination
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CM-24-002")
def test_owner_termination_sends_et_to_each_unreached_signatory() -> None:
    """Removed and departed signatories each get one ET, crediting the owner."""
    manager = _Manager()
    before = manager.ledger_object_ids()

    manager.terminate_as_owner()

    notices = manager.notices("Remove", EMBARGO_ID)
    assert set(notices) == _unreached_signatories()
    for recipient in _unreached_signatories():
        assert len(notices[recipient]) == 1
        notice = notices[recipient][0]
        # One recipient per notice: no notice names another participant.
        assert [_as_id(t) for t in notice.to] == [recipient]
        assert _as_id(notice.attributed_to) == OWNER
        # Delivery, not a record: the notice is never ledgered.
        assert notice.id_ not in manager.ledger_object_ids()
        assert notice.id_ in manager.dl.outbox_list()
    # The termination itself is the one new entry.
    assert len(manager.ledger_object_ids() - before) == 1


@pytest.mark.spec("CM-31-009")
def test_termination_notifies_nobody_who_is_not_bound_or_is_reached() -> None:
    """AC-3: a decliner, a never-joined invitee and an active one get no ET."""
    manager = _Manager()

    manager.terminate_as_owner()

    notices = manager.notices("Remove", EMBARGO_ID)
    assert DECLINER not in notices
    assert INVITEE not in notices
    assert ACTIVE not in notices
    assert OWNER not in notices


@pytest.mark.spec("EMB-19-001")
@pytest.mark.spec("CM-23-004")
def test_teardown_announce_reaches_active_participants_but_not_closed_ones() -> (
    None
):
    """The teardown's Announce goes to the active others, never to RM CLOSED.

    The closed signatory learns of the end from its CM-31-009 ET instead;
    a removed one is not active and gets neither the announcement.
    """
    manager = _Manager()

    manager.terminate_as_owner()

    announced = manager.notices("Announce", EMBARGO_ID)
    assert set(announced) == {OWNER, ACTIVE, DECLINER}
    assert DEPARTED not in announced
    assert REMOVED not in announced
    assert MANAGER not in announced
    assert set(manager.notices("Remove", EMBARGO_ID)) == (
        _unreached_signatories()
    )


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("CM-24-002")
@pytest.mark.spec("EMB-04-002")
def test_owner_ej_after_disclosure_sends_et_crediting_the_owner() -> None:
    """The owner's EJ of a revision after P/X/A ends the embargo (EMB-04-002).

    That path runs the shared terminate tree from a received ``Reject``;
    the unreached signatories get the ET, credited to the owner.
    """
    manager = _Manager()
    revision = manager.stage_revision(end_in_days=30)
    case = manager.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    manager.dl.save(case)
    invite = em_propose_embargo_activity(
        revision,
        context=CASE_ID,
        actor=MANAGER,
        to=[OWNER],
        id_=f"{CASE_ID}/embargo_invites/owner-revision-ej",
    )
    manager.dl.create(invite)

    result = manager.route(
        em_reject_embargo_activity(
            invite, context=CASE_ID, actor=OWNER, to=[MANAGER]
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED
    ended = manager.dl.read(CASE_ID)
    assert isinstance(ended, as_VulnerabilityCase)
    assert ended.active_embargo_id is None
    notices = {
        recipient: [a for a in sent if len(a.to) == 1]
        for recipient, sent in manager.notices("Remove", EMBARGO_ID).items()
    }
    for recipient in _unreached_signatories():
        assert len(notices[recipient]) == 1
        notice = notices[recipient][0]
        assert _as_id(notice.attributed_to) == OWNER
        assert notice.id_ not in manager.ledger_object_ids()
    for recipient in (DECLINER, INVITEE, ACTIVE):
        assert not notices.get(recipient)


def _cascade_terminate(manager: _Manager) -> None:
    """Run the shared terminate tree as the P/X/A cascade does."""
    sync_port = SyncActivityAdapter(manager.dl)
    result = BTBridge(
        datalayer=manager.dl,
        trigger_activity=TriggerActivityAdapter(manager.dl),
        sync_port=sync_port,
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(
        tree=terminate_embargo_bt(
            case_id=CASE_ID,
            result_out={},
            reason=TerminationReason.THREAT_SIGNAL,
        ),
        actor_id=MANAGER,
        sync_port=sync_port,
    )
    assert result.status == Status.SUCCESS, result.feedback_message


def _trigger_terminate(manager: _Manager) -> None:
    """The CASE_MANAGER terminates the embargo through its trigger."""
    SvcTerminateEmbargoUseCase(
        manager.dl,
        TerminateEmbargoTriggerRequest(actor_id=MANAGER, case_id=CASE_ID),
        trigger_activity=TriggerActivityAdapter(manager.dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(manager.dl),
    ).execute()


@pytest.mark.spec("CM-31-009")
@pytest.mark.parametrize(
    "terminate",
    [
        pytest.param(_cascade_terminate, id="pxa-cascade"),
        pytest.param(_trigger_terminate, id="trigger"),
    ],
)
def test_case_manager_termination_sends_et_without_attribution(
    terminate: Callable[[_Manager], None],
) -> None:
    """The shared terminate tree (P/X/A cascade, trigger) sends the ET too.

    The CASE_MANAGER decides the end itself here, so it credits nobody else.
    Its committed ``Remove`` goes to the active participants as well; the
    notice is the one addressed to a single unreached signatory.
    """
    manager = _Manager()

    terminate(manager)

    case = manager.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    assert case.active_embargo_id is None
    notices = {
        recipient: [a for a in sent if len(a.to) == 1]
        for recipient, sent in manager.notices("Remove", EMBARGO_ID).items()
    }
    for recipient in _unreached_signatories():
        assert len(notices[recipient]) == 1
        notice = notices[recipient][0]
        assert getattr(notice, "attributed_to", None) is None
        assert notice.id_ not in manager.ledger_object_ids()
    for recipient in (DECLINER, INVITEE, ACTIVE):
        assert not notices.get(recipient)


@pytest.mark.spec("CM-31-009")
def test_termination_on_or_after_the_agreed_end_is_expiry_and_sends_nothing() -> (
    None
):
    """Expiry on the agreed date owes no notice: the signatory knows it."""
    manager = _Manager(end_in_days=-1)

    manager.terminate_as_owner()

    assert manager.notices("Remove", EMBARGO_ID) == {}


# ---------------------------------------------------------------------------
# AC-2: revisions
# ---------------------------------------------------------------------------


def _activate_by_add(manager: _Manager, revision: Any) -> None:
    result = manager.route(
        add_embargo_to_case_activity(
            revision, target=CASE_ID, actor=OWNER, to=[MANAGER]
        )
    )
    assert result.disposition is HandlerDisposition.APPLIED


def _activate_by_owner_accept(manager: _Manager, revision: Any) -> None:
    invite = em_propose_embargo_activity(
        revision,
        context=CASE_ID,
        actor=MANAGER,
        to=[OWNER],
        id_=f"{CASE_ID}/embargo_invites/owner-revision",
    )
    manager.dl.create(invite)
    result = manager.route(
        em_accept_embargo_activity(
            invite, context=CASE_ID, actor=OWNER, to=[MANAGER]
        )
    )
    assert result.disposition is HandlerDisposition.APPLIED


_ACTIVATIONS = [
    pytest.param(_activate_by_add, id="add-embargo-event"),
    pytest.param(_activate_by_owner_accept, id="owner-accepts-revision"),
]


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("EP-05-001")
@pytest.mark.parametrize("activate", _ACTIVATIONS)
def test_shorter_revision_is_announced_to_each_unreached_signatory(
    activate: Callable[[_Manager, Any], None],
) -> None:
    """A revision ending sooner sends ``Announce(EmbargoEvent)`` with it."""
    manager = _Manager()
    revision = manager.stage_revision(end_in_days=30)

    activate(manager, revision)

    case = manager.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    assert case.active_embargo_id == REVISION_ID
    notices = manager.notices("Announce", REVISION_ID)
    assert set(notices) == _unreached_signatories()
    for recipient, sent in notices.items():
        assert len(sent) == 1
        assert [_as_id(t) for t in sent[0].to] == [recipient]
        assert _as_id(sent[0].attributed_to) == OWNER
        assert sent[0].id_ not in manager.ledger_object_ids()


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("EP-05-001")
@pytest.mark.parametrize("activate", _ACTIVATIONS)
def test_longer_revision_sends_nothing(
    activate: Callable[[_Manager, Any], None],
) -> None:
    """A revision ending later binds nobody who did not agree: no notice."""
    manager = _Manager()
    revision = manager.stage_revision(end_in_days=90)

    activate(manager, revision)

    assert manager.notices("Announce", REVISION_ID) == {}
    assert manager.notices("Remove", EMBARGO_ID) == {}


@pytest.mark.spec("CM-31-009")
def test_embargo_ending_notice_decision() -> None:
    """The one decision every path shares: terminated, shortened, or nothing."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    # One clock read per distinct end: two reads either side of a second
    # boundary would make the tie a one-second difference.
    later, sooner = days_from_now_utc(60), days_from_now_utc(30)
    for embargo_id, end_time in (
        ("a", later),
        ("same", later),
        ("short", sooner),
    ):
        dl.create(
            as_EmbargoEvent(
                id_=f"{CASE_ID}/e/{embargo_id}",
                context=CASE_ID,
                end_time=end_time,
            )
        )
    a, same, short = (f"{CASE_ID}/e/{i}" for i in ("a", "same", "short"))

    assert embargo_ending_notice(dl, before=None, after=a) is None
    assert embargo_ending_notice(dl, before=a, after=a) is None
    terminated = embargo_ending_notice(dl, before=a, after=None)
    assert terminated is not None
    assert terminated.kind is EmbargoEndingKind.TERMINATED
    assert terminated.notice_embargo_id == a
    shortened = embargo_ending_notice(dl, before=a, after=short)
    assert shortened is not None
    assert shortened.kind is EmbargoEndingKind.SHORTENED
    assert (shortened.ended_embargo_id, shortened.notice_embargo_id) == (
        a,
        short,
    )
    # Equal terms are contained: the EP-05-001 carry-over arm.
    tie = embargo_ending_notice(dl, before=a, after=same)
    assert tie is not None and tie.kind is EmbargoEndingKind.SHORTENED
    assert embargo_ending_notice(dl, before=short, after=a) is None


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("CM-10-007")
def test_notice_recipients_are_the_joined_unreached_signatories() -> None:
    manager = _Manager()
    case = manager.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)

    recipients = embargo_ending_notice_recipients(
        case, manager.dl, EMBARGO_ID, excluding={MANAGER}
    )

    assert set(recipients) == _unreached_signatories()
    assert (
        embargo_ending_notice_recipients(case, manager.dl, REVISION_ID) == []
    )


# ---------------------------------------------------------------------------
# AC-4, AC-5: the paused replica
# ---------------------------------------------------------------------------


class _Replica:
    """*actor_id*'s own replica, as it stands once its stream is paused."""

    def __init__(self, actor_id: str, *, removed: bool = True) -> None:
        self.actor_id = actor_id
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        _seed(self.dl)
        if removed:
            self._set_removal(f"{CASE_ID}/removals/{actor_id[-12:]}")

    def _set_removal(self, removal_activity: str | None) -> None:
        record = self.record()
        record.removal_activity = removal_activity
        self.dl.save(record)

    def record(self) -> CaseParticipant:
        record = self.dl.read(_participant_id(self.actor_id))
        assert isinstance(record, CaseParticipant)
        return record

    def case(self) -> as_VulnerabilityCase:
        case = self.dl.read(CASE_ID)
        assert isinstance(case, as_VulnerabilityCase)
        return case

    def receive(self, activity: Any) -> HandlerResult:
        return route_received(
            self.dl, activity, receiving_actor_id=self.actor_id
        )

    def embargo_state(self) -> tuple[Any, ...]:
        case = self.case()
        return (
            case.current_status.em.state,
            case.active_embargo_id,
            tuple(case.proposed_embargo_ids),
            len(case.case_statuses),
            tuple(
                (row.embargo_id, row.state)
                for row in self.record().embargo_consents
            ),
        )


def _termination_from(sender: str, dl: SqliteDataLayer, to: str) -> Any:
    return remove_embargo_from_case_activity(
        _embargo(dl), origin=CASE_ID, context=CASE_ID, actor=sender, to=[to]
    )


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.parametrize(
    ("actor_id", "removed"),
    [
        pytest.param(REMOVED, True, id="removed"),
        pytest.param(DEPARTED, False, id="departed"),
    ],
)
def test_paused_replica_applies_the_managers_termination(
    actor_id: str, removed: bool
) -> None:
    replica = _Replica(actor_id, removed=removed)
    assert ledger_stream_paused(replica.case(), replica.dl, actor_id)

    result = replica.receive(_termination_from(MANAGER, replica.dl, actor_id))

    assert result.disposition is HandlerDisposition.APPLIED
    case = replica.case()
    assert case.active_embargo_id is None
    assert case.current_status.em.state == EM.EXITED
    # The teardown is the CASE_MANAGER's act: a replica re-announces
    # nothing (BT-17-008, EMB-19-001).
    assert replica.dl.outbox_list() == []


@pytest.mark.spec("EMB-19-001")
@pytest.mark.spec("BT-17-008")
def test_active_replica_tearing_down_queues_no_announce() -> None:
    """With a trigger port wired, as in production, the replica still sends nothing."""
    replica = _Replica(ACTIVE, removed=False)

    result = route_received(
        replica.dl,
        _termination_from(MANAGER, replica.dl, ACTIVE),
        receiving_actor_id=ACTIVE,
        sync_port=SyncActivityAdapter(replica.dl),
        trigger_activity=TriggerActivityAdapter(replica.dl),
    )

    assert result.disposition is HandlerDisposition.APPLIED
    assert replica.case().active_embargo_id is None
    assert replica.dl.outbox_list() == []


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("PCR-03-001")
def test_paused_replica_ignores_a_termination_from_a_non_manager() -> None:
    replica = _Replica(REMOVED)
    before = replica.embargo_state()

    result = replica.receive(_termination_from(OWNER, replica.dl, REMOVED))

    assert result.disposition is HandlerDisposition.REFUSED
    assert replica.embargo_state() == before


def _shorter_revision_announced_by(
    sender: str, replica: _Replica, *, end_in_days: int = 30
) -> HandlerResult:
    revision = as_EmbargoEvent(
        id_=REVISION_ID,
        context=CASE_ID,
        end_time=days_from_now_utc(end_in_days),
    )
    # The inbox pre-store holds the inline embargo before dispatch
    # (EMB-18-003); the apply node stores it when it is still missing.
    return replica.receive(
        announce_embargo_activity(
            revision, context=CASE_ID, actor=sender, to=[replica.actor_id]
        )
    )


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.spec("EP-05-001")
def test_paused_replica_applies_the_managers_shorter_revision() -> None:
    replica = _Replica(REMOVED)

    result = _shorter_revision_announced_by(MANAGER, replica)

    assert result.disposition is HandlerDisposition.APPLIED
    case = replica.case()
    assert case.active_embargo_id == REVISION_ID
    assert case.current_status.em.state == EM.ACTIVE
    # Carried over by containment, as at the CASE_MANAGER (EP-05-001).
    assert replica.record().is_signatory(REVISION_ID)


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("PCR-03-001")
def test_paused_replica_ignores_a_revision_from_a_non_manager() -> None:
    replica = _Replica(REMOVED)
    before = replica.embargo_state()

    result = _shorter_revision_announced_by(OWNER, replica)

    assert result.disposition is HandlerDisposition.REFUSED
    assert replica.embargo_state() == before


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("RSH-08-003")
def test_active_replica_takes_a_revision_from_the_ledger_not_the_announce() -> (
    None
):
    replica = _Replica(ACTIVE, removed=False)
    assert not ledger_stream_paused(replica.case(), replica.dl, ACTIVE)
    before = replica.embargo_state()

    result = _shorter_revision_announced_by(MANAGER, replica)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert replica.embargo_state() == before


@pytest.mark.spec("CM-31-010")
def test_paused_replica_ignores_an_announced_longer_revision() -> None:
    replica = _Replica(REMOVED)
    before = replica.embargo_state()

    result = _shorter_revision_announced_by(MANAGER, replica, end_in_days=90)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert replica.embargo_state() == before


def _entry_event(
    activity: Any, *, event_type: str, log_index: int, prev_log_hash: str
) -> tuple[AnnounceLogEntryReceivedEvent, CaseLedgerEntry]:
    """The CASE_MANAGER's announcement of the ledger entry for *activity*.

    Returns the event and the entry, so the next entry can chain to it, as
    the backfill delivers them once the gap closed.
    """
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=log_index,
            object_id=activity.id_,
            event_type=event_type,
            payload_snapshot=activity.model_dump(
                by_alias=True, mode="json", exclude_none=True
            ),
            prev_log_hash=prev_log_hash,
        )
    )
    wire_entry = as_CaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    announce = announce_log_entry_activity(entry=wire_entry, actor=MANAGER)
    event = cast(AnnounceLogEntryReceivedEvent, extract_event(announce))
    event.activity = VultronActivity(
        id_=event.activity_id, type_="Announce", actor=MANAGER, object_=entry
    )
    return event, entry


def _replay(replica: _Replica, event: AnnounceLogEntryReceivedEvent) -> None:
    result = BTBridge(datalayer=replica.dl).execute_with_setup(
        tree=create_announce_log_entry_tree(),
        actor_id=replica.actor_id,
        activity=event,
        sync_port=SyncActivityAdapter(replica.dl),
    )
    assert result.status == Status.SUCCESS, result.feedback_message


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("CM-31-011")
def test_replaying_the_termination_after_reinstatement_changes_nothing() -> (
    None
):
    """AC-5: the notice and its ledger entry are idempotent across channels.

    The removed signatory applies the termination notice.  The Case Owner
    then reinstates it: the replica replays the ``Add(CaseParticipant)``
    entry (``ApplyReinstateCaseParticipantFromLedgerNode``, CM-31-011), which
    makes it active again, and then the termination's own entry.  That
    replay changes nothing further.
    """
    replica = _Replica(REMOVED)
    notice = replica.receive(_termination_from(MANAGER, replica.dl, REMOVED))
    assert notice.disposition is HandlerDisposition.APPLIED
    reinstatement, reinstatement_entry = _entry_event(
        add_participant_to_case_activity(
            replica.record(), target=CASE_ID, actor=OWNER, context=CASE_ID
        ),
        event_type=REINSTATE_CASE_PARTICIPANT_EVENT_TYPE,
        log_index=0,
        prev_log_hash=replica.case().genesis_hash,
    )
    _replay(replica, reinstatement)
    assert not replica.record().removed
    assert not ledger_stream_paused(replica.case(), replica.dl, REMOVED)
    after_notice = replica.embargo_state()

    termination, _ = _entry_event(
        _termination_from(MANAGER, replica.dl, REMOVED),
        event_type="remove_embargo_event_from_case",
        log_index=1,
        prev_log_hash=reinstatement_entry.entry_hash,
    )
    _replay(replica, termination)

    # Both entries were accepted onto the replica's chain, so the
    # termination really was replayed, not dropped.
    assert {
        entry.log_index
        for entry in replica.dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry) and entry.case_id == CASE_ID
    } == {0, 1}
    assert replica.embargo_state() == after_notice
    assert after_notice[:2] == (EM.EXITED, None)


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("EMB-18-003")
def test_paused_replica_refuses_an_announced_embargo_of_another_case() -> None:
    """An inline embargo whose context is another case is not stored."""
    replica = _Replica(REMOVED)
    before = replica.embargo_state()
    foreign = as_EmbargoEvent(
        id_=REVISION_ID,
        context="https://example.org/cases/another-case",
        end_time=days_from_now_utc(30),
    )

    result = replica.receive(
        announce_embargo_activity(
            foreign, context=CASE_ID, actor=MANAGER, to=[REMOVED]
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert replica.dl.read(REVISION_ID) is None
    assert replica.embargo_state() == before


@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("CM-10-005")
def test_withheld_replica_does_not_apply_an_announced_revision() -> None:
    """A withheld replica is owed no notice, so it applies no Announce.

    It is paused, but it is bound by no embargo in force; an
    ``Announce(EmbargoEvent)`` reaching it from the CASE_MANAGER is the
    teardown announcement, which must not activate the embargo it names.
    """
    replica = _Replica(DECLINER, removed=False)
    assert ledger_stream_paused(replica.case(), replica.dl, DECLINER)
    assert not awaits_embargo_ending_notice(
        replica.case(), replica.dl, DECLINER
    )
    before = replica.embargo_state()

    result = _shorter_revision_announced_by(MANAGER, replica)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert replica.embargo_state() == before


@pytest.mark.spec("CM-31-010")
def test_paused_replica_refuses_a_stored_embargo_of_another_case() -> None:
    """The case check covers an id the replica already holds, not only inline."""
    replica = _Replica(REMOVED)
    replica.dl.create(
        as_EmbargoEvent(
            id_=REVISION_ID,
            context="https://example.org/cases/another-case",
            end_time=days_from_now_utc(30),
        )
    )
    before = replica.embargo_state()

    result = _shorter_revision_announced_by(MANAGER, replica)

    assert result.disposition is HandlerDisposition.REFUSED
    assert replica.embargo_state() == before


@pytest.mark.spec("CM-31-009")
@pytest.mark.spec("BT-14-001")
def test_owed_notice_without_a_trigger_factory_is_an_internal_fault() -> None:
    """A notice owed but unbuildable is a wiring fault, not a silent skip."""
    manager = _Manager()

    with pytest.raises(
        VultronBTInternalError, match="trigger_activity_factory"
    ):
        route_received(
            manager.dl,
            remove_embargo_from_case_activity(
                _embargo(manager.dl), origin=CASE_ID, actor=OWNER, to=[MANAGER]
            ),
            receiving_actor_id=MANAGER,
            sync_port=SyncActivityAdapter(manager.dl),
        )
