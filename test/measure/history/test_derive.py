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

"""Deriving events from hand-built ledgers (CEH-03, CEH-04, CEH-06-005, CEH-06-006).

Each fixture holds a shape no committed recording does: an end-time exit, a
declined or timed-out invitation, a public exploit, a backward state, a
deployer with no Vendor role.
"""

from datetime import datetime

import pytest

from test.measure.history.builders import (
    CM,
    DEPLOYER,
    EMBARGO,
    EMBARGO_2,
    EMBARGO_END,
    INVITEE,
    OWNER,
    REPORTER,
    VENDOR,
    VENDOR_2,
    Ledger,
    case_status,
    consent,
    embargo,
    participant,
    stamp,
    status,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.measure.history import EventKind, GapLabel
from vultron.measure.ledger import Dimension, LedgerSource

_RM_KINDS = (
    EventKind.REPORT_RECEIVED,
    EventKind.REPORT_INVALID,
    EventKind.REPORT_VALID,
    EventKind.REPORT_DEFERRED,
    EventKind.REPORT_ACCEPTED,
    EventKind.REPORT_CLOSED,
)


def _vendor_ledger() -> Ledger:
    """A genesis, then the Case Owner's first act, then a seated vendor."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.seat(
        participant(
            VENDOR,
            [
                status(
                    "vendor-r", VENDOR, "RECEIVED", vf="vf", roles=("VENDOR",)
                )
            ],
            roles=("VENDOR",),
        )
    )
    return ledger


def _kinds(events) -> list:
    return [event.kind for event in events]


# ---------------------------------------------------------------------------
# The two clocks (CEH-03-006 to CEH-03-008)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-03-006")
@pytest.mark.spec("CEH-03-007")
def test_each_clock_is_read_from_its_own_field():
    ledger = _vendor_ledger()
    index = ledger.add_status(
        VENDOR, status("vendor-v", VENDOR, "VALID", vf="vf")
    )
    (event,) = [e for e in ledger.history().events if e.log_index == index]
    assert event.committed_at == datetime.fromisoformat(stamp(index * 2 + 1))
    assert event.claimed_at == datetime.fromisoformat(stamp(index * 2))


@pytest.mark.spec("CEH-03-008")
def test_an_entry_with_no_claimed_time_leaves_the_field_empty():
    ledger = _vendor_ledger()
    index = ledger.add(
        "add_participant_status_to_participant",
        "Add",
        VENDOR,
        status("vendor-v", VENDOR, "VALID", vf="vf"),
        claimed=None,
    )
    (event,) = [e for e in ledger.history().events if e.log_index == index]
    assert event.claimed_at is None
    assert event.committed_at == datetime.fromisoformat(stamp(index * 2 + 1))


@pytest.mark.spec("CEH-04-011")
def test_the_history_follows_log_order_not_claimed_times():
    ledger = _vendor_ledger()
    first = ledger.add(
        "add_participant_status_to_participant",
        "Add",
        VENDOR,
        status("v-v", VENDOR, "VALID", vf="vf"),
        claimed=stamp(900),
    )
    second = ledger.add(
        "add_participant_status_to_participant",
        "Add",
        VENDOR,
        status("v-a", VENDOR, "ACCEPTED", vf="vf"),
        claimed=stamp(100),
    )
    events = [e for e in ledger.history().events if e.log_index >= first]
    assert [(e.kind, e.log_index) for e in events] == [
        (EventKind.REPORT_VALID, first),
        (EventKind.REPORT_ACCEPTED, second),
    ]
    first_claim, second_claim = events[0].claimed_at, events[1].claimed_at
    assert first_claim is not None and second_claim is not None
    assert first_claim > second_claim


# ---------------------------------------------------------------------------
# State comparison (CEH-04-001 to CEH-04-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-04-001")
@pytest.mark.spec("CEH-04-013")
def test_a_status_restating_the_state_reached_yields_no_event():
    ledger = _vendor_ledger()
    first = ledger.add_status(VENDOR, status("v-1", VENDOR, "VALID", vf="vf"))
    again = ledger.add_status(VENDOR, status("v-2", VENDOR, "VALID", vf="vf"))
    history = ledger.history()
    assert _kinds(e for e in history.events if e.log_index == first) == [
        EventKind.REPORT_VALID
    ]
    assert [e for e in history.events if e.log_index == again] == []
    assert history.excluded == []


@pytest.mark.spec("CEH-04-002")
def test_every_report_management_state_entered_is_one_event():
    """Including the deferred and invalid verdicts, in the order entered."""
    ledger = _vendor_ledger()
    ledger.add_status(VENDOR, status("v-i", VENDOR, "INVALID", vf="vf"))
    ledger.add_status(VENDOR, status("v-v", VENDOR, "VALID", vf="vf"))
    ledger.add_status(VENDOR, status("v-d", VENDOR, "DEFERRED", vf="vf"))
    ledger.add_status(VENDOR, status("v-a", VENDOR, "ACCEPTED", vf="vf"))
    ledger.add_status(VENDOR, status("v-c", VENDOR, "CLOSED", vf="vf"))
    events = ledger.history().for_participant(VENDOR)
    assert _kinds(events) == list(_RM_KINDS)


@pytest.mark.spec("CEH-04-003")
def test_awareness_and_readiness_are_separate_events_for_each_vendor():
    ledger = _vendor_ledger()
    ledger.seat(
        participant(
            VENDOR_2,
            [status("v2-r", VENDOR_2, "RECEIVED", vf="Vf", roles=("VENDOR",))],
            roles=("VENDOR",),
        )
    )
    ledger.add_status(VENDOR, status("v-aware", VENDOR, "RECEIVED", vf="Vf"))
    ledger.add_status(VENDOR, status("v-fix", VENDOR, "RECEIVED", vf="VF"))
    ledger.add_status(
        VENDOR_2, status("v2-fix", VENDOR_2, "RECEIVED", vf="VF")
    )
    history = ledger.history()
    for vendor in (VENDOR, VENDOR_2):
        cs = [
            e.kind
            for e in history.for_participant(vendor)
            if e.kind in CSEvent
        ]
        assert cs == [CSEvent.V, CSEvent.F], vendor
    # A vendor reporting awareness and readiness at once yields both, in order.
    jump = Ledger()
    jump.standard_genesis()
    jump.add_status(
        VENDOR, status("j", VENDOR, "RECEIVED", vf="VF", roles=("VENDOR",))
    )
    assert _kinds(
        e for e in jump.history().for_participant(VENDOR) if e.kind in CSEvent
    ) == [CSEvent.V, CSEvent.F]


@pytest.mark.spec("CEH-04-003")
def test_a_fix_path_on_a_participant_without_the_vendor_role_is_no_event():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(
        REPORTER,
        status("r-vf", REPORTER, "ACCEPTED", vf="Vf", roles=("REPORTER",)),
    )
    assert ledger.history().of_kind(CSEvent.V) == []


@pytest.mark.spec("CEH-04-004")
@pytest.mark.spec("CEH-06-006")
def test_a_vendorless_deployer_yields_its_fix_deployed_event():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(
        DEPLOYER,
        status("dep-r", DEPLOYER, "RECEIVED", d="d", roles=("DEPLOYER",)),
    )
    deployed = ledger.add_status(
        DEPLOYER,
        status("dep-d", DEPLOYER, "RECEIVED", d="D", roles=("DEPLOYER",)),
    )
    events = ledger.history().for_participant(DEPLOYER)
    assert _kinds(events) == [EventKind.REPORT_RECEIVED, CSEvent.D]
    assert events[-1].log_index == deployed
    assert CSEvent.V not in _kinds(events)


# ---------------------------------------------------------------------------
# Several events in one entry, and none (CEH-04-011 to CEH-04-013)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-04-012")
@pytest.mark.spec("CEH-04-011")
def test_a_genesis_seating_several_states_yields_one_event_each_in_order():
    history = _vendor_ledger().history()
    cm_events = history.for_participant(CM)
    assert [(e.kind, e.log_index) for e in cm_events[:3]] == [
        (EventKind.REPORT_RECEIVED, 0),
        (EventKind.REPORT_VALID, 0),
        (EventKind.REPORT_ACCEPTED, 0),
    ]
    assert [e.log_index for e in history.events] == sorted(
        e.log_index for e in history.events
    )


@pytest.mark.spec("CEH-04-013")
def test_a_note_and_an_ownership_transfer_yield_no_event():
    ledger = _vendor_ledger()
    note = ledger.add(
        "add_note_to_case",
        "Add",
        OWNER,
        {"id": "urn:uuid:note", "type": "Note"},
    )
    offer = ledger.add(
        "offer_case_ownership_transfer",
        "Offer",
        OWNER,
        {"id": "urn:uuid:case-1", "type": "VulnerabilityCase"},
    )
    accept = ledger.add(
        "accept_case_ownership_transfer",
        "Accept",
        VENDOR,
        {"id": "urn:uuid:activity-offer", "type": "Offer"},
    )
    owner = ledger.add(
        "update_case_owner",
        "Update",
        CM,
        {
            "id": "urn:uuid:case-1",
            "type": "VulnerabilityCase",
            "attributedTo": VENDOR,
            "caseParticipants": [
                participant(
                    OWNER,
                    [
                        status("owner-r", OWNER, "RECEIVED"),
                        status("owner-v", OWNER, "VALID"),
                    ],
                )
            ],
        },
    )
    indices = {e.log_index for e in ledger.history().events}
    assert indices.isdisjoint({note, offer, accept, owner})


# ---------------------------------------------------------------------------
# Recommendations and backward states (CEH-04-014 to CEH-04-016)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-04-014")
def test_a_recommended_participant_yields_no_event_before_its_own_record():
    ledger = Ledger()
    ledger.standard_genesis()
    recommended = participant(
        VENDOR,
        [status("rec-start", VENDOR, "START", vf="vf", roles=("VENDOR",))],
        roles=("VENDOR",),
    )
    offer = ledger.add("offer_case_participant", "Offer", CM, recommended)
    accept = ledger.add(
        "accept_offer_case_participant",
        "Accept",
        OWNER,
        {"id": "urn:uuid:offer", "type": "Offer", "object": recommended},
    )
    own = ledger.seat(
        participant(
            VENDOR,
            [status("own-r", VENDOR, "RECEIVED", vf="Vf", roles=("VENDOR",))],
            roles=("VENDOR",),
        )
    )
    history = ledger.history()
    events = history.for_participant(VENDOR)
    assert {e.log_index for e in events} == {own}
    assert _kinds(events) == [EventKind.REPORT_RECEIVED, CSEvent.V]
    assert not any(e.log_index in (offer, accept) for e in history.events)
    assert history.excluded == []


@pytest.mark.spec("CEH-04-015")
@pytest.mark.spec("CEH-04-016")
def test_a_state_behind_the_one_reached_is_excluded_and_reported():
    ledger = _vendor_ledger()
    ledger.add_status(VENDOR, status("v-a", VENDOR, "ACCEPTED", vf="VF"))
    backward = ledger.add_status(
        VENDOR, status("v-back", VENDOR, "RECEIVED", vf="Vf")
    )
    following = ledger.add_status(
        VENDOR, status("v-c", VENDOR, "CLOSED", vf="VF")
    )
    history = ledger.history()
    assert [e for e in history.events if e.log_index == backward] == []
    excluded = {
        (x.log_index, x.dimension, x.named, x.reached)
        for x in history.excluded
    }
    assert excluded == {
        (backward, Dimension.RM, "RECEIVED", "ACCEPTED"),
        (backward, Dimension.VF, "Vf", "VF"),
    }
    assert all(x.participant == VENDOR for x in history.excluded)
    assert _kinds(e for e in history.events if e.log_index == following) == [
        EventKind.REPORT_CLOSED
    ]


@pytest.mark.spec("CEH-04-015")
def test_a_public_state_behind_the_case_state_is_excluded():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add(
        "add_case_status_to_case", "Add", CM, case_status("cs-P", "Pxa")
    )
    backward = ledger.add(
        "add_case_status_to_case", "Add", CM, case_status("cs-p", "pxa")
    )
    history = ledger.history()
    assert len(history.of_kind(CSEvent.P)) == 1
    (excluded,) = history.excluded
    assert (excluded.log_index, excluded.participant, excluded.dimension) == (
        backward,
        None,
        Dimension.PXA,
    )


# ---------------------------------------------------------------------------
# Joining (CEH-04-010)
# ---------------------------------------------------------------------------


def _invited(ledger: Ledger) -> int:
    """Seat an inert invitee, as a stub Invite does (CM-11-006)."""
    ledger.add(
        "invite_actor_to_case",
        "Invite",
        CM,
        {"id": INVITEE, "type": "Organization"},
    )
    return ledger.seat(
        participant(
            INVITEE,
            [status("inv-r", INVITEE, "RECEIVED", vf="vf", roles=("VENDOR",))],
            roles=("VENDOR",),
            joined=False,
            consents=[consent(INVITEE, "INVITED")],
        )
    )


@pytest.mark.spec("CEH-04-010")
def test_joining_is_derived_from_the_acceptance_entry():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    seated = _invited(ledger)
    accepted = ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    events = ledger.history().for_participant(INVITEE)
    assert not any(e.log_index == seated for e in events)
    assert [(e.kind, e.log_index) for e in events] == [
        (EventKind.JOINED, accepted),
        (EventKind.REPORT_RECEIVED, accepted),
        (EventKind.CONSENT_AGREED, accepted),
    ]
    assert events[-1].embargo_id == EMBARGO


@pytest.mark.spec("CEH-04-010")
def test_an_expired_invitation_yields_no_joining_event():
    """The stub Invite's deadline passes; its expiry changes no record, so
    no entry records it (CM-11-039, CM-11-040)."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    deadline = stamp(6)
    ledger.add(
        "invite_actor_to_case",
        "Invite",
        CM,
        {"id": INVITEE, "type": "Organization"},
        endTime=deadline,
    )
    ledger.seat(
        participant(
            INVITEE,
            [status("inv-r", INVITEE, "RECEIVED", vf="vf", roles=("VENDOR",))],
            roles=("VENDOR",),
            joined=False,
            consents=[consent(INVITEE, "INVITED")],
        )
    )
    after = ledger.add_status(OWNER, status("owner-a", OWNER, "ACCEPTED"))
    assert ledger.entries[after]["published"] > deadline
    history = ledger.history()
    assert history.of_kind(EventKind.JOINED) == []
    assert history.for_participant(INVITEE) == []


@pytest.mark.spec("CEH-04-010")
@pytest.mark.spec("CEH-04-008")
@pytest.mark.spec("CEH-06-006")
def test_a_refused_invitation_yields_only_the_declined_consent():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _invited(ledger)
    refused = ledger.add(
        "reject_invite_actor_to_case",
        "Reject",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    ledger.add_status(
        CM, status("inv-c", INVITEE, "CLOSED", vf="Vf", roles=("VENDOR",))
    )
    events = ledger.history().for_participant(INVITEE)
    assert [(e.kind, e.log_index, e.embargo_id) for e in events] == [
        (EventKind.CONSENT_DECLINED, refused, EMBARGO)
    ]


# ---------------------------------------------------------------------------
# Embargo start, exit and consent (CEH-04-005 to CEH-04-009)
# ---------------------------------------------------------------------------


def _proposal(
    ledger: Ledger, end_time: str = "2026-03-01T00:00:00+00:00"
) -> None:
    """A proposal of EMBARGO_2, every participant's row created, the vendor
    invited with an RSVP deadline."""
    ledger.add(
        "invite_to_embargo_on_case",
        "Invite",
        REPORTER,
        embargo(EMBARGO_2, end_time),
    )
    for actor in (CM, OWNER, REPORTER, VENDOR):
        ledger.add(
            "create_embargo_consent",
            "Create",
            CM,
            consent(
                actor,
                "AGREED" if actor == REPORTER else "UNINVITED",
                EMBARGO_2,
            ),
        )
    ledger.add(
        "update_embargo_consent",
        "Update",
        CM,
        consent(VENDOR, "INVITED", EMBARGO_2, rsvp_deadline=stamp(500)),
    )


@pytest.mark.spec("CEH-04-005")
@pytest.mark.spec("CEH-04-008")
@pytest.mark.spec("CEH-04-009")
def test_agreeing_declining_and_timing_out_are_distinct_named_events():
    """Three invitees of one proposal answer it three ways, on one ledger."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _proposal(ledger)
    for actor in (VENDOR_2, DEPLOYER):
        ledger.add(
            "update_embargo_consent",
            "Update",
            CM,
            consent(actor, "INVITED", EMBARGO_2, rsvp_deadline=stamp(500)),
        )
    invite = {
        "id": "urn:uuid:inv",
        "type": "Invite",
        "object": embargo(EMBARGO_2),
    }
    agreed = ledger.add(
        "accept_invite_to_embargo_on_case", "Accept", VENDOR, invite
    )
    declined = ledger.add(
        "reject_invite_to_embargo_on_case", "Reject", VENDOR_2, invite
    )
    timed_out = ledger.add(
        "update_embargo_consent",
        "Update",
        CM,
        consent(DEPLOYER, "TIMED_OUT", EMBARGO_2),
    )
    answers = [
        (e.participant, e.kind, e.embargo_id, e.log_index)
        for e in ledger.history().events
        if e.log_index >= agreed
    ]
    assert answers == [
        (VENDOR, EventKind.CONSENT_AGREED, EMBARGO_2, agreed),
        (VENDOR_2, EventKind.CONSENT_DECLINED, EMBARGO_2, declined),
        (DEPLOYER, EventKind.CONSENT_TIMED_OUT, EMBARGO_2, timed_out),
    ]


@pytest.mark.spec("CEH-03-013")
@pytest.mark.spec("CEH-03-015")
@pytest.mark.spec("CEH-06-006")
def test_a_timed_out_invitation_carries_the_earlier_rsvp_deadline():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _proposal(ledger)
    timing_out = consent(VENDOR, "TIMED_OUT", EMBARGO_2)
    assert "rsvpDeadline" not in timing_out
    ledger.add("update_embargo_consent", "Update", CM, timing_out)
    (event,) = ledger.history().of_kind(EventKind.CONSENT_TIMED_OUT)
    assert event.deadline == datetime.fromisoformat(stamp(500))
    assert event.gaps == [GapLabel.STAMPED_WHEN_NEXT_HANDLED]


@pytest.mark.spec("CEH-04-005")
def test_activation_starts_the_embargo_and_the_owner_agrees():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _proposal(ledger)
    active = ledger.add(
        "activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2)
    )
    history = ledger.history()
    starts = history.of_kind(EventKind.EMBARGO_START)
    assert [
        (e.log_index, e.embargo_id, e.replaces_embargo_id) for e in starts
    ] == [
        (0, EMBARGO, None),
        (active, EMBARGO_2, EMBARGO),
    ]
    assert starts[0].participant is None
    owner_agreed = [
        e
        for e in history.for_participant(OWNER)
        if e.kind is EventKind.CONSENT_AGREED and e.embargo_id == EMBARGO_2
    ]
    assert [e.log_index for e in owner_agreed] == [active]


@pytest.mark.spec("CEH-04-005")
def test_a_shorter_revision_carries_every_signatory_over():
    """A revision ending no later is agreed by containment (CM-10-001)."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _proposal(ledger, end_time="2026-01-02T00:00:00+00:00")
    active = ledger.add(
        "activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2)
    )
    carried = {
        e.participant
        for e in ledger.history().of_kind(EventKind.CONSENT_AGREED)
        if e.log_index == active
    }
    assert carried == {CM, OWNER}  # the reporter agreed as proposer already


@pytest.mark.spec("CEH-04-006")
@pytest.mark.spec("CEH-04-007")
@pytest.mark.spec("CEH-03-015")
@pytest.mark.spec("CEH-06-006")
def test_an_end_time_exit_carries_its_reason_and_deadline_and_no_cause():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        CM,
        embargo(),
        content="END_TIME_REACHED",
    )
    (event,) = ledger.history().of_kind(EventKind.EMBARGO_EXIT)
    assert event.exit_reason is TerminationReason.END_TIME_REACHED
    assert event.exit_cause is None
    assert event.deadline == datetime.fromisoformat(EMBARGO_END)
    assert event.embargo_id == EMBARGO
    assert (
        event.semantic_type is MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE
    )


@pytest.mark.spec("CEH-04-006")
@pytest.mark.spec("CEH-04-007")
def test_an_early_exit_carries_its_cause_as_recorded():
    cause = {"kind": "THREAT_SIGNAL", "signals": ["P", "X"]}
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="EARLY",
        terminationCause=cause,
    )
    # The CASE_MANAGER's own Remove of the same embargo is not a second exit.
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        CM,
        embargo(),
        content="EARLY",
        terminationCause=cause,
    )
    (event,) = ledger.history().of_kind(EventKind.EMBARGO_EXIT)
    assert event.exit_reason is TerminationReason.EARLY
    assert event.exit_cause == cause
    assert event.deadline is None
    assert GapLabel.STAMPED_WHEN_NEXT_HANDLED not in event.gaps


def test_an_exit_with_no_reason_is_reported_unreadable():
    ledger = Ledger()
    ledger.standard_genesis()
    index = ledger.add(
        "remove_embargo_event_from_case", "Remove", CM, embargo()
    )
    history = ledger.history()
    assert history.of_kind(EventKind.EMBARGO_EXIT) == []
    assert [u.log_index for u in history.unreadable_entries] == [index]


# ---------------------------------------------------------------------------
# The four gap labels (CEH-03-011 to CEH-03-014, CEH-06-005)
# ---------------------------------------------------------------------------


class TestGapLabels:
    """One event of each of the four gap kinds carries its label (CEH-06-005)."""

    @pytest.mark.spec("CEH-03-011")
    @pytest.mark.spec("CEH-06-005")
    def test_events_seated_by_the_creation_sequence_are_labelled(self):
        history = _vendor_ledger().history()
        owner_r, reporter_a = (
            history.for_participant(OWNER)[0],
            history.for_participant(REPORTER)[0],
        )
        assert owner_r.kind is EventKind.REPORT_RECEIVED
        assert reporter_a.kind is EventKind.REPORT_ACCEPTED
        for event in (owner_r, reporter_a):
            assert event.gaps == [GapLabel.SEATED_AT_CREATION]
        (owner_v,) = [
            e
            for e in history.for_participant(OWNER)
            if e.kind is EventKind.REPORT_VALID
        ]
        assert owner_v.log_index == 1
        assert owner_v.gaps == []

    @pytest.mark.spec("CEH-03-012")
    @pytest.mark.spec("CEH-03-014")
    @pytest.mark.spec("CEH-06-005")
    def test_public_state_is_stamped_at_adoption_and_x_and_a_out_of_band(self):
        ledger = _vendor_ledger()
        # The vendor's own report of P, X and A is not the case's public state.
        reported = ledger.add_status(
            VENDOR,
            status(
                "v-pxa",
                VENDOR,
                "RECEIVED",
                vf="vf",
                case_status=case_status("v-cs", "PXA"),
            ),
        )
        adopted = ledger.add(
            "add_case_status_to_case", "Add", CM, case_status("cs-PXA", "PXA")
        )
        history = ledger.history()
        public = history.of_kind(CSEvent.P, CSEvent.X, CSEvent.A)
        assert [(e.kind, e.log_index) for e in public] == [
            (CSEvent.P, adopted),
            (CSEvent.X, adopted),
            (CSEvent.A, adopted),
        ]
        assert reported < adopted
        assert public[0].gaps == [GapLabel.STAMPED_AT_ADOPTION]
        for event in public[1:]:
            assert event.gaps == [
                GapLabel.STAMPED_AT_ADOPTION,
                GapLabel.REPORTED_OUT_OF_BAND,
            ]

    @pytest.mark.spec("CEH-03-013")
    @pytest.mark.spec("CEH-06-005")
    @pytest.mark.parametrize(
        "claimed",
        [
            # The lazy check, long after the end time.
            "2026-01-09T00:00:00+00:00",
            # An outside request at the end time: the ledger records it alike.
            EMBARGO_END,
        ],
    )
    def test_an_end_time_exit_by_the_case_manager_is_stamped_when_next_handled(
        self, claimed
    ):
        """Every CASE_MANAGER end-time exit, whichever path: the stamp may lag
        the deadline, which the event carries (CEH-03-013, CEH-03-015)."""
        ledger = Ledger()
        ledger.standard_genesis()
        ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
        ledger.add(
            "remove_embargo_event_from_case",
            "Remove",
            CM,
            embargo(),
            content="END_TIME_REACHED",
            claimed=claimed,
        )
        (event,) = ledger.history().of_kind(EventKind.EMBARGO_EXIT)
        assert event.gaps == [GapLabel.STAMPED_WHEN_NEXT_HANDLED]
        assert event.deadline == datetime.fromisoformat(EMBARGO_END)


# ---------------------------------------------------------------------------
# The history carries the ledger's source and holes
# ---------------------------------------------------------------------------


def test_an_unknown_semantic_type_is_reported_and_the_rest_derived():
    ledger = _vendor_ledger()
    odd = ledger.add(
        "frobnicate_case", "Add", VENDOR, status("x", VENDOR, "VALID")
    )
    later = ledger.add_status(VENDOR, status("v-v", VENDOR, "VALID", vf="vf"))
    history = ledger.history()
    assert [u.log_index for u in history.unreadable_entries] == [odd]
    assert any(e.log_index == later for e in history.events)
    assert history.source is LedgerSource.COMPLETE_COPY


@pytest.mark.spec("CEH-04-010")
def test_joining_after_the_embargo_ended_implies_no_consent():
    """The Invite named the embargo, but it ended before the answer."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _invited(ledger)
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="EARLY",
    )
    ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    kinds = _kinds(ledger.history().for_participant(INVITEE))
    assert kinds == [EventKind.JOINED, EventKind.REPORT_RECEIVED]


@pytest.mark.spec("CEH-04-010")
def test_a_joined_record_with_no_acceptance_releases_the_held_state():
    """A merge hole hid the acceptance: no joining event, the state stays."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _invited(ledger)
    later = ledger.add(
        "update_case_participant",
        "Update",
        CM,
        participant(
            INVITEE,
            [status("inv-r", INVITEE, "RECEIVED", vf="vf", roles=("VENDOR",))],
            roles=("VENDOR",),
            joined=True,
        ),
    )
    events = ledger.history().for_participant(INVITEE)
    assert [(e.kind, e.log_index) for e in events] == [
        (EventKind.REPORT_RECEIVED, later)
    ]


@pytest.mark.spec("CEH-04-010")
def test_with_no_embargo_seen_joining_agrees_to_the_one_the_invite_names():
    """A merge missing the genesis: the Invite's embargo is the evidence."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                CM, [status("cm-r", CM, "RECEIVED")], roles=("CASE_MANAGER",)
            )
        ],
        with_embargo=False,
    )
    ledger.add_status(OWNER, status("owner-r", OWNER, "RECEIVED"))
    accepted = ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    (agreed,) = ledger.history().of_kind(EventKind.CONSENT_AGREED)
    assert (agreed.participant, agreed.embargo_id, agreed.log_index) == (
        INVITEE,
        EMBARGO,
        accepted,
    )


@pytest.mark.spec("CEH-03-006")
def test_an_entry_with_no_commit_stamp_is_reported_unreadable():
    ledger = _vendor_ledger()
    index = ledger.add_status(VENDOR, status("v-v", VENDOR, "VALID", vf="vf"))
    del ledger.entries[index]["published"]
    history = ledger.history()
    assert [(u.log_index, u.reason) for u in history.unreadable_entries] == [
        (index, "no commit stamp")
    ]
    assert not any(e.log_index == index for e in history.events)


def test_an_exit_naming_no_embargo_with_none_in_force_is_unreadable():
    ledger = Ledger()
    ledger.genesis([], with_embargo=False)
    index = ledger.add(
        "remove_embargo_event_from_case", "Remove", CM, None, content="EARLY"
    )
    history = ledger.history()
    assert history.of_kind(EventKind.EMBARGO_EXIT) == []
    assert [u.log_index for u in history.unreadable_entries] == [index]


# ---------------------------------------------------------------------------
# Edge paths found in review
# ---------------------------------------------------------------------------


def test_an_end_time_exit_not_committed_by_the_case_manager_is_unlabelled():
    """Only the CASE_MANAGER's own exit is a deadline it found late."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="END_TIME_REACHED",
    )
    (event,) = ledger.history().of_kind(EventKind.EMBARGO_EXIT)
    assert event.gaps == []
    assert event.deadline == datetime.fromisoformat(EMBARGO_END)


@pytest.mark.spec("CEH-04-008")
def test_an_implied_agreement_never_overrides_a_refusal():
    """A joiner that declined the embargo first stays declined (CM-11-001)."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _invited(ledger)
    ledger.add(
        "update_embargo_consent", "Update", CM, consent(INVITEE, "DECLINED")
    )
    ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    kinds = _kinds(ledger.history().for_participant(INVITEE))
    assert kinds == [
        EventKind.CONSENT_DECLINED,
        EventKind.JOINED,
        EventKind.REPORT_RECEIVED,
    ]


@pytest.mark.spec("CEH-04-005")
def test_an_activation_with_none_in_force_replaces_nothing_and_starts_once():
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                CM, [status("cm-r", CM, "RECEIVED")], roles=("CASE_MANAGER",)
            )
        ],
        with_embargo=False,
    )
    ledger.add_status(OWNER, status("owner-r", OWNER, "RECEIVED"))
    first = ledger.add(
        "activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2)
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    starts = ledger.history().of_kind(EventKind.EMBARGO_START)
    assert [
        (e.log_index, e.embargo_id, e.replaces_embargo_id) for e in starts
    ] == [(first, EMBARGO_2, None)]


@pytest.mark.spec("CEH-04-005")
def test_ending_an_embargo_not_in_force_leaves_the_one_in_force():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(EMBARGO_2),
        content="EARLY",
    )
    _invited(ledger)
    ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    history = ledger.history()
    assert [e.embargo_id for e in history.of_kind(EventKind.EMBARGO_EXIT)] == [
        EMBARGO_2
    ]
    agreed = [
        e.embargo_id
        for e in history.for_participant(INVITEE)
        if e.kind is EventKind.CONSENT_AGREED
    ]
    assert agreed == [EMBARGO]


@pytest.mark.spec("CEH-03-008")
def test_an_unparseable_claimed_time_reads_as_absent():
    ledger = _vendor_ledger()
    index = ledger.add(
        "add_participant_status_to_participant",
        "Add",
        VENDOR,
        status("v-v", VENDOR, "VALID", vf="vf"),
        claimed="last tuesday",
    )
    (event,) = [e for e in ledger.history().events if e.log_index == index]
    assert event.claimed_at is None


def test_times_with_no_offset_read_as_utc_and_compare():
    """A revision whose end time has no offset is compared, not a crash."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _proposal(ledger, end_time="2026-01-02T00:00:00")
    active = ledger.add(
        "activate_embargo_on_case",
        "Add",
        OWNER,
        embargo(EMBARGO_2, "2026-01-02T00:00:00"),
    )
    history = ledger.history()
    carried = {
        e.participant
        for e in history.of_kind(EventKind.CONSENT_AGREED)
        if e.log_index == active
    }
    assert carried == {CM, OWNER}
    assert all(e.committed_at.tzinfo is not None for e in history.events)


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (status("bad-rm", VENDOR, "REOPENED", vf="vf"), "no known RM state"),
        (
            {
                "id": "no-rm",
                "type": "ParticipantStatus",
                "attributedTo": VENDOR,
            },
            "no known RM state",
        ),
        (status("bad-vf", VENDOR, "RECEIVED", vf="vF"), "unreadable vf state"),
        (status("odd-vf", VENDOR, "RECEIVED", vf="Xf"), "unreadable vf state"),
        (
            {"id": "anon", "type": "ParticipantStatus", "rmState": "VALID"},
            "names no participant",
        ),
        (
            {"type": "CaseParticipant", "participantStatuses": []},
            "record names no actor",
        ),
        (
            {
                "type": "EmbargoConsent",
                "attributedTo": VENDOR,
                "state": "AGREED",
            },
            "consent row lacks",
        ),
    ],
)
def test_an_unreadable_record_is_reported_and_the_rest_derived(record, reason):
    ledger = _vendor_ledger()
    odd = ledger.add(
        "add_participant_status_to_participant", "Add", VENDOR, record
    )
    later = ledger.add_status(
        VENDOR, status("v-a", VENDOR, "ACCEPTED", vf="vf")
    )
    history = ledger.history()
    (unreadable,) = history.unreadable_entries
    assert unreadable.log_index == odd
    assert reason in unreadable.reason
    assert not any(e.log_index == odd for e in history.events)
    assert any(e.log_index == later for e in history.events)


def test_each_nameless_participant_record_is_reported():
    ledger = _vendor_ledger()
    nameless = {"type": "CaseParticipant", "participantStatuses": []}
    odd = ledger.add(
        "add_case_participant_to_case",
        "Add",
        CM,
        {"type": "Collection", "items": [nameless, dict(nameless)]},
    )
    reported = [
        u.log_index
        for u in ledger.history().unreadable_entries
        if "names no actor" in u.reason
    ]
    assert reported == [odd, odd]


def test_an_embargo_reply_naming_no_embargo_is_reported():
    ledger = _vendor_ledger()
    odd = ledger.add(
        "accept_invite_to_embargo_on_case",
        "Accept",
        VENDOR,
        {"id": "urn:uuid:inv", "type": "Invite"},
    )
    history = ledger.history()
    assert [u.log_index for u in history.unreadable_entries] == [odd]
    assert history.of_kind(EventKind.CONSENT_AGREED)[-1].log_index != odd


def test_a_refusal_with_no_embargo_in_force_records_no_consent():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(),
        content="EARLY",
    )
    _invited(ledger)
    ledger.add(
        "reject_invite_actor_to_case",
        "Reject",
        INVITEE,
        ledger.stub_invite(INVITEE),
    )
    history = ledger.history()
    assert history.for_participant(INVITEE) == []
    assert history.unreadable_entries == []


@pytest.mark.parametrize("place", ["target", "origin"])
def test_a_stub_case_status_in_an_invite_target_is_not_the_cases(place):
    """A record under an Invite's target or origin is no public state."""
    ledger = _vendor_ledger()
    ledger.add(
        "add_case_status_to_case", "Add", CM, case_status("cs-P", "Pxa")
    )
    invite = ledger.stub_invite(INVITEE)
    invite.setdefault(place, {})["caseStatus"] = case_status("stub-cs", "pxa")
    ledger.add("accept_invite_actor_to_case", "Accept", INVITEE, invite)
    history = ledger.history()
    assert history.excluded == []
    assert len(history.of_kind(CSEvent.P)) == 1
