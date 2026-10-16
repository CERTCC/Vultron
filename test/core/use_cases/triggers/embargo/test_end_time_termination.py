"""Why an embargo ended, and ending it when its end time passes (#4293).

ADR-0122: a termination records its *what* (``END_TIME_REACHED`` or
``EARLY``, carried as the ``Remove``'s ``content``) and, on the register
entry, its *why* (a ``THREAT_SIGNAL`` cause naming the signals).  An embargo
reaches its end time through the CASE_MANAGER's lazy check or an outside
request such as a Sentinel; both share one idempotent path, and whichever
arrives second commits nothing.  The lazy check is a clock decision composed
into the one tree that handles a received activity or a case-scoped trigger
(CLP-10-025, ADR-0135), never a separate tree run ahead of it.
"""

import threading
from datetime import datetime, timedelta
from typing import cast

import pytest
from py_trees.common import Status

from test.support.clock_decisions import run_end_time_check
from test.support.embargo_register import (
    activate,
    agree_to_active_embargo,
    propose,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.end_time_tree import (
    END_TIME_LEDGER_FRESH_NODE_NAME,
)
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.behaviors.sync.nodes import CheckLedgerFreshnessNode
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import PxaDimension
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignal,
    ThreatSignalTermination,
)
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.use_case_result import (
    ActivityResult,
    HandlerDisposition,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.rm import RM
from vultron.core.trigger_dispatcher import RegistryTriggerDispatcher
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.core.use_cases.triggers.case.add_participant_status import (
    SvcAddParticipantStatusUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcTerminateEmbargoUseCase,
    SvcWithdrawEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    AddParticipantStatusTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    TerminateEmbargoTriggerRequest,
    WithdrawEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.semantic_registry import extract_event
from vultron.trigger_registry import entries
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

S = EmbargoRegisterStatus


class _World:
    """A CASE_MANAGER's store holding a case with an embargo in force.

    The embargo in force ends at *end_time*; a second embargo is an open
    revision of it, so a termination must cancel it (EP-08-004).  A finder
    participant is the other party the teardown announcement reaches.
    """

    def __init__(self, end_time: datetime) -> None:
        self.manager = as_Service(name="Vendor Co")
        self.finder = as_Service(name="Finder Co")
        self.stranger = as_Service(name="Stranger Co")
        self.dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.manager.id_
        )
        self.dl.create(self.manager)
        self.dl.create(self.finder)
        self.dl.create(self.stranger)
        case = VulnerabilityCase(
            name="End-time case", attributed_to=self.manager.id_
        )
        self.embargo = as_EmbargoEvent(context=case.id_, end_time=end_time)
        self.revision = as_EmbargoEvent(
            context=case.id_, end_time=end_time + timedelta(days=30)
        )
        owner = VendorParticipant(
            attributed_to=self.manager.id_, context=case.id_
        )
        owner.add_role(CVDRole.CASE_MANAGER)
        finder = ReporterParticipant(
            attributed_to=self.finder.id_, context=case.id_
        )
        case.case_participants = [owner.id_, finder.id_]
        case.actor_participant_index = {
            self.manager.id_: owner.id_,
            self.finder.id_: finder.id_,
        }
        activate(case, self.embargo.id_)
        propose(case, self.revision.id_)
        self.case_id = case.id_
        self.finder_participant = finder
        for obj in (case, self.embargo, self.revision, owner, finder):
            self.dl.create(obj)
        write_consent_rows(self.dl, case)

    def case(self) -> VulnerabilityCase:
        return cast(VulnerabilityCase, self.dl.read(self.case_id))

    def ports(self) -> dict:
        return {
            "trigger_activity": TriggerActivityAdapter(self.dl),
            "sync_port": SyncActivityAdapter(self.dl),
            "wire_render_port": As2WireRenderAdapter(),
        }

    def lazy_check(self, now: datetime, actor_id: str | None = None):
        """Run the end-time check as the clock-decision stage runs it."""
        return run_end_time_check(
            self.dl, self.case_id, actor_id or self.manager.id_, now
        )

    def status_from(self, sender_id: str):
        """A received ``Add(ParticipantStatus)`` from *sender_id* to the
        CASE_MANAGER (PCR-08), handled by its real received use case."""
        status = as_ParticipantStatus(
            context=self.case_id, attributed_to=sender_id
        )
        self.dl.create(status)
        activity = add_status_to_participant_activity(
            status,
            target=self.finder_participant,
            actor=sender_id,
            context=self.case_id,
            to=[self.manager.id_],
        )
        event = cast(
            AddParticipantStatusToParticipantReceivedEvent,
            extract_event(activity).model_copy(
                update={"receiving_actor_id": self.manager.id_}
            ),
        )
        return AddParticipantStatusToParticipantReceivedUseCase(
            self.dl, event, **self.ports()
        ).execute()

    def sentinel_request(self, reason=TerminationReason.END_TIME_REACHED):
        return SvcTerminateEmbargoUseCase(
            self.dl,
            TerminateEmbargoTriggerRequest(
                actor_id=self.manager.id_, case_id=self.case_id, reason=reason
            ),
            **self.ports(),
        ).execute()

    def teardown_entries(self):
        return [
            entry
            for entry in ledger_entries(self.dl, self.case_id)
            if entry.event_type == EMBARGO_TEARDOWN_EVENT_TYPE
        ]


def _assert_full_cascade(world: _World, termination: EmbargoTermination):
    """AC-5: TERMINATED with its reason, proposals CANCELLED, EM EXITED, ET."""
    case = world.case()
    entry = case.embargo_register_entry(world.embargo.id_)
    assert entry is not None
    assert entry.status is S.TERMINATED
    assert entry.termination == termination
    assert case.embargo_termination == termination
    assert case.embargo_register_status(world.revision.id_) is S.CANCELLED
    assert case.em_state is EM.EXITED
    (teardown,) = world.teardown_entries()
    snapshot = teardown.payload_snapshot
    assert snapshot["type"] == "Remove"
    assert snapshot["content"] == termination.reason.value
    assert snapshot["actor"] == world.manager.id_
    # The announcement reaches the other participant, never the manager.
    assert world.finder.id_ in snapshot["to"]
    assert world.manager.id_ not in snapshot["to"]
    assert snapshot["id"] in world.dl.outbox_list()


# ---------------------------------------------------------------------------
# AC-3: the CASE_MANAGER's lazy check
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-003")
def test_lazy_check_ends_an_embargo_whose_end_time_has_passed() -> None:
    world = _World(end_time=now_utc() - timedelta(hours=1))

    result = world.lazy_check(now_utc())

    assert result.status == Status.SUCCESS
    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


@pytest.mark.spec("EMB-13-003")
def test_lazy_check_leaves_an_embargo_still_in_force() -> None:
    world = _World(end_time=days_from_now_utc(10))

    result = world.lazy_check(now_utc())

    assert result.status == Status.SUCCESS
    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []


@pytest.mark.spec("EMB-13-003")
def test_lazy_check_does_nothing_for_a_participant_that_is_not_manager() -> (
    None
):
    world = _World(end_time=now_utc() - timedelta(hours=1))

    result = world.lazy_check(now_utc(), actor_id=world.finder.id_)

    assert result.status == Status.SUCCESS
    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []


@pytest.mark.spec("EMB-13-003")
def test_lazy_check_on_an_ended_embargo_commits_nothing() -> None:
    world = _World(end_time=now_utc() - timedelta(hours=1))
    world.lazy_check(now_utc())

    result = world.lazy_check(now_utc())

    assert result.status == Status.SUCCESS
    assert len(world.teardown_entries()) == 1


# ---------------------------------------------------------------------------
# AC-4: an outside request (a Sentinel) shares the path
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-003")
def test_sentinel_request_ends_the_embargo_at_its_end_time() -> None:
    world = _World(end_time=now_utc() - timedelta(minutes=5))

    result = world.sentinel_request()

    assert result.activity is not None
    assert result.activity["content"] == "END_TIME_REACHED"
    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


@pytest.mark.spec("EMB-13-003")
def test_sentinel_request_before_the_end_time_is_refused() -> None:
    world = _World(end_time=days_from_now_utc(10))

    with pytest.raises(VultronInvalidStateTransitionError, match="before"):
        world.sentinel_request()

    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []


@pytest.mark.spec("EMB-13-003")
def test_sentinel_after_the_lazy_check_is_answered_as_already_done() -> None:
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    world.lazy_check(now_utc())

    result = world.sentinel_request()

    assert result.activity is None
    assert len(world.teardown_entries()) == 1


@pytest.mark.spec("EMB-13-003")
def test_lazy_check_after_the_sentinel_commits_nothing() -> None:
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    world.sentinel_request()

    result = world.lazy_check(now_utc())

    assert result.status == Status.SUCCESS
    assert len(world.teardown_entries()) == 1


@pytest.mark.spec("EMB-13-003")
def test_racing_lazy_check_and_sentinel_commit_one_termination() -> None:
    """Started together, exactly one of the two commits the termination,
    and the other is answered as already done."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    start = threading.Barrier(2)
    errors: list[BaseException] = []
    results: dict[str, object] = {}

    def run(name: str, step) -> None:
        start.wait()
        try:
            results[name] = step()
        except BaseException as exc:  # noqa: BLE001 — reported below
            errors.append(exc)

    threads = [
        threading.Thread(
            target=run, args=("sentinel", world.sentinel_request)
        ),
        threading.Thread(
            target=run, args=("lazy", lambda: world.lazy_check(now_utc()))
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    _assert_full_cascade(world, EmbargoTermination.end_time_reached())
    (teardown,) = world.teardown_entries()
    sentinel = cast(ActivityResult, results["sentinel"])
    lazy = cast(BTExecutionResult, results["lazy"])
    # The lazy check never fails; the Sentinel either committed the one
    # termination or was answered as already done, with no activity.
    assert lazy.status == Status.SUCCESS
    if sentinel.activity is not None:
        assert sentinel.activity["id"] == teardown.payload_snapshot["id"]


@pytest.mark.spec("EMB-13-003")
def test_an_early_request_after_the_end_time_ends_it_at_its_end_time() -> None:
    world = _World(end_time=now_utc() - timedelta(minutes=5))

    result = world.sentinel_request(reason=TerminationReason.EARLY)

    assert result.activity is not None
    assert result.activity["content"] == "END_TIME_REACHED"
    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


@pytest.mark.spec("EMB-13-003")
@pytest.mark.spec("BT-15-001")
def test_a_case_trigger_after_the_end_time_runs_the_lazy_check_first() -> None:
    """A threat status the manager triggers after the end time finds the
    embargo already ended at its end time, not ended early: the check is the
    first step of the trigger's own tree (ADR-0135)."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    dispatcher = RegistryTriggerDispatcher(entries(), **world.ports())

    dispatcher.trigger(
        AddParticipantStatusTriggerRequest(
            actor_id=world.manager.id_,
            case_id=world.case_id,
            pxa_state=CS_pxa.Pxa,
        ),
        world.dl,
    )

    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


@pytest.mark.spec("EMB-13-003")
def test_accepting_a_revision_after_the_end_time_does_not_extend_it() -> None:
    """The owner's accept of the open revision, triggered after the end
    time, finds the embargo ended and the revision cancelled, so it cannot
    silently extend an expired embargo."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    case = world.case()
    case.pending_embargo_proposal_index = {
        world.revision.id_: f"{world.case_id}/proposals/revision"
    }
    world.dl.save(case)

    # The register refuses to activate the cancelled revision.
    with pytest.raises(VultronInvalidStateTransitionError, match="CANCELLED"):
        SvcAcceptEmbargoUseCase(
            world.dl,
            AcceptEmbargoTriggerRequest(
                actor_id=world.manager.id_,
                case_id=world.case_id,
            ),
            **world.ports(),
        ).execute()

    _assert_full_cascade(world, EmbargoTermination.end_time_reached())
    assert world.case().active_embargo_id is None


@pytest.mark.spec("EMB-13-003")
@pytest.mark.spec("CLP-10-025")
def test_a_participants_activity_after_the_end_time_ends_the_embargo() -> None:
    """The end-time check is a clock decision of the received tree: a
    participant's activity naming the overdue case lets the CASE_MANAGER end
    the embargo before it judges the activity."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))

    world.status_from(world.finder.id_)

    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("HP-01-006")
def test_a_non_participants_activity_commits_no_termination() -> None:
    """The sender guard runs before the clock decisions, so a sender with no
    standing in the case never makes the CASE_MANAGER write (AC-9)."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    before = len(ledger_entries(world.dl, world.case_id))

    result = world.status_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []
    assert len(ledger_entries(world.dl, world.case_id)) == before


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("EP-08-004")
def test_the_termination_commits_one_entry_per_as2_activity_in_order() -> None:
    """Each entry the end-time decision commits is one CASE_MANAGER-authored
    AS2 activity: the ``Remove`` first, whose register step already cancelled
    the open revision, then the ``Add(CaseStatus)`` (ADR-0135)."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    before = {e.id_ for e in ledger_entries(world.dl, world.case_id)}

    world.lazy_check(now_utc())

    added = [
        e
        for e in ledger_entries(world.dl, world.case_id)
        if e.id_ not in before
    ]
    assert [e.payload_snapshot["type"] for e in added] == ["Remove", "Add"]
    assert all(e.payload_snapshot["actor"] == world.manager.id_ for e in added)
    assert len({e.log_object_id for e in added}) == len(added)
    # No register state shows TERMINATED beside a PROPOSED entry.
    case = world.case()
    assert case.embargo_register_status(world.revision.id_) is S.CANCELLED


# ---------------------------------------------------------------------------
# AC-5: every cause runs the full cascade
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-08-004")
def test_an_early_termination_runs_the_full_cascade() -> None:
    world = _World(end_time=days_from_now_utc(10))

    world.sentinel_request(reason=TerminationReason.EARLY)

    _assert_full_cascade(world, EmbargoTermination.early())


@pytest.mark.spec("EP-08-004")
@pytest.mark.spec("RSH-03-001")
def test_a_threat_termination_records_its_signals_and_runs_the_cascade() -> (
    None
):
    world = _World(end_time=days_from_now_utc(10))
    sync_port = SyncActivityAdapter(world.dl)

    result = BTBridge(datalayer=world.dl, **world.ports()).execute_with_setup(
        tree=terminate_embargo_bt(
            case_id=world.case_id,
            result_out={},
            termination=ThreatSignalTermination(
                signals=[ThreatSignal.P, ThreatSignal.X]
            ),
        ),
        actor_id=world.manager.id_,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS, result.feedback_message
    # The wire carries the what (EARLY); the entry records the why too.
    _assert_full_cascade(
        world, EmbargoTermination.threat([ThreatSignal.P, ThreatSignal.X])
    )


@pytest.mark.spec("EMB-13-004")
@pytest.mark.spec("RSH-03-001")
def test_a_threat_status_records_the_signals_it_carries() -> None:
    """The cascade a received threat status starts records ``EARLY`` on the
    wire and ``THREAT_SIGNAL`` with the status's signals on the entry."""
    world = _World(end_time=days_from_now_utc(10))
    status = as_CaseStatus(
        context=world.case_id, pxa=PxaDimension(state=CS_pxa.PXa)
    )

    result = BTBridge(datalayer=world.dl, **world.ports()).execute_with_setup(
        tree=ThreatTerminationBranchNode(
            status_obj=status,
            case_id=world.case_id,
            sender_actor_id=world.finder.id_,
        ),
        actor_id=world.manager.id_,
    )

    assert result.status == Status.SUCCESS, result.feedback_message
    _assert_full_cascade(
        world, EmbargoTermination.threat([ThreatSignal.P, ThreatSignal.X])
    )


# ---------------------------------------------------------------------------
# A case trigger after the end time judges the case the decision left
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-003")
@pytest.mark.spec("BT-15-003")
def test_revising_after_the_end_time_is_refused_and_extends_nothing() -> None:
    """The revision is judged after the end-time decision ended the
    embargo, so it cannot propose new terms for an expired one."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))

    with pytest.raises(VultronInvalidStateTransitionError, match="EXITED"):
        SvcProposeEmbargoRevisionUseCase(
            world.dl,
            ProposeEmbargoRevisionTriggerRequest(
                actor_id=world.manager.id_,
                case_id=world.case_id,
                end_time=days_from_now_utc(20),
            ),
            **world.ports(),
        ).execute()

    _assert_full_cascade(world, EmbargoTermination.end_time_reached())
    assert [
        e.payload_snapshot["type"]
        for e in ledger_entries(world.dl, world.case_id)
    ] == ["Remove", "Add"]


@pytest.mark.spec("EMB-13-003")
@pytest.mark.spec("BT-15-003")
def test_withdrawing_after_the_end_time_commits_no_leave() -> None:
    """A CASE_MANAGER that is not the owner passes the withdraw trigger's
    own checks before the decision runs; its tree then finds no embargo in
    force and commits no ``Leave``."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    case = world.case()
    case.attributed_to = world.finder.id_
    world.dl.save(case)
    agree_to_active_embargo(world.dl, world.case(), world.manager.id_)

    with pytest.raises(VultronValidationError, match="No embargo is in force"):
        SvcWithdrawEmbargoUseCase(
            world.dl,
            WithdrawEmbargoTriggerRequest(
                actor_id=world.manager.id_, case_id=world.case_id
            ),
            **world.ports(),
        ).execute()

    _assert_full_cascade(world, EmbargoTermination.end_time_reached())
    assert [
        e.payload_snapshot["type"]
        for e in ledger_entries(world.dl, world.case_id)
    ] == ["Remove", "Add"]


def _refuse_the_end_time_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the ledger refuse the end-time termination's commit, as a
    gapped local prefix does (SYNC-10-001), and only that commit."""
    original = CheckLedgerFreshnessNode.update

    def _update(node: CheckLedgerFreshnessNode) -> Status:
        if node.name == END_TIME_LEDGER_FRESH_NODE_NAME:
            node.feedback_message = "local ledger prefix has a gap"
            return Status.FAILURE
        return original(node)

    monkeypatch.setattr(CheckLedgerFreshnessNode, "update", _update)


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("BT-15-003")
def test_a_refused_end_time_commit_lets_the_trigger_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clock decision whose commit the ledger refuses is logged and the
    trigger's own tree still runs, against the case as it stands."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    _refuse_the_end_time_commit(monkeypatch)

    result = SvcAddParticipantStatusUseCase(
        world.dl,
        AddParticipantStatusTriggerRequest(
            actor_id=world.manager.id_,
            case_id=world.case_id,
            rm_state=RM.RECEIVED,
        ),
        **world.ports(),
    ).execute()

    assert result.activity_id is not None
    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []


@pytest.mark.spec("CLP-10-025")
def test_a_refused_end_time_commit_lets_the_received_tree_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same refusal in a received tree is logged, and the activity is
    still judged, against the case as it stands."""
    in_force = _World(end_time=days_from_now_utc(10))
    expected = in_force.status_from(in_force.finder.id_).disposition
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    _refuse_the_end_time_commit(monkeypatch)

    result = world.status_from(world.finder.id_)

    # Judged as it would be on a case whose embargo is still in force.
    assert result.disposition is expected
    assert expected is not HandlerDisposition.REFUSED
    assert world.case().em_state is EM.REVISE
    assert world.teardown_entries() == []
