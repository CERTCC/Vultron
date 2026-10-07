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
"""A participant that joins during a revision is invited to it (EP-09-011).

The CASE_MANAGER relays a revision to the participants on the roster when it is
proposed (EP-09-002).  A joiner seated afterwards signs the embargo in force but
was never asked about the revision, so it would lapse on arrival if the owner
activated longer terms.  The admission therefore ends by relaying every open
proposal to the joiner.
"""

from typing import cast

import pytest

from test.core.use_cases.received.test_embargo_revision_relay import (
    MANAGER,
    PROPOSER,
    _active_case_with_revision,
    _active_id,
    _consent_of,
    _deliver,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received.actor.invite import (
    AcceptInviteActorToCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

JOINER = "https://example.org/users/joiner"


def _relayed_to(dl: SqliteDataLayer, actor_id: str) -> list[VultronActivity]:
    """The embargo Invites relayed to *actor_id* (not the full-case Invite).

    The full-case Invite (CM-11-010) is also an Invite to the joiner; it
    carries the CASE_MANAGER's ledger position in ``content`` and is not a
    relayed proposal (EP-09-011).
    """
    return [
        a
        for a in (cast(VultronActivity, dl.read(i)) for i in dl.outbox_list())
        if a.type_ == "Invite"
        and (a.to or []) == [actor_id]
        and "logIndex" not in str(a.content or "")
    ]


def _join(dl: SqliteDataLayer, case_id: str, make_payload):
    invite = rm_invite_to_case_activity(
        as_Actor(id_=JOINER),
        to=[JOINER],
        target=case_id,
        actor=MANAGER,
        roles=[CVDRole.VENDOR],
        id_=f"{case_id}/invitations/joiner",
    )
    dl.create(invite)
    event = make_payload(
        rm_accept_invite_to_case_activity(invite, actor=JOINER)
    )
    return AcceptInviteActorToCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _open_revision(case_id: str, make_payload):
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )
    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)
    return dl, revision


@pytest.mark.spec("EP-09-011")
def test_joiner_during_revise_is_invited_to_the_open_revision(make_payload):
    """AC-1: one committed Invite for the revision, attributed to its proposer."""
    case_id = "https://example.org/cases/joiner-relay"
    dl, revision = _open_revision(case_id, make_payload)
    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.REVISE)

    result = _join(dl, case_id, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED
    invites = _relayed_to(dl, JOINER)
    assert len(invites) == 1
    assert invites[0].actor == MANAGER
    assert invites[0].attributed_to == PROPOSER
    committed = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.log_object_id == invites[0].id_
    ]
    assert len(committed) == 1
    # The joiner signs the terms in force and is asked about the revision.
    assert (
        _consent_of(dl, case_id, JOINER, _active_id(dl, case_id))
        is EmbargoConsentState.ACCEPTED
    )
    assert (
        _consent_of(dl, case_id, JOINER, revision.id_)
        is EmbargoConsentState.INVITED
    )


@pytest.mark.spec("EP-09-011")
def test_joiner_without_an_open_proposal_gets_no_embargo_invite(make_payload):
    """No proposal on the table, so nothing is relayed."""
    case_id = "https://example.org/cases/joiner-no-relay"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )

    result = _join(dl, case_id, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED
    assert _relayed_to(dl, JOINER) == []


@pytest.mark.spec("EP-09-011")
@pytest.mark.spec("EP-09-004")
def test_joiner_that_accepts_the_relayed_revision_holds_its_consent(
    make_payload,
):
    """AC-2: the joiner's Accept lands on the revision's row, A's row is kept.

    A row ``ACCEPTED`` for the revision is what makes the joiner a signatory of
    it when the owner activates it (EP-05-001).
    """
    from vultron.core.use_cases.received.embargo import (
        AcceptInviteToEmbargoOnCaseReceivedUseCase,
    )
    from vultron.wire.as2.factories import em_accept_embargo_activity

    case_id = "https://example.org/cases/joiner-accepts"
    dl, revision = _open_revision(case_id, make_payload)
    _join(dl, case_id, make_payload)
    (relayed,) = _relayed_to(dl, JOINER)
    active_before = _active_id(dl, case_id)

    accept = em_accept_embargo_activity(
        proposal=cast(as_Invite, relayed),
        context=case_id,
        actor=JOINER,
        to=[MANAGER],
    )
    AcceptInviteToEmbargoOnCaseReceivedUseCase(
        dl,
        make_payload(accept, receiving_actor_id=MANAGER),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()

    assert (
        _consent_of(dl, case_id, JOINER, revision.id_)
        is EmbargoConsentState.ACCEPTED
    )
    assert (
        _consent_of(dl, case_id, JOINER, active_before)
        is EmbargoConsentState.ACCEPTED
    )


def _run_relay_again(dl: SqliteDataLayer, case_id: str):
    from test.core.behaviors.bt_harness import BTTestScenario
    from vultron.core.behaviors.case.nodes.invite_revision_relay import (
        RelayOpenProposalsToJoinerNode,
    )

    scenario = BTTestScenario(actor_id=MANAGER, dl=dl)
    return scenario.run(
        RelayOpenProposalsToJoinerNode(case_id=case_id, invitee_id=JOINER)
    )


@pytest.mark.spec("EP-09-011")
def test_a_rerun_of_the_relay_does_not_invite_the_joiner_twice(make_payload):
    """The joiner's row for the proposal is the latch: a re-run sends nothing."""
    case_id = "https://example.org/cases/joiner-rerun"
    dl, _ = _open_revision(case_id, make_payload)
    _join(dl, case_id, make_payload)
    assert len(_relayed_to(dl, JOINER)) == 1

    result = _run_relay_again(dl, case_id)

    assert result.status.name == "SUCCESS"
    assert len(_relayed_to(dl, JOINER)) == 1


@pytest.mark.spec("EP-09-011")
def test_every_open_proposal_is_relayed_to_the_joiner(make_payload):
    """Two counter-proposals are open, so the joiner gets two Invites."""
    case_id = "https://example.org/cases/joiner-two-proposals"
    dl, _ = _open_revision(case_id, make_payload)
    second = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/second",
        content="Even longer terms",
        context=case_id,
        end_time=days_from_now_utc(120),
    )
    dl.create(second)
    counter = em_propose_embargo_activity(
        second,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/second",
    )
    _deliver(dl, counter, make_payload, receiving_actor_id=MANAGER)

    _join(dl, case_id, make_payload)

    invites = _relayed_to(dl, JOINER)
    assert len(invites) == 2
    assert all(a.attributed_to == PROPOSER for a in invites)
    for embargo_id in (second.id_, f"{case_id}/embargo_events/revision"):
        assert (
            _consent_of(dl, case_id, JOINER, embargo_id)
            is EmbargoConsentState.INVITED
        )


@pytest.mark.spec("EP-09-011")
def test_an_open_proposal_with_no_committed_entry_is_an_internal_error(
    make_payload,
):
    """The manager cannot name the proposer, so it raises instead of skipping."""
    case_id = "https://example.org/cases/joiner-unknown-proposer"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    _join(dl, case_id, make_payload)
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.proposed_embargoes = [f"{case_id}/embargo_events/ghost"]
    dl.save(case)

    result = _run_relay_again(dl, case_id)

    assert result.status.name == "FAILURE"
    assert result.internal_error
