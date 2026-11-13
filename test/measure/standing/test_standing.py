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

"""The standing record of a case ledger (ADR-0190, level 1).

The committed recordings are read whole and cut short: whole, every one ends
with the embargo exited and every report closed; cut short, the case still
stands mid-way, with an embargo revision open and moves left to make.
"""

import json
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    DEPLOYER,
    EMBARGO_2,
    INVITEE,
    VENDOR,
    Ledger,
    embargo,
    participant,
    seat_vendor,
    status,
)
from vultron.core.states.cs import CS, CS_pxa
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_dimensions,
    cs_transition_event,
    next_cs_states,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.demo.recordings.layout import RECORDINGS_DIR, recording_path
from vultron.measure.baselines import ORIGINAL, baseline
from vultron.measure.history import read_case_event_histories
from vultron.measure.history.snapshot import snapshot_records
from vultron.measure.ledger import (
    CaseLedger,
    Dimension,
    actor_uri,
    dimension_state,
    first_present,
    read_case_ledgers,
)
from vultron.measure.scoring import (
    met_desiderata,
    score_case,
    score_prefix,
)
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
    case_state_sequences,
)
from vultron.measure.standing import (
    CaseStanding,
    DesideratumStatus,
    ParticipantStanding,
    StandingGap,
    StandingRecord,
    case_standing,
    desiderata_standing,
)

_SCENARIOS = sorted(
    p.parent.name for p in RECORDINGS_DIR.glob("*/case-actor.jsonl")
)


def _actor(name: str) -> str:
    return f"http://{name}:7999/api/v2/actors/{name}"


def _ledger(path: Path) -> CaseLedger:
    (ledger,) = read_case_ledgers([path]).cases.values()
    return ledger


def _cut(scenario: str, entries: int, tmp_path: Path) -> CaseLedger:
    """The recording of *scenario* with only its first *entries* entries."""
    lines = recording_path(scenario).read_text(encoding="utf-8").splitlines()
    path = tmp_path / f"{scenario}-{entries}.jsonl"
    path.write_text("\n".join(lines[:entries]) + "\n", encoding="utf-8")
    return _ledger(path)


def _rows(scenario: str) -> Iterator[dict[str, Any]]:
    text = recording_path(scenario).read_text(encoding="utf-8")
    yield from map(json.loads, text.splitlines())


def _last_stated(
    scenario: str,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """What the recording's snapshots last state, read without the history.

    Returns each participant's last stated RM, VF and D, and the last EM
    and PXA a case status states.
    """
    participants: dict[str, dict[str, str]] = {}
    case: dict[str, str] = {}
    for row in _rows(scenario):
        records = snapshot_records(row["payloadSnapshot"])
        statuses = [
            (p.actor, s) for p in records.participants for s in p.statuses
        ] + [
            (actor_uri(first_present(s, "attributedTo")), s)
            for s in records.loose_statuses
        ]
        for actor, stated in statuses:
            assert actor is not None, "every recorded status names its actor"
            last = participants.setdefault(actor, {})
            for dim in (Dimension.RM, Dimension.VF, Dimension.D):
                value = dimension_state([stated], dim)
                if value is not None:
                    last[dim.value] = value
        for stated in records.case_statuses:
            for dim in (Dimension.EM, Dimension.PXA):
                value = dimension_state([stated], dim)
                if value is not None:
                    case[dim.value] = value
    return participants, case


@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_a_recording_stands_in_the_states_its_last_snapshots_state(scenario):
    """AC-1: each participant's RM, the case's EM and every vendor's CS."""
    record = case_standing(_ledger(recording_path(scenario)))
    participants, case = _last_stated(scenario)

    assert record.gap is None
    assert record.end_confirmed
    assert record.case is not None
    assert record.case.em == case["em"] == EM.EXITED
    assert record.case.pxa.name == case["pxa"]
    assert {p.participant for p in record.participants} == set(participants)
    for standing in record.participants:
        stated = participants[standing.participant]
        assert standing.rm == stated["rm"], standing.participant
        if standing.case_state is not None:
            vf, d, pxa = cs_dimensions(standing.case_state)
            assert vf == stated.get("vf", "vf"), standing.participant
            assert d == stated.get("d", "d"), standing.participant
            assert pxa is record.case.pxa


def test_a_refused_invitee_stands_closed_though_it_never_joined():
    record = case_standing(_ledger(recording_path("rcv-reject")))
    invitee = record.for_participant(_actor("actor1"))
    assert (invitee.rm, invitee.joined) == (RM.CLOSED, False)
    assert invitee.rm_moves == ()
    assert invitee.score is None
    assert invitee.unscored.reason is UnprojectableReason.NO_CASE_STATE_EVENTS


@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_every_vendor_is_scored_as_vultron_measure_scores_it(scenario):
    """AC-2: the scores are ``score_case``'s, the statuses read from them."""
    record = case_standing(_ledger(recording_path(scenario)))
    (history,) = read_case_event_histories(
        [recording_path(scenario)]
    ).histories.values()
    summary = score_case(case_state_sequences(history))
    scored = [p for p in record.participants if p.score is not None]
    assert sorted(p.participant for p in scored) == sorted(
        v.participant for v in summary.vendors
    )
    # rcv-reject's only vendor refuses its invitation, so it has no sequence.
    assert bool(scored) == (scenario != "rcv-reject")
    for standing in scored:
        expected = summary.for_participant(standing.participant)
        assert standing.score == expected.score
        met = sum(
            (
                1 - baseline(d)
                for d, s in zip(ORIGINAL, standing.desiderata, strict=True)
                if s.status is DesideratumStatus.MET
            ),
            Fraction(0),
        )
        reachable = sum(
            (
                1 - baseline(d)
                for d, s in zip(ORIGINAL, standing.desiderata, strict=True)
                if s.status is not DesideratumStatus.BROKEN
            ),
            Fraction(0),
        )
        assert met <= standing.score.worst
        assert standing.score.best <= reachable


def test_a_complete_history_meets_or_breaks_every_desideratum():
    history = "VFDPXA"
    statuses = desiderata_standing(score_prefix(history))
    met = set(met_desiderata(history))
    assert [s.status for s in statuses] == [
        DesideratumStatus.MET if d in met else DesideratumStatus.BROKEN
        for d in ORIGINAL
    ]


def test_an_empty_history_leaves_every_desideratum_open():
    statuses = desiderata_standing(score_prefix(""))
    assert {s.status for s in statuses} == {DesideratumStatus.OPEN}
    assert [(s.before, s.after) for s in statuses][:2] == [
        (CSEvent.D, CSEvent.P),
        (CSEvent.F, CSEvent.P),
    ]


def test_publication_before_the_fix_breaks_what_it_precedes():
    by_order = {
        (s.before + s.after): s.status
        for s in desiderata_standing(score_prefix("VP"))
    }
    assert by_order["VP"] is DesideratumStatus.MET
    assert by_order["FP"] is DesideratumStatus.BROKEN
    assert by_order["DP"] is DesideratumStatus.BROKEN
    assert by_order["XA"] is DesideratumStatus.OPEN


def test_a_vendors_moves_are_the_state_machines_from_its_states(tmp_path):
    """AC-3: rcv-embargo cut before the vendor's fix is ready."""
    record = case_standing(_cut("rcv-embargo", 32, tmp_path))
    assert not record.end_confirmed
    vendor = record.for_participant(_actor("actor1"))
    assert vendor.rm is RM.ACCEPTED
    assert vendor.case_state is CS.Vfdpxa
    assert [m.destination for m in vendor.rm_moves] == [
        dest for dest in RM if is_valid_rm_transition(RM.ACCEPTED, dest)
    ]
    assert {m.destination for m in vendor.cs_moves} == set(
        next_cs_states(CS.Vfdpxa)
    )
    assert [m.event for m in vendor.cs_moves] == [
        cs_transition_event(CS.Vfdpxa, dest)
        for dest in (CS.VFdpxa, CS.VfdPxa, CS.VfdpXa, CS.VfdpxA)
    ]
    assert vendor.case_state_prefix == (CSEvent.V,)
    for move in vendor.cs_moves:
        assert score_prefix(move.extend(vendor.case_state_prefix))


def test_a_case_cut_mid_revision_stands_in_revise(tmp_path):
    """rcv-embargo proposes a second embargo at 23 and activates it at 33."""
    record = case_standing(_cut("rcv-embargo", 30, tmp_path))
    assert record.case == CaseStanding(em=EM.REVISE, pxa=record.case.pxa)
    assert {m.trigger for m in record.case.em_moves} == set(EM_Trigger)
    after = case_standing(_cut("rcv-embargo", 34, tmp_path))
    assert after.case.em is EM.ACTIVE


def test_a_finished_case_allows_no_move():
    record = case_standing(_ledger(recording_path("rv")))
    assert record.case.em_moves == ()
    assert all(p.rm_moves == () for p in record.participants)


def test_a_hand_built_case_stands_as_its_entries_state():
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add(
        "invite_to_embargo_on_case", "Invite", VENDOR, embargo(EMBARGO_2)
    )
    record = case_standing(ledger.case_ledger())
    assert record.case.em is EM.REVISE
    vendor = record.for_participant(VENDOR)
    assert (vendor.rm, vendor.case_state) == (RM.RECEIVED, CS.Vfdpxa)
    assert [m.event for m in vendor.cs_moves] == [
        CSEvent.P,
        CSEvent.X,
        CSEvent.A,
    ]
    # The vendor is aware before anything public: V before P, X and A is met.
    assert {
        s.before + s.after
        for s in vendor.desiderata
        if s.status is DesideratumStatus.MET
    } == {"VP", "VX", "VA"}
    assert {s.status for s in vendor.desiderata if s.before != CSEvent.V} == {
        DesideratumStatus.OPEN
    }


@pytest.mark.spec("CEH-02-006")
def test_a_ledger_with_a_hole_names_the_gap_and_scores_nothing(tmp_path):
    """AC-4: a recording with entries 10 and 11 missing."""
    lines = recording_path("rv").read_text(encoding="utf-8").splitlines()
    path = tmp_path / "holed.jsonl"
    path.write_text(
        "\n".join(lines[:10] + lines[12:]) + "\n", encoding="utf-8"
    )
    record = case_standing(_ledger(path))
    assert record.gap is not None
    assert record.gap.missing_log_indices == [10, 11]
    assert record.case is None
    assert record.participants == []


def test_a_broken_register_names_the_gap(tmp_path):
    """EMBARGO_2 terminated beside EMBARGO in force has no EM state."""
    ledger = Ledger()
    ledger.genesis([])
    ledger.add(
        "announce_vulnerability_case",
        "Announce",
        "urn:cm",
        {
            "id": "urn:uuid:case-1",
            "type": "VulnerabilityCase",
            "embargoRegister": [
                {"embargo": embargo(EMBARGO_2), "status": "TERMINATED"}
            ],
        },
    )
    record = case_standing(ledger.case_ledger())
    assert record.gap is not None
    assert "invariants" in record.gap.register_problem
    assert record.case is None


def test_a_gap_names_a_hole():
    with pytest.raises(ValidationError, match="at least one hole"):
        StandingGap()


def test_a_record_holds_a_reading_or_its_gap():
    gap = StandingGap(missing_log_indices=[3])
    case = CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa)
    with pytest.raises(ValidationError, match="holds no reading"):
        StandingRecord(case_id="c", end_confirmed=False, gap=gap, case=case)
    with pytest.raises(ValidationError, match="holds the case's standing"):
        StandingRecord(case_id="c", end_confirmed=False)


def test_a_participant_is_scored_or_says_why_not():
    with pytest.raises(ValidationError, match="either a score"):
        ParticipantStanding(participant=VENDOR, rm=RM.START)


def test_a_record_serializes_as_json():
    record = case_standing(_ledger(recording_path("rv")))
    data = json.loads(record.model_dump_json())
    vendor = next(
        p for p in data["participants"] if p["case_state"] is not None
    )
    assert vendor["case_state"] == "VFdPxa"
    assert len(vendor["desiderata"]) == len(ORIGINAL)
    assert data["case"]["pxa"] == "Pxa"


def _write(path: Path, entries: list[dict[str, Any]]) -> Path:
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8"
    )
    return path


def test_copies_that_disagree_name_the_gap(tmp_path):
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    other = json.loads(json.dumps(ledger.entries))
    other[1]["entryHash"] = "another-hash"
    read = read_case_ledgers(
        [
            _write(tmp_path / "a.jsonl", ledger.entries),
            _write(tmp_path / "b.jsonl", other),
        ]
    )
    (case_ledger,) = read.cases.values()
    record = case_standing(case_ledger)
    assert record.gap is not None
    assert record.gap.conflicting_log_indices == [1]
    assert record.participants == []


def test_an_unplaceable_row_names_the_gap(tmp_path):
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    rows = json.loads(json.dumps(ledger.entries))
    del rows[1]["logIndex"]
    record = case_standing(_ledger(_write(tmp_path / "a.jsonl", rows)))
    assert record.gap is not None
    assert len(record.gap.unusable_rows) == 1


def test_an_unreadable_entry_names_the_gap():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add("not_a_semantic_type", "Note", VENDOR)
    record = case_standing(ledger.case_ledger())
    assert record.gap is not None
    (unreadable,) = record.gap.unreadable_entries
    assert unreadable.log_index == 1
    assert record.case is None


def test_an_unscored_participant_keeps_the_projections_reason():
    """A Deployer without the Vendor role has no case-state model state."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.seat(
        participant(
            DEPLOYER,
            [
                status(
                    "dep-r", DEPLOYER, "ACCEPTED", d="D", roles=("DEPLOYER",)
                )
            ],
            roles=("DEPLOYER",),
        )
    )
    record = case_standing(ledger.case_ledger())
    deployer = record.for_participant(DEPLOYER)
    assert deployer.unscored.reason is UnprojectableReason.NO_VENDOR_AWARENESS
    assert deployer.cs_moves == ()
    assert deployer.case_state is None


def test_a_participant_with_no_event_is_unscored_for_that_reason():
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.seat(participant(INVITEE, [], roles=("VENDOR",), joined=False))
    record = case_standing(ledger.case_ledger())
    invitee = record.for_participant(INVITEE)
    assert invitee.unscored.reason is UnprojectableReason.NO_CASE_STATE_EVENTS
    assert "no event" in invitee.unscored.detail
    assert [m.destination for m in invitee.rm_moves] == [RM.RECEIVED]


def test_the_reason_given_must_be_the_participants_own():
    reason = UnprojectableParticipant(
        participant=INVITEE,
        reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
        detail="none",
    )
    with pytest.raises(ValidationError, match="not"):
        ParticipantStanding(participant=VENDOR, rm=RM.START, unscored=reason)


def test_every_move_names_the_participant_whose_state_it_moves(tmp_path):
    """AC-3 (#6368): each RM and CS move is labelled with its participant."""
    record = case_standing(_cut("rcv-embargo", 32, tmp_path))
    for standing in record.participants:
        for move in (*standing.rm_moves, *standing.cs_moves):
            assert move.participant == standing.participant
    assert any(p.cs_moves for p in record.participants)
