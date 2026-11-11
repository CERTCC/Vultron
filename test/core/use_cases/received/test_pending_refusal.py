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

"""The CASE_MANAGER's refusal closes the proposer's pending assertion.

A non-manager's embargo proposal is recorded in its pending-assertion store
(EP-09-008, SYNC-11-002).  A refused proposal is never committed, so only the
manager's ``Reject(Invite(EmbargoEvent))`` closes it; another participant's
``Reject`` is an answer, not the refusal, and closes nothing (#3962 AC-4).
"""

from datetime import timedelta
from typing import cast

import pytest

from test.support.act_clock import recorded_clock_reads
from test.support.act_runner import run_in_act
from test.support.future_dates import days_from_now
from test.support.objects import make
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.pending_assertion import (
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.use_cases.received._pending_refusal import (
    close_refused_embargo_ask,
)
from vultron.core.use_cases.received.embargo import (
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    ReporterParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_PROPOSER = "https://example.org/actors/refusal-finder"
_MANAGER = "https://example.org/actors/refusal-manager"
_OTHER = "https://example.org/actors/refusal-other"
_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_ACCEPT = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value


def _proposer_with_pending_proposal(
    *,
    manager_roster_id: str = _MANAGER,
    other_is_case_manager: bool = False,
) -> tuple[SqliteDataLayer, VulnerabilityCase, as_Invite]:
    """The proposer's replica: its ask to the manager is pending.

    *manager_roster_id* is how the roster spells the manager: the
    ``attributed_to`` a peer wrote inside an activity, which the extractor
    does not normalise as it does a sender id (OID-01-007).  With
    *other_is_case_manager* the roster also records ``CVDRole.CASE_MANAGER``
    on ``_OTHER``, listed after the manager — the window a role delegation
    opens (CM-33).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_PROPOSER)
    for actor_id in (_PROPOSER, _MANAGER, _OTHER):
        dl.create(
            make(as_Service, id_=actor_id, name=actor_id.rsplit("/", 1)[-1])
        )
    case = make(VulnerabilityCase, name="Refusal case", attributed_to=_MANAGER)
    manager = make(
        VendorParticipant,
        attributed_to=manager_roster_id,
        context=case.id_,
    )
    manager.add_role(CVDRole.CASE_MANAGER)
    finders = [
        make(
            ReporterParticipant,
            attributed_to=actor_id,
            context=case.id_,
        )
        for actor_id in (_PROPOSER, _OTHER)
    ]
    if other_is_case_manager:
        finders[1].add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [manager.id_, *(f.id_ for f in finders)]
    case.actor_participant_index = {
        manager_roster_id: manager.id_,
        _PROPOSER: finders[0].id_,
        _OTHER: finders[1].id_,
    }
    dl.create(case)
    for participant in (manager, *finders):
        dl.create(participant)

    embargo = make(
        as_EmbargoEvent, context=case.id_, end_time=days_from_now(30)
    )
    proposal = em_propose_embargo_activity(
        embargo=embargo, context=case.id_, actor=_PROPOSER, to=[_MANAGER]
    )
    dl.create(embargo)
    dl.create(proposal)
    record_pending_assertion(
        _PROPOSER, case.id_, _INVITE, proposal.id_, at=now_utc()
    )
    return dl, case, proposal


def _reject_event(
    dl: SqliteDataLayer,
    proposal: as_Invite,
    case_id: str,
    rejecting_actor_id: str,
) -> RejectInviteToEmbargoOnCaseReceivedEvent:
    reject = em_reject_embargo_activity(
        proposal=proposal,
        context=case_id,
        actor=rejecting_actor_id,
        to=[_PROPOSER],
    )
    return cast(
        RejectInviteToEmbargoOnCaseReceivedEvent,
        received_event(reject, at=dl).model_copy(
            update={"receiving_actor_id": _PROPOSER}
        ),
    )


def _receive_reject(
    dl: SqliteDataLayer,
    proposal: as_Invite,
    case_id: str,
    rejecting_actor_id: str,
) -> None:
    event = _reject_event(dl, proposal, case_id, rejecting_actor_id)
    run_in_act(
        RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, wire_render_port=As2WireRenderAdapter()
        )
    )


def _pending(case_id: str, proposal_id: str) -> bool:
    return get_pending_assertion_store(_PROPOSER).is_suppressed(
        case_id,
        _INVITE,
        proposal_id,
        at=now_utc(),
    )


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("SYNC-11-003")
@pytest.mark.spec("EP-09-014")
@pytest.mark.spec("EP-09-019")
@pytest.mark.spec("CLP-05-009")
def test_case_managers_reject_closes_the_pending_proposal() -> None:
    dl, case, proposal = _proposer_with_pending_proposal()
    assert _pending(case.id_, proposal.id_)

    _receive_reject(dl, proposal, case.id_, _MANAGER)

    assert not _pending(case.id_, proposal.id_)


@pytest.mark.spec("EP-09-017")
@pytest.mark.spec("ARCH-24-008")
def test_participants_reject_leaves_the_proposal_pending() -> None:
    """A participant holding no role is not the authority: its Reject
    leaves the ask pending.

    Called below the use case's door guards, which refuse ``_OTHER`` on
    grounds of their own (it is not the Invite's invitee, EP-09-010);
    through the use case this would pass whatever the authority check said.
    """
    dl, case, proposal = _proposer_with_pending_proposal()
    assert _pending(case.id_, proposal.id_)

    close_refused_embargo_ask(
        dl,
        _reject_event(dl, proposal, case.id_, _OTHER),
        at=now_utc(),
    )

    assert _pending(case.id_, proposal.id_)


@pytest.mark.spec("EP-09-019")
@pytest.mark.spec("OID-01-006")
@pytest.mark.spec("ARCH-24-008")
def test_a_slash_spelled_managers_reject_closes_the_pending_proposal() -> None:
    """The roster spells the manager with a trailing slash; its Reject still
    closes the ask.

    The sender id is normalised at extraction and the roster's
    ``attributed_to`` is not (OID-01-007), so the two spellings meet here.
    They name one actor (OID-01-006): the manager's refusal is still the
    manager's, and the proposer must not keep waiting on an ask that was
    refused (#5924).
    """
    dl, case, proposal = _proposer_with_pending_proposal(
        manager_roster_id=_MANAGER + "/"
    )
    assert resolve_case_manager_id(case, dl) == _MANAGER + "/"
    assert _pending(case.id_, proposal.id_)

    _receive_reject(dl, proposal, case.id_, _MANAGER)

    assert not _pending(case.id_, proposal.id_)


@pytest.mark.spec("EP-09-017")
@pytest.mark.spec("EP-09-019")
@pytest.mark.spec("ARCH-24-008")
@pytest.mark.parametrize(
    ("rejecting_actor_id", "closes"),
    [(_MANAGER, True), (_OTHER, False)],
    ids=["resolved-manager", "second-holder"],
)
def test_a_reject_closes_the_ask_only_from_the_resolved_manager(
    rejecting_actor_id: str, closes: bool
) -> None:
    """Two holders of the role on the roster: only the resolver's answer is
    the authority whose Reject closes the ask (ARCH-24-001, ARCH-24-006).

    Called below the use case's door guards, which refuse ``_OTHER`` on
    grounds of their own (it is not the Invite's invitee, EP-09-010); through
    the use case the second holder's arm would pass whatever the authority
    check said.
    """
    dl, case, proposal = _proposer_with_pending_proposal(
        other_is_case_manager=True
    )
    assert resolve_case_manager_id(case, dl) == _MANAGER
    assert _pending(case.id_, proposal.id_)

    close_refused_embargo_ask(
        dl,
        _reject_event(dl, proposal, case.id_, rejecting_actor_id),
        at=now_utc(),
    )

    assert _pending(case.id_, proposal.id_) is not closes


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("SYNC-11-005")
@pytest.mark.spec("EMB-02-004")
@pytest.mark.parametrize("overdue", [False, True], ids=["pending", "overdue"])
def test_the_managers_reject_judges_the_pending_accept_at_the_acts_instant(
    overdue: bool,
) -> None:
    """The Reject closes the Accept the participant still waits on at the
    act's instant, and reads no clock to judge it (ADR-0176).

    The pending Accept times out exactly *timeout* after it was emitted, so
    an act a microsecond before that clears it and an act at that instant
    finds it already timed out (SYNC-11-005).  Both act instants are
    minutes past the wall clock, so a lookup that read the clock would find
    the Accept still pending and clear it in the overdue arm.
    """
    dl, case, proposal = _proposer_with_pending_proposal()
    store = get_pending_assertion_store(_PROPOSER)
    record_pending_assertion(
        _PROPOSER,
        case.id_,
        _ACCEPT,
        f"{case.id_}/activities/pending-accept",
        subject_id=proposal.id_,
        at=now_utc(),
    )
    emitted = now_utc()
    accept = store.pending_for_subject(
        case.id_, _ACCEPT, proposal.id_, at=emitted
    )
    assert accept is not None
    deadline = accept.emitted_at + timedelta(seconds=store.timeout_seconds)
    at = deadline if overdue else deadline - timedelta(microseconds=1)
    event = _reject_event(dl, proposal, case.id_, _MANAGER)
    use_case = RejectInviteToEmbargoOnCaseReceivedUseCase(
        dl, event, wire_render_port=As2WireRenderAdapter()
    )

    with recorded_clock_reads() as clock_reads:
        run_in_act(use_case, at=at)

    assert clock_reads == []
    assert accept.status == ("timed_out" if overdue else "cleared")
    assert not _pending(case.id_, proposal.id_)
