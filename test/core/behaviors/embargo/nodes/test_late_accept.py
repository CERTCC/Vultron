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

"""The routing of a late embargo Accept (EMB-17, nodes/late_accept.py).

:func:`late_accept_route` names the arm; :class:`LateAcceptRouteIsNode` is
each arm's condition, read from the case when the node runs; and
:class:`ReinviteLateAccepterNode` invites the accepter to the case's terms —
its Active Embargo, or else its earliest-expiring live open proposal —
unless the accepter has already been asked about them or has answered.
"""

from datetime import UTC, datetime, timedelta

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from test.support.embargo_register import propose, reject, write_consent_rows
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.late_accept import (
    LateAcceptRoute,
    LateAcceptRouteIsNode,
    late_accept_route,
    late_accept_terms,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteLateAccepterNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_NOW = datetime.now(tz=UTC)

_R = LateAcceptRoute


@pytest.mark.spec("EMB-17-001")
@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("EMB-17-012")
@pytest.mark.parametrize(
    ("em_state", "answerable", "has_terms", "route"),
    [
        # The case can answer the accepted embargo: its Active Embargo or
        # one of its open proposals (MSM-07-003).
        (EM.PROPOSED, True, True, _R.HONOUR),
        (EM.ACTIVE, True, True, _R.HONOUR),
        (EM.REVISE, True, True, _R.HONOUR),
        # It cannot, but holds terms to invite to.
        (EM.PROPOSED, False, True, _R.REINVITE),
        (EM.ACTIVE, False, True, _R.REINVITE),
        (EM.REVISE, False, True, _R.REINVITE),
        # Under proposal, but every open proposal's embargo has ended.
        (EM.PROPOSED, False, False, _R.UNBOUND),
        # No embargo and no proposal: nothing to bind, whatever is asked.
        (EM.EXITED, False, False, _R.UNBOUND),
        (EM.EXITED, True, True, _R.UNBOUND),
        (EM.NONE, False, False, _R.UNBOUND),
        (EM.NONE, True, True, _R.UNBOUND),
    ],
)
def test_each_case_state_has_one_route(
    em_state, answerable, has_terms, route
) -> None:
    assert (
        late_accept_route(em_state, answerable=answerable, has_terms=has_terms)
        is route
    )


def _run(
    dl: SqliteDataLayer,
    node: py_trees.behaviour.Behaviour,
    actor_id: str = CASE_MANAGER_ACTOR,
    *,
    with_factory: bool = False,
) -> Status:
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl) if with_factory else None,
        sync_port=SyncActivityAdapter(dl) if with_factory else None,
    ).execute_with_setup(tree=tree, actor_id=actor_id)
    return node.status


def _case(
    suffix: str,
    em_state: EM = EM.ACTIVE,
    *,
    other_consent=EmbargoConsentState.AGREED,
) -> tuple[VulnerabilityCase, SqliteDataLayer]:
    """A fixture case whose register's embargoes are stored, as in production.

    The re-invite reads the embargo it names, to order the proposals and to
    stamp the Invite's RSVP deadline (EP-08-002, CM-28-012).
    """
    case, _, dl = make_case_with_manager(
        suffix, em_state, other_consent=other_consent
    )
    for entry in case.embargo_register:
        if isinstance(entry.embargo, EmbargoEvent):
            dl.save(entry.embargo)
    return case, dl


def _with_proposals(
    case: VulnerabilityCase,
    dl: SqliteDataLayer,
    *ends: tuple[str, datetime],
    rejected: tuple[str, ...] = (),
) -> dict[str, str]:
    """Propose an embargo per (*suffix*, *end*), store it, reject *rejected*.

    Returns each suffix's embargo id.  Each proposal is stored, so the
    re-invite can read and order it, and every participant gets its row.
    """
    ids: dict[str, str] = {}
    for suffix, end in ends:
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/{suffix}",
            context=case.id_,
            end_time=end,
        )
        dl.create(embargo)
        propose(case, embargo)
        ids[suffix] = embargo.id_
    for suffix in rejected:
        reject(case, ids[suffix])
    dl.save(case)
    write_consent_rows(dl, case)
    return ids


def _set_row(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    embargo_id: str,
    state: EmbargoConsentState,
) -> None:
    """Give the accepter a *state* row for *embargo_id*, outside the ledger."""
    record = dl.read(case.actor_participant_index[OTHER_PARTICIPANT_ACTOR])
    assert isinstance(record, CaseParticipant)
    rows = [
        EmbargoConsent(embargo_id=embargo_id, state=state)
        if row.embargo_id == embargo_id
        else row
        for row in record.embargo_consents
    ]
    dl.save(record.model_copy(update={"embargo_consents": rows}))


def _invited_embargo_ids(dl: SqliteDataLayer) -> list[str]:
    """The embargo each queued Invite names (the ledger fan-out aside)."""
    ids = []
    for activity_id in dl.outbox_list():
        body = read_sealed_body_dict(dl, activity_id)
        assert body is not None
        if body.get("type") != "Invite":
            continue
        obj = body["object"]
        ids.append(obj["id"] if isinstance(obj, dict) else obj)
    return ids


def _reinvite(case: VulnerabilityCase) -> ReinviteLateAccepterNode:
    return ReinviteLateAccepterNode(
        case_id=case.id_, invitee_id=OTHER_PARTICIPANT_ACTOR, now=_NOW
    )


def _route_node(
    case: VulnerabilityCase, embargo_id: str, route: LateAcceptRoute
) -> LateAcceptRouteIsNode:
    return LateAcceptRouteIsNode(
        case_id=case.id_,
        embargo_id=embargo_id,
        accepting_actor_id=OTHER_PARTICIPANT_ACTOR,
        route=route,
        now=_NOW,
    )


@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-012")
def test_an_accepted_open_proposal_is_honoured() -> None:
    case, dl = _case("late-honour-proposal", EM.PROPOSED)
    (proposal_id,) = case.proposed_embargo_ids

    assert _run(dl, _route_node(case, proposal_id, _R.HONOUR)) is (
        Status.SUCCESS
    )


@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-012")
def test_an_accepted_open_revision_is_honoured() -> None:
    """EM ``REVISE``: the open revision is answerable beside the embargo in force."""
    case, dl = _case("late-honour-revision", EM.REVISE)
    (revision_id,) = case.proposed_embargo_ids

    assert _run(dl, _route_node(case, revision_id, _R.HONOUR)) is (
        Status.SUCCESS
    )


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("EMB-17-012")
@pytest.mark.spec("EP-08-002")
def test_a_rejected_proposal_beside_open_ones_reinvites_to_the_earliest():
    """No Active Embargo: the re-invite names the earliest-expiring proposal.

    The later-ending proposal is recorded first, so arrival order would pick
    it (EP-08-002); the comparator picks the one that ends first.
    """
    case, dl = _case("late-reinvite-earliest", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("long", _NOW + timedelta(days=90)),
        ("short", _NOW + timedelta(days=30)),
        rejected=("old",),
    )
    assert case.em_state == EM.PROPOSED

    assert _run(dl, _route_node(case, ids["old"], _R.REINVITE)) is (
        Status.SUCCESS
    )
    assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
    assert _invited_embargo_ids(dl) == [ids["short"]]
    record = dl.read(case.actor_participant_index[OTHER_PARTICIPANT_ACTOR])
    assert isinstance(record, CaseParticipant)
    assert record.consent_for(ids["short"]) == EmbargoConsentState.INVITED
    assert record.consent_for(ids["long"]) == EmbargoConsentState.UNINVITED


@pytest.mark.spec("EMB-17-003")
def test_the_active_embargo_is_invited_to_before_any_proposal() -> None:
    case, dl = _case("late-reinvite-active", EM.ACTIVE, other_consent=None)
    active_id = case.active_embargo_id
    assert active_id is not None
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("shorter", _NOW + timedelta(days=1)),
        rejected=("old",),
    )

    assert _run(dl, _route_node(case, ids["old"], _R.REINVITE)) is (
        Status.SUCCESS
    )
    assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
    assert _invited_embargo_ids(dl) == [active_id]


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("EP-07-006")
def test_a_proposal_whose_embargo_has_ended_is_not_invited_to() -> None:
    """Only a live proposal is terms: an ended one cannot carry an RSVP deadline.

    The earliest-ending proposal has already ended, so the re-invite skips
    it for the live one; with no live proposal the case holds nothing to
    invite to, and the Accept takes the no-op arm.
    """
    case, dl = _case("late-reinvite-ended", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("ended", _NOW - timedelta(days=1)),
        ("live", _NOW + timedelta(days=60)),
        rejected=("old",),
    )

    assert late_accept_terms(dl, case, _NOW) == ids["live"]
    assert late_accept_terms(dl, case, _NOW + timedelta(days=61)) is None
    assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
    assert _invited_embargo_ids(dl) == [ids["live"]]


@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("EMB-17-007")
def test_a_case_whose_only_proposal_has_ended_binds_nothing() -> None:
    case, dl = _case("late-unbound-ended", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("ended", _NOW - timedelta(seconds=1)),
        rejected=("old",),
    )
    assert case.em_state == EM.PROPOSED

    for route in LateAcceptRoute:
        expected = Status.SUCCESS if route is _R.UNBOUND else Status.FAILURE
        assert _run(dl, _route_node(case, ids["old"], route)) is expected


@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-003")
@pytest.mark.parametrize("route", list(LateAcceptRoute))
def test_the_condition_holds_only_for_the_cases_route(route) -> None:
    case, dl = _case(f"late-route-{route.value}")
    embargo_id = case.active_embargo_id
    assert embargo_id is not None

    status = _run(dl, _route_node(case, embargo_id, route))

    expected = Status.SUCCESS if route is _R.HONOUR else Status.FAILURE
    assert status is expected


class TestReinviteLateAccepterNode:
    @pytest.mark.spec("EMB-17-003")
    def test_a_case_under_proposal_reinvites_to_its_open_proposal(
        self,
    ) -> None:
        case, dl = _case(
            "late-reinvite-proposal", EM.PROPOSED, other_consent=None
        )
        (proposal_id,) = case.proposed_embargo_ids

        assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
        assert _invited_embargo_ids(dl) == [proposal_id]

    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("EMB-17-007")
    def test_no_terms_to_invite_to_is_a_failure(self, caplog) -> None:
        """EM ``EXITED``: the route never sends a late Accept here (ARCH-15).

        Reaching the re-invite with no terms is a routing bug, so the node
        reports it as a FAILURE rather than a silent SUCCESS, and sends no
        invitation (EMB-17-007).
        """
        case, dl = _case("late-reinvite-none", EM.EXITED)

        with caplog.at_level("ERROR"):
            status = _run(dl, _reinvite(case), with_factory=True)

        assert status is Status.FAILURE
        assert "no terms to invite" in caplog.text
        assert dl.outbox_list() == []

    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize(
        "state", [EmbargoConsentState.INVITED, EmbargoConsentState.AGREED]
    )
    def test_an_accepter_already_asked_or_answered_is_not_asked_again(
        self, state, caplog
    ) -> None:
        """A row that takes no ``INVITE`` is not re-invited (EP-09-011 shape)."""
        case, dl = _case(
            f"late-reinvite-skip-{state.value.lower()}",
            EM.PROPOSED,
            other_consent=None,
        )
        (proposal_id,) = case.proposed_embargo_ids
        _set_row(dl, case, proposal_id, state)

        with caplog.at_level("INFO"):
            status = _run(dl, _reinvite(case), with_factory=True)

        assert status is Status.SUCCESS
        assert f"already {state}" in caplog.text
        assert dl.outbox_list() == []

    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize(
        "state",
        [
            EmbargoConsentState.UNINVITED,
            EmbargoConsentState.DECLINED,
            EmbargoConsentState.TIMED_OUT,
        ],
    )
    def test_an_accepter_inviting_can_move_is_invited(self, state) -> None:
        """``INVITE`` moves the row, so the accepter is asked (EMB-17-003)."""
        case, dl = _case(
            f"late-reinvite-ask-{state.value.lower()}",
            EM.PROPOSED,
            other_consent=None,
        )
        (proposal_id,) = case.proposed_embargo_ids
        _set_row(dl, case, proposal_id, state)

        assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
        assert _invited_embargo_ids(dl) == [proposal_id]
        record = dl.read(case.actor_participant_index[OTHER_PARTICIPANT_ACTOR])
        assert isinstance(record, CaseParticipant)
        assert record.consent_for(proposal_id) == EmbargoConsentState.INVITED

    @pytest.mark.spec("EMB-17-003")
    def test_an_accepter_with_no_record_is_a_failure(self) -> None:
        """The manager holds its own roster (Regime 1, ADR-0087): no guess."""
        case, dl = _case("late-reinvite-norecord", EM.PROPOSED)
        node = ReinviteLateAccepterNode(
            case_id=case.id_,
            invitee_id="https://example.org/actors/stranger",
            now=_NOW,
        )

        assert _run(dl, node, with_factory=True) is Status.FAILURE
        assert dl.outbox_list() == []

    @pytest.mark.spec("EMB-17-003")
    def test_no_port_sends_nothing(self, caplog) -> None:
        case, dl = _case("late-reinvite-noport")

        with caplog.at_level("WARNING"):
            status = _run(dl, _reinvite(case))

        assert status is Status.SUCCESS
        assert "trigger_activity unavailable" in caplog.text
        assert dl.outbox_list() == []
