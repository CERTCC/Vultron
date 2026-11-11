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

"""No outbox entry is delivered before the act that queued it commits (OX-03-002).

A node that sends an activity and then commits the ledger entry recording it
(SYNC-09-002) writes the outbox first.  The outbox monitor drains as soon as
an activity is queued (OX-09-001), so a drain woken by that write can take
the activity before the commit runs.  Should the commit then fail, a
participant has an act no ledger entry records (CLP-07-013).

Each node here runs on its own, outside any ``ActTransaction``, so the only
transaction around its send is the one the node opens itself.  The store's
enqueue callback stands in for the woken drain: it takes every pending
activity at once, as a drain that wins the race does, and notes whether the
entry recording it was already committed.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import cast

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    make_case_with_manager,
)
from test.support.act_runner import run_tree
from test.support.ledger import fail_commits
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    EmitInviteActorToCaseNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    EmitOfferCaseParticipantToOwnerNode,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.enums.roles import CVDRole

_OWNER = "https://example.org/actors/owner"
_INVITEE = "https://example.org/actors/invitee"
_RECOMMENDER = "https://example.org/actors/recommender"


class _AddressedCaseManagerNote(_CommitCaseManagerActivityBase):
    """A CASE_MANAGER act addressed to the case's other participants.

    The shape of every ``_CommitCaseManagerActivityBase`` send
    (``notify_participants=True``): queued, then committed.
    """

    def __init__(self, case_id: str) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=MessageSemantics.ADD_NOTE_TO_CASE.value,
            notify_participants=True,
        )

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        factory = self.trigger_activity_factory
        assert factory is not None and self.actor_id is not None
        note_id, _ = factory.create_note(
            name="addressed note",
            content="sent to every other participant",
            context_id=self._case_id,
            attributed_to=self.actor_id,
        )
        return factory.add_note_to_case(
            note_id=note_id, case_id=self._case_id, actor=self.actor_id, to=to
        )


@dataclass
class _Setup:
    """A store holding a case, the node that sends on it, and its actor."""

    dl: SqliteDataLayer
    actor_id: str
    case_id: str
    node: Callable[[], py_trees.behaviour.Behaviour]
    semantic_type: str


def _case_manager_act() -> _Setup:
    case, _cm, dl = make_case_with_manager("ox-03-002")
    return _Setup(
        dl=dl,
        actor_id=CASE_MANAGER_ACTOR,
        case_id=case.id_,
        node=lambda: _AddressedCaseManagerNote(case.id_),
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE.value,
    )


def _stub_invite() -> _Setup:
    case_id = "https://example.org/cases/ox-03-002-invite"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)
    dl.create(
        make(
            VulnerabilityCase,
            id_=case_id,
            name="OX-03-002 stub invite",
            attributed_to=_OWNER,
            stub_summary="Security issue - details shared after acceptance",
        )
    )
    return _Setup(
        dl=dl,
        actor_id=_OWNER,
        case_id=case_id,
        node=lambda: EmitInviteActorToCaseNode(
            invitee_id=_INVITEE, case_id=case_id, roles=["vendor"]
        ),
        semantic_type="invite_actor_to_case",
    )


def _participant_offer() -> _Setup:
    case_manager = "https://example.org/actors/case-actor"
    case_id = "https://example.org/cases/ox-03-002-offer"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_manager)
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="OX-03-002 offer",
        attributed_to=_OWNER,
    )
    records = [
        make(
            CaseParticipant,
            id_=f"{case_id}/participants/case-actor",
            attributed_to=case_manager,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        ),
        make(
            CaseParticipant,
            id_=f"{case_id}/participants/owner",
            attributed_to=_OWNER,
            context=case_id,
            case_roles=[CVDRole.CASE_OWNER],
        ),
    ]
    for record in records:
        actor = cast(str, record.attributed_to)
        case.actor_participant_index[actor] = record.id_
        case.case_participants.append(record.id_)
    dl.create(case)
    for record in records:
        dl.create(record)
    return _Setup(
        dl=dl,
        actor_id=case_manager,
        case_id=case_id,
        node=lambda: EmitOfferCaseParticipantToOwnerNode(
            recommendation_id="https://example.org/activities/recommend-1",
            recommender_id=_RECOMMENDER,
            recommended_id=_INVITEE,
            case_id=case_id,
        ),
        semantic_type="offer_case_participant",
    )


SENDERS: dict[str, Callable[[], _Setup]] = {
    "CASE_MANAGER act (_CommitCaseManagerActivityBase)": _case_manager_act,
    "stub Invite (_EmitSingleActivityBase._record_sent)": _stub_invite,
    "Offer(CaseParticipant) to the Case Owner": _participant_offer,
}


@dataclass
class _EagerDrain:
    """An outbox drain woken by every enqueue (OX-09-001) that wins the race.

    It takes each pending activity the moment it is woken and records, for
    each, whether the act's *semantic_type* entry was committed when it was
    taken.  The act's ``Announce(CaseLedgerEntry)`` fan-out is queued by the
    commit itself (SYNC-09-002), so it is taken with the entry committed.
    """

    dl: SqliteDataLayer
    semantic_type: str
    delivered: dict[str, bool] = field(default_factory=dict)

    def __call__(self, _actor_id: str) -> None:
        while (activity_id := self.dl.outbox_pop()) is not None:
            self.delivered[activity_id] = self.semantic_type in (
                _committed_semantic_types(self.dl)
            )


def _committed_semantic_types(dl: SqliteDataLayer) -> set[str]:
    return {
        e.semantic_type
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
    }


@pytest.fixture(params=sorted(SENDERS))
def setup(request: pytest.FixtureRequest) -> Iterator[_Setup]:
    built = SENDERS[request.param]()
    yield built
    built.dl.close()


def _run(setup: _Setup) -> tuple[_EagerDrain, BTExecutionResult]:
    drain = _EagerDrain(setup.dl, setup.semantic_type)
    setup.dl.set_enqueue_callback(drain)
    result = run_tree(
        BTBridge(
            datalayer=setup.dl,
            trigger_activity=TriggerActivityAdapter(setup.dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(setup.dl),
        ),
        tree=setup.node(),
        actor_id=setup.actor_id,
        case_id=setup.case_id,
    )
    return drain, result


@pytest.mark.spec("OX-03-002")
@pytest.mark.spec("OX-09-001")
def test_a_send_whose_commit_fails_is_never_delivered(
    setup: _Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The act's commit fails after its outbox write: nothing is delivered."""
    failed = fail_commits(
        monkeypatch,
        commit_tree,
        when=lambda kw: kw["semantic_type"] == setup.semantic_type,
    )

    drain, result = _run(setup)

    assert failed, "the act never reached its commit"
    # The failed commit escapes the node as an internal error, never a plain
    # FAILURE an enclosing Selector could read as a guard miss (BT-14-001).
    assert result.status == py_trees.common.Status.FAILURE
    assert result.internal_error is True
    assert drain.delivered == {}, (
        "an activity whose act did not commit was delivered:"
        f" {sorted(drain.delivered)}"
    )
    assert setup.dl.outbox_list() == []
    assert setup.semantic_type not in _committed_semantic_types(setup.dl)


@pytest.mark.spec("OX-03-002")
@pytest.mark.spec("OX-09-001")
def test_a_committed_send_is_delivered_only_after_its_commit(
    setup: _Setup,
) -> None:
    """A drain woken by the send finds the act's entry already committed."""
    drain, result = _run(setup)

    assert result.status == py_trees.common.Status.SUCCESS
    assert drain.delivered, "the act sent nothing"
    assert all(drain.delivered.values()), (
        "delivered before the entry recording it committed:"
        f" {sorted(a for a, ok in drain.delivered.items() if not ok)}"
    )
