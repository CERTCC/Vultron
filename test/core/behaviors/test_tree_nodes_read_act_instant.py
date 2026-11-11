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
"""Tree builders and deciding nodes read the act's instant, never the clock.

Slice 2 of ADR-0176 (#5649).  A builder takes no time and reads no clock, so
building a tree moves no recorded run's clock; a clock decision with nothing
due reads no clock when it ticks either; and each deciding node judges at the
instant the act carries, so the same instant gives the same verdict.

The static half, that no module below the act's edge reads the clock, is
``test/architecture/test_clock_reads_at_act_edge.py``.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import make_embargo_case_with_actor
from test.support.act_clock import clock_at, recorded_clock_reads
from test.support.act_runner import run_tree
from test.support.clock_decisions import run_end_time_check
from test.support.embargo_register import activate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.case_clock_decisions import (
    case_clock_decisions,
)
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    create_clock_decision_gate,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    ClearRefusedAssertionNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
    create_propose_ownership_transfer_tree,
    create_reject_ownership_transfer_tree,
    create_undo_ownership_transfer_tree,
)
from vultron.core.behaviors.embargo.answer_trees import (
    accept_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.end_time_tree import (
    end_embargo_at_end_time_bt,
    end_time_clock_decision,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    ask_case_manager_to_terminate_once,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.models import _helpers
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.pending_assertion import (
    PendingAssertionStore,
    get_pending_assertion_store,
    reset_pending_assertion_stores,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
    ProposeCaseOwnershipTransferReceivedUseCase,
    RejectCaseOwnershipTransferReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE = "https://example.org/cases/act-instant-slice-2"
_OWNER = "https://example.org/actors/owner"
_OTHER = "https://example.org/actors/other"
_OFFER = f"{_CASE}/offers/o1"
# A fixed end time: the act's instant is pinned, so no wall clock is needed.
_END_TIME = datetime(2026, 6, 1, 12, tzinfo=UTC)


@pytest.fixture
def clock_reads() -> Iterator[list[datetime]]:
    """Every read of the wall clock behind ``now_utc``, in order."""
    with recorded_clock_reads() as reads:
        assert _helpers.now_utc() is not None
        reads.clear()
        yield reads


#: Every builder this slice changed, built as its production caller builds it.
_BUILDERS: dict[str, Callable[[], object]] = {
    "case_clock_decisions": lambda: case_clock_decisions(_CASE),
    "embargo_clock_decisions": lambda: embargo_clock_decisions(_CASE),
    "end_time_clock_decision": lambda: end_time_clock_decision(case_id=_CASE),
    "end_embargo_at_end_time_bt": lambda: end_embargo_at_end_time_bt(
        case_id=_CASE, result_out={}
    ),
    "terminate_embargo_bt": lambda: terminate_embargo_bt(
        case_id=_CASE,
        result_out={},
        termination=EmbargoTermination.end_time_reached(),
    ),
    "ask_case_manager_to_terminate_once": lambda: (
        ask_case_manager_to_terminate_once(_CASE, TerminationReason.EARLY)
    ),
    "accept_invite_to_embargo_tree": lambda: accept_invite_to_embargo_tree(
        case_id=_CASE,
        embargo_id=f"{_CASE}/embargo_events/e1",
        accepting_actor_id=_OTHER,
        invite_id=f"{_CASE}/invites/i1",
        sender_rule=AcceptInviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
    ),
    "create_propose_ownership_transfer_tree": lambda: (
        create_propose_ownership_transfer_tree(
            case_id=_CASE,
            proposed_case_id=_CASE,
            transferee_id=_OTHER,
            proposal_id=f"{_CASE}/proposals/p1",
            sender_rule=ProposeCaseOwnershipTransferReceivedUseCase.sender_entitlement,
            sender_id=_OWNER,
        )
    ),
    "create_accept_ownership_transfer_tree": lambda: (
        create_accept_ownership_transfer_tree(
            case_id=_CASE,
            offer_id=_OFFER,
            sender_id=_OTHER,
            answer_id=f"{_CASE}/answers/a1",
            sender_rule=AcceptCaseOwnershipTransferReceivedUseCase.sender_entitlement,
        )
    ),
    "create_reject_ownership_transfer_tree": lambda: (
        create_reject_ownership_transfer_tree(
            case_id=_CASE,
            offer_id=_OFFER,
            sender_id=_OTHER,
            answer_id=f"{_CASE}/answers/r1",
            sender_rule=RejectCaseOwnershipTransferReceivedUseCase.sender_entitlement,
        )
    ),
    "create_undo_ownership_transfer_tree": lambda: (
        create_undo_ownership_transfer_tree(
            case_id=_CASE,
            offer_id=_OFFER,
            sender_id=_OWNER,
            undo_id=f"{_CASE}/undos/u1",
            sender_rule=UndoCaseOwnershipTransferReceivedUseCase.sender_entitlement,
        )
    ),
}


@pytest.mark.spec("CS-13-002")
@pytest.mark.parametrize("name", sorted(_BUILDERS))
def test_building_a_tree_reads_no_clock(
    name: str, clock_reads: list[datetime]
) -> None:
    _BUILDERS[name]()

    assert clock_reads == []


def _manager_store(end_time: datetime):
    """The CASE_MANAGER's store with an embargo in force ending *end_time*."""
    dl, _, case, embargo = make_embargo_case_with_actor(
        _CASE, _OWNER, case_manager_actor_id=_OWNER
    )
    dl.save(as_EmbargoEvent(id_=embargo.id_, context=_CASE, end_time=end_time))
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    activate(stored, embargo.id_)
    dl.save(stored)
    return dl


def _run_decisions(dl, at: datetime) -> Status:
    gate = create_clock_decision_gate(
        _CASE, [*case_clock_decisions(_CASE), *embargo_clock_decisions(_CASE)]
    )
    result = run_tree(
        BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ),
        tree=gate,
        actor_id=_OWNER,
        at=at,
    )
    assert not result.internal_error, result.feedback_message
    return result.status


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("CLP-10-025")
def test_clock_decisions_with_nothing_due_read_no_clock(
    clock_reads: list[datetime],
) -> None:
    """A decision that writes nothing moves no recording (ADR-0176)."""
    at = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    dl = _manager_store(end_time=at + timedelta(days=30))
    clock_reads.clear()

    assert _run_decisions(dl, at) == Status.SUCCESS

    assert clock_reads == []


@pytest.mark.spec("EMB-13-003")
@pytest.mark.parametrize(
    ("offset", "ended"),
    [(timedelta(microseconds=-1), False), (timedelta(0), True)],
)
def test_the_end_time_decision_judges_at_the_acts_instant(
    offset: timedelta, ended: bool
) -> None:
    """The same instant gives the same verdict: an embargo ends at its end
    time, not a moment before (ADR-0122).

    The case is created before its embargo's end, as it is in production, so
    the ending entry the check commits postdates it (CLP-14-013)."""
    end = _END_TIME
    with clock_at(end - timedelta(days=30)):
        dl = _manager_store(end_time=end)

    run_end_time_check(dl, _CASE, _OWNER, now=end + offset)

    em = cast(VulnerabilityCase, dl.read(_CASE)).em_state
    assert (em is EM.EXITED) is ended


@pytest.fixture
def owner_pending_store() -> Iterator[PendingAssertionStore]:
    """The owner's pending-assertion store, reset around the test."""
    reset_pending_assertion_stores()
    yield get_pending_assertion_store(_OWNER)
    reset_pending_assertion_stores()


@pytest.mark.spec("CS-13-002", "CLP-06-006")
@pytest.mark.parametrize("overdue", [False, True])
def test_clearing_a_refused_assertion_judges_its_timeout_at_the_acts_instant(
    owner_pending_store: PendingAssertionStore, overdue: bool
) -> None:
    """The clear marks what is overdue at the act's instant, not the clock's,
    so a still-pending entry is cleared and an overdue one is left timed
    out."""
    refused = f"{_CASE}/activities/refused"
    emitted = datetime.now(tz=UTC)
    owner_pending_store.add(_CASE, "add_note_to_case", refused, at=emitted)
    at = emitted + timedelta(
        seconds=owner_pending_store.timeout_seconds + 1 if overdue else 0
    )
    node = ClearRefusedAssertionNode(
        case_id=_CASE,
        refused_activity_id=refused,
        reason="refused",
        sender_id=_OTHER,
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)

    result = run_tree(BTBridge(datalayer=dl), node, actor_id=_OWNER, at=at)

    assert result.status == Status.SUCCESS
    assert [e.object_id for e in node.cleared] == (
        [] if overdue else [refused]
    )
