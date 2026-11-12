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

"""The event history of every committed recording (CEH-06-001).

Each recording under ``ui/src/recordings/`` is the CASE_MANAGER's own copy of
a real scenario run.  :data:`_NARRATIVES` states what each scenario's branch
choices (its ``steps.json``) require the case to have recorded; the tests
assert the derived history holds exactly that.
"""

import json
from dataclasses import dataclass
from datetime import datetime

import pytest

from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.demo.recordings.layout import RECORDINGS_DIR, recording_path
from vultron.measure.history import (
    CaseEventHistory,
    EventKind,
    GapLabel,
    read_case_event_histories,
)
from vultron.measure.ledger import LedgerSource


def _actor(name: str) -> str:
    """The URI a recording gives the demo actor *name*."""
    return f"http://{name}:7999/api/v2/actors/{name}"


CASE_ACTOR = _actor("case-actor")


@dataclass(frozen=True)
class Narrative:
    """What a scenario's branch choices require of its history.

    Fields:
        owner: The Case Owner at creation.
        joiners: Every invitee that accepted, in joining order.
        vendors: Every vendor that became aware and has a fix ready, once
            each.
        deployers: Every participant whose fix deployment is recorded.
        declined: Every invitee that refused its invitation.
        embargoes: How many embargo register entries went into force.
        exit_cause: The cause kind of the early embargo exit.
    """

    owner: str
    joiners: tuple[str, ...] = ()
    vendors: tuple[str, ...] = ()
    deployers: tuple[str, ...] = ()
    declined: tuple[str, ...] = ()
    embargoes: int = 1
    exit_cause: str = "THREAT_SIGNAL"


#: The branch choices of each recording, as its history must show them.
_NARRATIVES: dict[str, Narrative] = {
    # reporter → vendor; the vendor reports its fix ready.
    "rv": Narrative(owner=_actor("actor1"), vendors=(_actor("actor1"),)),
    # reporter → vendor with a CSAF report; the case's first embargo is the
    # report's disclosure date, the vendor's longer default stays pending.
    "rv-csaf": Narrative(owner=_actor("actor1"), vendors=(_actor("actor1"),)),
    # reporter → vendor, which invites a second vendor.
    "rvv": Narrative(
        owner=_actor("actor1"),
        joiners=(_actor("actor3"),),
        vendors=(_actor("actor3"), _actor("actor1")),
    ),
    # reporter → coordinator, which invites a vendor that accepts.
    "rcv": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor1"),),
        vendors=(_actor("actor1"),),
    ),
    # ... and the vendor proposes an embargo, which the owner activates
    # and later ends early.
    "rcv-embargo": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor1"),),
        vendors=(_actor("actor1"),),
        embargoes=2,
        exit_cause="OTHER",
    ),
    # ... the vendor refuses the invitation.
    "rcv-reject": Narrative(
        owner=_actor("actor2"), declined=(_actor("actor1"),)
    ),
    # ... the coordinator invites a second coordinator, which brings in a
    # vendor that also deploys.
    "rcvcv": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor1"), _actor("actor3"), _actor("actor4")),
        vendors=(_actor("actor1"), _actor("actor4")),
        deployers=(_actor("actor4"),),
    ),
    # ... the vendor proposes an embargo, then a revision of it.
    "rcvv-embargo": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor1"), _actor("actor3")),
        vendors=(_actor("actor1"), _actor("actor3")),
        embargoes=3,
    ),
    # reporter → coordinator → second coordinator → vendor; the owner keeps
    # the case, or offers ownership.
    "rccv-extension": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor3"), _actor("actor1")),
        vendors=(_actor("actor1"),),
    ),
    "rccv-handoff": Narrative(
        owner=_actor("actor2"),
        joiners=(_actor("actor3"), _actor("actor1")),
        vendors=(_actor("actor1"),),
    ),
    # reporter → vendor → coordinator → second vendor.
    "rvcv-extension": Narrative(
        owner=_actor("actor1"),
        joiners=(_actor("actor2"), _actor("actor3")),
        vendors=(_actor("actor3"), _actor("actor1")),
    ),
    "rvcv-handoff": Narrative(
        owner=_actor("actor1"),
        joiners=(_actor("actor2"), _actor("actor3")),
        vendors=(_actor("actor3"), _actor("actor1")),
    ),
}


def _history(scenario: str) -> CaseEventHistory:
    read = read_case_event_histories([recording_path(scenario)])
    (history,) = read.histories.values()
    return history


def test_every_committed_recording_has_a_narrative():
    committed = {
        p.parent.name for p in RECORDINGS_DIR.glob("*/case-actor.jsonl")
    }
    assert committed == set(_NARRATIVES)


def _participants_with(history: CaseEventHistory, kind) -> list[str]:
    """The participants with an event of *kind*, in first-event order."""
    return list(
        dict.fromkeys(e.participant or "" for e in history.of_kind(kind))
    )


@pytest.mark.spec("CEH-06-001")
@pytest.mark.parametrize("scenario", sorted(_NARRATIVES))
def test_a_recording_yields_the_events_its_narrative_requires(scenario):
    narrative = _NARRATIVES[scenario]
    history = _history(scenario)

    assert history.source is LedgerSource.COMPLETE_COPY
    assert history.end_confirmed
    assert history.excluded == []
    assert history.unreadable_entries == []

    # The creation sequence seats the owner at received and the reporter at
    # accepted (CM-14-009, CM-14-012).
    owner_first = history.for_participant(narrative.owner)[0]
    assert owner_first.kind is EventKind.REPORT_RECEIVED
    assert GapLabel.SEATED_AT_CREATION in owner_first.gaps

    assert _participants_with(history, EventKind.JOINED) == list(
        narrative.joiners
    )
    for kind, expected in (
        (CSEvent.V, narrative.vendors),
        (CSEvent.F, narrative.vendors),
        (CSEvent.D, narrative.deployers),
    ):
        found = _participants_with(history, kind)
        assert sorted(found) == sorted(expected), kind
        assert len(history.of_kind(kind)) == len(expected), kind
    assert _participants_with(history, EventKind.CONSENT_DECLINED) == list(
        narrative.declined
    )
    assert len(history.of_kind(EventKind.EMBARGO_START)) == narrative.embargoes

    # Every scenario ends with the embargo ended early, the vul public, and
    # every joined participant's report closed.
    (exit_,) = history.of_kind(EventKind.EMBARGO_EXIT)
    assert exit_.exit_reason is TerminationReason.EARLY
    assert exit_.exit_cause is not None
    assert exit_.exit_cause["kind"] == narrative.exit_cause
    (public,) = history.of_kind(CSEvent.P)
    assert public.gaps == [GapLabel.STAMPED_AT_ADOPTION]
    assert public.participant is None
    seated = {
        e.participant
        for e in history.of_kind(
            EventKind.REPORT_RECEIVED, EventKind.REPORT_ACCEPTED
        )
    }
    assert {narrative.owner, CASE_ACTOR, *narrative.joiners} <= seated
    assert seated.isdisjoint(narrative.declined)
    assert set(_participants_with(history, EventKind.REPORT_CLOSED)) == seated

    # One joiner's joining and report-received events share a log index.
    for joiner in narrative.joiners:
        joined, received = history.for_participant(joiner)[:2]
        assert (joined.kind, received.kind) == (
            EventKind.JOINED,
            EventKind.REPORT_RECEIVED,
        )
        assert joined.log_index == received.log_index

    assert [e.log_index for e in history.events] == sorted(
        e.log_index for e in history.events
    )


@pytest.mark.spec("CEH-04-010")
def test_the_refused_invitee_in_rcv_reject_never_joins():
    """Its inert record is seated two entries before the refusal."""
    history = _history("rcv-reject")
    invitee = _actor("actor1")
    assert history.of_kind(EventKind.JOINED) == []
    events = history.for_participant(invitee)
    assert [(e.kind, e.semantic_type.value) for e in events] == [
        (EventKind.CONSENT_DECLINED, "reject_invite_actor_to_case")
    ]


@pytest.mark.spec("CEH-04-014")
def test_the_recommended_vendor_in_rccv_extension_is_dated_to_its_own_record():
    """Entry 21 recommends the vendor at ``RM.START``; entry 25 seats it."""
    history = _history("rccv-extension")
    vendor = _actor("actor1")
    events = history.for_participant(vendor)
    assert min(e.log_index for e in events) >= 25
    assert not any(e.log_index in (21, 22) for e in history.events)


@pytest.mark.spec("CEH-03-011")
def test_the_reporter_is_seated_at_accepted_by_the_creation_sequence():
    history = _history("rcv")
    reporter_events = history.for_participant(_actor("actor0"))
    first = reporter_events[0]
    assert (first.kind, first.log_index) == (EventKind.REPORT_ACCEPTED, 0)
    assert GapLabel.SEATED_AT_CREATION in first.gaps


@pytest.mark.spec("CEH-03-012")
def test_public_awareness_is_dated_to_adoption_not_the_first_report():
    """In rcv-embargo the owner reports P at entry 38; the CASE_MANAGER
    adopts it at 39."""
    history = _history("rcv-embargo")
    (public,) = history.of_kind(CSEvent.P)
    assert public.log_index == 39
    assert public.gaps == [GapLabel.STAMPED_AT_ADOPTION]


@pytest.mark.spec("CEH-01-003")
@pytest.mark.spec("CEH-03-005")
@pytest.mark.spec("CEH-03-006")
@pytest.mark.spec("CEH-03-007")
@pytest.mark.spec("CEH-03-009")
@pytest.mark.parametrize("scenario", sorted(_NARRATIVES))
def test_every_event_carries_its_entrys_index_type_and_clocks(scenario):
    path = recording_path(scenario)
    entries = {
        e["logIndex"]: e
        for e in map(json.loads, path.read_text(encoding="utf-8").splitlines())
    }
    events = _history(scenario).events
    for event in events:
        entry = entries[event.log_index]
        assert event.semantic_type.value == entry["semanticType"]
        assert event.committed_at == datetime.fromisoformat(entry["published"])
        claimed = entry["payloadSnapshot"]["published"]
        assert event.claimed_at == datetime.fromisoformat(claimed)
    # An act reads its clock once (ADR-0176), so an entry the committer
    # authored itself claims the instant it commits at.  A message from
    # another participant does not, and that is what shows the two clocks
    # are read from their own fields.
    assert any(e.claimed_at != e.committed_at for e in events)


@pytest.mark.spec("CEH-03-009")
def test_one_kind_from_two_semantic_types_names_each():
    received = _history("rcv").of_kind(EventKind.REPORT_RECEIVED)
    assert {e.semantic_type.value for e in received} == {
        "create_case",
        "accept_invite_actor_to_case",
    }


@pytest.mark.spec("CEH-04-005")
def test_rcv_embargo_yields_each_embargo_step_at_its_own_entry():
    history = _history("rcv-embargo")
    steps = [
        (e.kind, e.participant, e.log_index)
        for e in history.events
        if e.kind
        in (
            EventKind.EMBARGO_START,
            EventKind.EMBARGO_EXIT,
            EventKind.CONSENT_AGREED,
        )
        and e.log_index > 0
    ]
    assert steps == [
        (EventKind.CONSENT_AGREED, _actor("actor1"), 16),  # joining
        (EventKind.CONSENT_AGREED, _actor("actor0"), 26),  # the proposer
        (EventKind.CONSENT_AGREED, _actor("actor1"), 32),  # its Accept
        (EventKind.EMBARGO_START, None, 33),
        (EventKind.CONSENT_AGREED, _actor("actor2"), 33),  # the owner
        (EventKind.EMBARGO_EXIT, None, 37),
    ]


@pytest.mark.spec("CEH-04-009")
def test_rcvv_embargo_consents_name_the_embargo_each_answers():
    """An embargo and its revision: each answer names its own entry."""
    history = _history("rcvv-embargo")
    starts = [e.embargo_id for e in history.of_kind(EventKind.EMBARGO_START)]
    default, proposal, revision = starts
    answered = {
        (e.participant, e.embargo_id, e.log_index)
        for e in history.of_kind(EventKind.CONSENT_AGREED)
        if e.log_index > 0
    }
    assert {
        (_actor("actor1"), proposal, 32),
        (_actor("actor1"), revision, 40),
        (_actor("actor0"), revision, 45),
        (_actor("actor3"), revision, 50),
    } <= answered
    assert {embargo for _, embargo, _ in answered} == {
        default,
        proposal,
        revision,
    }
