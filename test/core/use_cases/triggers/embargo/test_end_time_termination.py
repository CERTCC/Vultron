"""Why an embargo ended, and ending it when its end time passes (#4293).

ADR-0122: a termination records its *what* (``END_TIME_REACHED`` or
``EARLY``, carried as the ``Remove``'s ``content``) and, on the register
entry, its *why* (a ``THREAT_SIGNAL`` cause naming the signals).  An embargo
reaches its end time through the CASE_MANAGER's lazy check or an outside
request such as a Sentinel; both share one idempotent path, and whichever
arrives second commits nothing.
"""

import threading
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.support.embargo_register import activate, propose, write_consent_rows
from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.end_time_tree import (
    end_embargo_if_end_time_passed,
    end_time_case_upkeep,
)
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.dispatcher import DirectActivityDispatcher
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import PxaDimension
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignal,
    ThreatSignalTermination,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.models.use_case_result import ActivityResult, HandlerResult
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.trigger_dispatcher import RegistryTriggerDispatcher
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.trigger_registry import entries
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
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
        self.dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.manager.id_
        )
        self.dl.create(self.manager)
        self.dl.create(self.finder)
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
        finder = FinderParticipant(
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

    def lazy_check(self, now: datetime):
        return end_embargo_if_end_time_passed(
            datalayer=self.dl,
            case_id=self.case_id,
            actor_id=self.manager.id_,
            now=now,
            **self.ports(),
        )

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

    result = end_embargo_if_end_time_passed(
        datalayer=world.dl,
        case_id=world.case_id,
        actor_id=world.finder.id_,
        now=now_utc(),
        **world.ports(),
    )

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
def test_a_case_trigger_after_the_end_time_runs_the_lazy_check_first() -> None:
    """A threat status the manager triggers after the end time finds the
    embargo already ended at its end time, not ended early."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    ports = world.ports()
    dispatcher = RegistryTriggerDispatcher(
        entries(),
        **ports,
        case_upkeep=(end_time_case_upkeep(lambda _dl: ports),),
    )

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
def test_an_inbound_activity_after_the_end_time_sees_the_embargo_ended() -> (
    None
):
    """The inbox dispatcher's lazy check commits the termination before the
    use case for the activity runs."""
    world = _World(end_time=now_utc() - timedelta(minutes=5))
    seen: list[EM] = []

    class _UseCase:
        def __init__(self, dl, event) -> None:
            pass

        def execute(self) -> HandlerResult:
            seen.append(world.case().em_state)
            return HandlerResult.applied()

    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.ADD_NOTE_TO_CASE: _UseCase},
        case_upkeep=(end_time_case_upkeep(lambda _dl: world.ports()),),
    )
    event = MagicMock()
    event.semantic_type = MessageSemantics.ADD_NOTE_TO_CASE
    event.actor_id = None  # skips the join-backfill gate
    event.case_id = world.case_id
    event.activity_id = f"{world.case_id}/activities/note"
    event.receiving_actor_id = world.manager.id_

    dispatcher.dispatch(event, world.dl)

    assert seen == [EM.EXITED]
    _assert_full_cascade(world, EmbargoTermination.end_time_reached())


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
