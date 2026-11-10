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

"""An embargo Accept is answered by availability (MSM-07-012, EMB-17).

:func:`embargo_availability` is the one test, read on the on-time and the
late path alike; :func:`available_terms` names the terms a refused accepter
is re-invited to; :class:`EmbargoAvailabilityIsNode` and
:class:`CaseHoldsAvailableTermsNode` are the conditions of the Accept tree's
diversions; and :class:`ReinviteRefusedAccepterNode` invites a refused
accepter to the case's terms unless it has already been asked about them or
has answered.
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
from test.support.act_runner import run_tree
from test.support.embargo_register import propose, reject, write_consent_rows
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.accept_availability import (
    CaseHoldsAvailableTermsNode,
    EmbargoAvailabilityIsNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteRefusedAccepterNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.services.embargo_availability import (
    EmbargoAvailability,
    available_terms,
    embargo_availability,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_NOW = datetime.now(tz=UTC)

_A = EmbargoAvailability


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
    run_tree(
        BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl)
            if with_factory
            else None,
            sync_port=SyncActivityAdapter(dl) if with_factory else None,
        ),
        tree=tree,
        actor_id=actor_id,
        at=_NOW,
    )
    return node.status


def _case(
    suffix: str,
    em_state: EM = EM.ACTIVE,
    *,
    other_consent: EmbargoConsentState | None = EmbargoConsentState.AGREED,
) -> tuple[VulnerabilityCase, SqliteDataLayer]:
    """A fixture case whose register's embargoes are all stored.

    The availability test reads each answerable embargo's end time, and the
    re-invite reads the embargo it names to stamp the Invite's RSVP deadline
    (EP-08-002, CM-28-012).  A revision the fixture names by id alone is
    stored too, ending later than the embargo in force.
    """
    case, _, dl = make_case_with_manager(
        suffix, em_state, other_consent=other_consent
    )
    for entry in case.embargo_register:
        embargo = entry.embargo
        if not isinstance(embargo, EmbargoEvent):
            embargo = as_EmbargoEvent(
                id_=embargo,
                context=case.id_,
                end_time=_NOW + timedelta(days=90),
            )
        dl.save(embargo)
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


def _end_active_embargo(
    case: VulnerabilityCase, dl: SqliteDataLayer, end: datetime
) -> str:
    """Move the end time of *case*'s Active Embargo to *end*, in both copies.

    The register carries the object and the store holds it; both read the
    new end time.  The entry stays ``ACTIVE``: the clock has not ended it.
    """
    active_id = case.active_embargo_id
    assert active_id is not None
    stored = dl.read(active_id)
    assert isinstance(stored, EmbargoEvent)
    ended = stored.model_copy(update={"end_time": end})
    dl.save(ended)
    case.embargo_register = [
        entry.model_copy(update={"embargo": ended})
        if entry.embargo_id == active_id
        else entry
        for entry in case.embargo_register
    ]
    dl.save(case)
    return active_id


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


def _reinvite(case: VulnerabilityCase) -> ReinviteRefusedAccepterNode:
    return ReinviteRefusedAccepterNode(
        case_id=case.id_, invitee_id=OTHER_PARTICIPANT_ACTOR
    )


def _is(
    case: VulnerabilityCase, embargo_id: str, availability: EmbargoAvailability
) -> EmbargoAvailabilityIsNode:
    return EmbargoAvailabilityIsNode(
        case_id=case.id_,
        embargo_id=embargo_id,
        availability=availability,
    )


# ---------------------------------------------------------------------------
# The one test (MSM-07-012)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-07-012")
@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-012")
@pytest.mark.parametrize("em_state", [EM.PROPOSED, EM.ACTIVE, EM.REVISE])
def test_the_active_embargo_and_open_proposals_are_available(em_state):
    case, dl = _case(f"avail-{em_state.name.lower()}", em_state)
    answerable = [
        *([case.active_embargo_id] if case.active_embargo_id else []),
        *case.proposed_embargo_ids,
    ]
    assert answerable

    for embargo_id in answerable:
        assert embargo_availability(dl, case, embargo_id, _NOW) is (
            _A.AVAILABLE
        )


@pytest.mark.spec("MSM-07-012")
@pytest.mark.spec("EMB-17-004")
def test_a_terminated_embargo_is_held_but_unavailable() -> None:
    case, dl = _case("avail-exited", EM.EXITED)
    (entry,) = case.embargo_register

    assert embargo_availability(dl, case, entry.embargo_id, _NOW) is (
        _A.UNAVAILABLE
    )


@pytest.mark.spec("MSM-07-012")
def test_a_rejected_proposal_is_held_but_unavailable() -> None:
    case, dl = _case("avail-rejected", EM.NONE)
    ids = _with_proposals(
        case, dl, ("old", _NOW + timedelta(days=20)), rejected=("old",)
    )

    assert embargo_availability(dl, case, ids["old"], _NOW) is _A.UNAVAILABLE


@pytest.mark.spec("MSM-07-039")
def test_an_embargo_the_register_never_held_is_never_held() -> None:
    case, dl = _case("avail-never")

    found = embargo_availability(
        dl, case, f"{case.id_}/embargo_events/never-proposed", _NOW
    )

    assert found is _A.NEVER_HELD


@pytest.mark.spec("MSM-07-012")
@pytest.mark.spec("EMB-17-002")
@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(hours=1), _A.AVAILABLE),
        # An embargo reaches its end time at that instant (ADR-0122).
        (timedelta(0), _A.UNAVAILABLE),
        (-timedelta(seconds=1), _A.UNAVAILABLE),
    ],
    ids=["before-end-time", "at-end-time", "after-end-time"],
)
def test_an_active_embargo_past_its_end_time_is_unavailable(
    offset, expected
) -> None:
    """The clock has not terminated it, but its end time decides (AC-3)."""
    case, dl = _case(f"avail-ended-{offset.total_seconds():.0f}")
    active_id = _end_active_embargo(case, dl, _NOW + offset)
    assert case.active_embargo_id == active_id

    assert embargo_availability(dl, case, active_id, _NOW) is expected


@pytest.mark.spec("MSM-07-012")
def test_an_open_proposal_past_its_end_time_is_unavailable() -> None:
    case, dl = _case("avail-proposal-ended", EM.NONE)
    ids = _with_proposals(case, dl, ("ended", _NOW - timedelta(days=1)))

    assert embargo_availability(dl, case, ids["ended"], _NOW) is (
        _A.UNAVAILABLE
    )


@pytest.mark.spec("EMB-18-003")
def test_an_unreadable_answerable_embargo_is_an_internal_error() -> None:
    """A proposal the manager's own store cannot read is its own fault.

    It raises rather than reading as available or not, so no Accept is ever
    answered on a store fault (EMB-18-003).
    """
    case, dl = _case("avail-unreadable", EM.NONE)
    missing = f"{case.id_}/embargo_events/missing"
    propose(case, missing)
    dl.save(case)

    with pytest.raises(RuntimeError, match="cannot read"):
        embargo_availability(dl, case, missing, _NOW)
    with pytest.raises(RuntimeError, match="cannot read"):
        available_terms(dl, case, _NOW)


# ---------------------------------------------------------------------------
# The terms a refused accepter is re-invited to (EMB-17-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("EP-08-002")
def test_the_terms_are_the_earliest_ending_live_proposal() -> None:
    """No Active Embargo: the earliest-ending available proposal.

    The later-ending proposal is recorded first, so arrival order would pick
    it (EP-08-002); the comparator picks the one that ends first, and skips
    the one whose embargo has already ended (EP-07-006).
    """
    case, dl = _case("terms-earliest", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("long", _NOW + timedelta(days=90)),
        ("ended", _NOW - timedelta(days=1)),
        ("short", _NOW + timedelta(days=30)),
        rejected=("old",),
    )

    assert available_terms(dl, case, _NOW) == ids["short"]
    # An embargo has ended at its end time, not only after it (ADR-0122).
    assert available_terms(dl, case, _NOW + timedelta(days=90)) is None


@pytest.mark.spec("EMB-17-003")
def test_the_active_embargo_is_the_terms_before_any_proposal() -> None:
    case, dl = _case("terms-active", EM.ACTIVE, other_consent=None)
    _with_proposals(case, dl, ("shorter", _NOW + timedelta(days=1)))

    assert available_terms(dl, case, _NOW) == case.active_embargo_id


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("MSM-07-012")
def test_an_active_embargo_past_its_end_time_is_no_terms() -> None:
    """An ended embargo in force is skipped for a live revision of it."""
    case, dl = _case("terms-active-ended", EM.ACTIVE)
    ids = _with_proposals(case, dl, ("revision", _NOW + timedelta(days=30)))
    _end_active_embargo(case, dl, _NOW - timedelta(hours=1))

    assert available_terms(dl, case, _NOW) == ids["revision"]


@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("EMB-17-007")
@pytest.mark.parametrize("em_state", [EM.EXITED, EM.NONE])
def test_a_case_with_no_active_or_proposed_embargo_holds_no_terms(em_state):
    case, dl = _case(f"terms-none-{em_state.name.lower()}", em_state)

    assert available_terms(dl, case, _NOW) is None
    assert (
        _run(dl, CaseHoldsAvailableTermsNode(case_id=case.id_))
        is Status.FAILURE
    )


# ---------------------------------------------------------------------------
# The conditions of the Accept tree's diversions
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-07-012")
@pytest.mark.spec("MSM-07-039")
@pytest.mark.parametrize("availability", list(EmbargoAvailability))
def test_the_condition_holds_only_for_the_embargos_availability(
    availability,
) -> None:
    case, dl = _case(f"avail-node-{availability.value}", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("open", _NOW + timedelta(days=30)),
        ("old", _NOW + timedelta(days=20)),
        rejected=("old",),
    )
    named = {
        _A.AVAILABLE: ids["open"],
        _A.UNAVAILABLE: ids["old"],
        _A.NEVER_HELD: f"{case.id_}/embargo_events/never-proposed",
    }

    for found, embargo_id in named.items():
        node = _is(case, embargo_id, availability)
        expected = Status.SUCCESS if found is availability else Status.FAILURE
        assert _run(dl, node) is expected, (found, availability)


@pytest.mark.spec("MSM-07-012")
@pytest.mark.parametrize(
    ("ended", "detail"),
    [(False, "the register holds it REJECTED"), (True, "end time")],
)
def test_the_refusal_reason_names_why_the_embargo_is_unavailable(
    ended, detail
) -> None:
    """The reason is what the refusal notice carries (CLP-05-001)."""
    case, dl = _case(f"avail-reason-{ended}", EM.NONE)
    ids = _with_proposals(
        case,
        dl,
        ("old", _NOW + timedelta(days=20)),
        ("ended", _NOW - timedelta(days=1)),
        rejected=("old",),
    )
    node = _is(case, ids["ended" if ended else "old"], _A.UNAVAILABLE)

    assert _run(dl, node) is Status.SUCCESS
    assert detail in node.feedback_message
    assert "MSM-07-012" in node.feedback_message


@pytest.mark.spec("MSM-07-039")
def test_the_never_held_reason_names_the_fault() -> None:
    case, dl = _case("avail-reason-never")
    node = _is(case, f"{case.id_}/embargo_events/x", _A.NEVER_HELD)

    assert _run(dl, node) is Status.SUCCESS
    assert "never held" in node.feedback_message
    assert "MSM-07-039" in node.feedback_message


@pytest.mark.spec("EMB-17-003")
def test_the_terms_condition_holds_when_the_case_holds_terms() -> None:
    case, dl = _case("terms-node", EM.PROPOSED)

    assert (
        _run(dl, CaseHoldsAvailableTermsNode(case_id=case.id_))
        is Status.SUCCESS
    )


# ---------------------------------------------------------------------------
# The re-invite (EMB-17-003)
# ---------------------------------------------------------------------------


class TestReinviteRefusedAccepterNode:
    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("EP-08-002")
    def test_the_reinvite_names_the_earliest_live_proposal(self) -> None:
        case, dl = _case("reinvite-earliest", EM.NONE)
        ids = _with_proposals(
            case,
            dl,
            ("old", _NOW + timedelta(days=20)),
            ("long", _NOW + timedelta(days=90)),
            ("short", _NOW + timedelta(days=30)),
            rejected=("old",),
        )

        assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
        assert _invited_embargo_ids(dl) == [ids["short"]]
        record = dl.read(case.actor_participant_index[OTHER_PARTICIPANT_ACTOR])
        assert isinstance(record, CaseParticipant)
        assert record.consent_for(ids["short"]) == EmbargoConsentState.INVITED
        assert record.consent_for(ids["long"]) == EmbargoConsentState.UNINVITED

    @pytest.mark.spec("EMB-17-003")
    def test_a_case_under_proposal_reinvites_to_its_open_proposal(
        self,
    ) -> None:
        case, dl = _case("reinvite-proposal", EM.PROPOSED, other_consent=None)
        (proposal_id,) = case.proposed_embargo_ids

        assert _run(dl, _reinvite(case), with_factory=True) is Status.SUCCESS
        assert _invited_embargo_ids(dl) == [proposal_id]

    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.spec("EMB-17-007")
    def test_no_terms_to_invite_to_is_a_failure(self, caplog) -> None:
        """EM ``EXITED``: the tree never sends a refused Accept here (ARCH-15).

        Reaching the re-invite with no terms is a routing bug, so the node
        reports it as a FAILURE rather than a silent SUCCESS, and sends no
        invitation (EMB-17-007).
        """
        case, dl = _case("reinvite-none", EM.EXITED)

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
            f"reinvite-skip-{state.value.lower()}",
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
            f"reinvite-ask-{state.value.lower()}",
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
    def test_an_accepter_with_no_record_is_a_failure(self, caplog) -> None:
        """The manager holds its own roster (Regime 1, ADR-0087): no guess."""
        case, dl = _case("reinvite-norecord", EM.PROPOSED)
        node = ReinviteRefusedAccepterNode(
            case_id=case.id_,
            invitee_id="https://example.org/actors/stranger",
        )

        with caplog.at_level("ERROR"):
            status = _run(dl, node, with_factory=True)

        assert status is Status.FAILURE
        assert "CaseParticipant" in node.feedback_message
        assert "stranger" in caplog.text
        assert dl.outbox_list() == []

    @pytest.mark.spec("EMB-17-003")
    def test_no_port_sends_nothing(self, caplog) -> None:
        case, dl = _case("reinvite-noport")

        with caplog.at_level("WARNING"):
            status = _run(dl, _reinvite(case))

        assert status is Status.SUCCESS
        assert "trigger_activity unavailable" in caplog.text
        assert dl.outbox_list() == []
