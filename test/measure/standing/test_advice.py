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

"""Each allowed move's change in expected desiderata outcome (AC-6, #6368)."""

import json
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    CM,
    EMBARGO_2,
    OWNER,
    REPORTER,
    VENDOR,
    VENDOR_2,
    Ledger,
    embargo,
    participant,
    publish,
    seat_vendor,
    status,
)
from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.rm import RM
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.baselines import (
    EmbargoEnd,
    Event,
    EventKind,
    JointState,
    VendorPath,
    WalkPrefix,
    vendor_desiderata,
)
from vultron.measure.history import derive_case
from vultron.measure.ledger import read_case_ledgers
from vultron.measure.sequences import case_state_sequences
from vultron.measure.standing import (
    CSMove,
    EMMove,
    NoJointStep,
    RMMove,
    ScoredMove,
    StandingRecord,
    case_prefix,
    case_standing,
    joint_step,
)

_F_BEFORE_P = r"$\evF \prec \evP$"


def _vendor_case() -> Ledger:
    """The standard genesis, and a vendor aware at RM Received."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    return ledger


def _scored(record: StandingRecord, participant: str, name: str) -> ScoredMove:
    (move,) = [
        m
        for m in record.moves
        if m.move.participant == participant and m.move.name == name
    ]
    return move


def test_one_moves_change_matches_a_hand_count():
    """Publication from Vfdpxa takes ``F ≺ P`` from 1/3 to 0.

    From ``Vfdpxa`` the indifference walk takes F, P, X or A, each 1/4.  F
    meets ``F ≺ P``; P breaks it; X forces P next and breaks it; A leads to
    ``VfdpxA``, where F, P and X are each 1/3 and only F meets it.  So the
    chance is 1/4 + 1/4 · 1/3 = 1/3, and publishing now ends it at 0.
    """
    record = case_standing(_vendor_case().case_ledger())
    publication = _scored(record, VENDOR, "cs.public_becomes_aware")
    assert publication.changes is not None
    (change,) = [c for c in publication.changes if c.notation == _F_BEFORE_P]
    assert (change.vendor, change.other_vendor) == (VENDOR, None)
    assert change.change == Fraction(-1, 3)


def test_the_prefix_is_the_standing_in_the_joint_model():
    history, reached = derive_case(_vendor_case().case_ledger())
    sequences = case_state_sequences(history).sequences
    prefix = case_prefix(
        history,
        sequences,
        {p.participant: p.rm for p in reached.participants},
        reached.em(),
    )
    assert prefix is not None
    assert prefix.state.vendors == (VendorPath(RM.RECEIVED, CS_vf.Vf, CS_d.d),)
    assert (prefix.state.pxa, prefix.state.em) == (CS_pxa.pxa, EM.ACTIVE)
    assert prefix.history == (
        frozenset({Event(EventKind.EMBARGO_START)}),
        frozenset({Event(EventKind.V, 1)}),
    )


def test_a_case_with_no_vendor_has_no_prefix_and_no_numbers():
    ledger = Ledger()
    ledger.standard_genesis()
    history, reached = derive_case(ledger.case_ledger())
    assert case_prefix(history, [], {}, reached.em()) is None
    record = case_standing(ledger.case_ledger())
    assert record.moves
    for move in record.moves:
        assert move.changes is None
        assert move.unscored is not None
        assert move.advice or "no vendor" in move.unscored


def test_a_non_vendors_move_names_why_it_has_no_number():
    record = case_standing(_vendor_case().case_ledger())
    move = _scored(record, OWNER, "rm.validate")
    assert move.changes is None
    assert move.unscored is not None
    assert "moves no vendor's state" in move.unscored


def test_a_move_that_keeps_every_state_is_advice_with_no_number():
    """A second proposal while one is open keeps EM at PROPOSED."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                OWNER,
                [status("owner-r", OWNER, "RECEIVED")],
                roles=("CASE_OWNER",),
            )
        ],
        with_embargo=False,
    )
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add(
        "invite_to_embargo_on_case", "Invite", REPORTER, embargo(EMBARGO_2)
    )
    record = case_standing(ledger.case_ledger())
    assert record.case is not None
    assert record.case.em is EM.PROPOSED
    advice = [m for m in record.moves if m.advice]
    assert advice
    for move in advice:
        assert isinstance(move.move, EMMove)
        assert move.move.source is move.move.destination is EM.PROPOSED
        assert (move.changes, move.unscored) == (None, None)
    accept = [
        m
        for m in record.moves
        if isinstance(m.move, EMMove)
        and m.move.trigger is EM_Trigger.ACCEPT
        and m.move.destination is EM.ACTIVE
    ]
    assert accept and all(m.changes for m in accept)


def test_an_owners_end_before_any_fix_is_ready_is_an_other_exit():
    record = case_standing(_vendor_case().case_ledger())
    end = _scored(record, OWNER, "em.terminate")
    assert end.changes is not None
    (own_terms,) = [
        c for c in end.changes if c.notation == r"$\evExOwn \prec \evP$"
    ]
    # Ending the embargo otherwise rules out its exit on its own terms.
    assert own_terms.change < 0


def test_each_vendor_gets_its_own_changes_and_the_cross_vendor_ones():
    ledger = _vendor_case()
    seat_vendor(ledger, VENDOR_2, "Vf")
    record = case_standing(ledger.case_ledger())
    move = _scored(record, VENDOR, "cs.public_becomes_aware")
    assert move.changes is not None
    assert len(move.changes) == len(vendor_desiderata(2))
    assert {c.vendor for c in move.changes} == {VENDOR, VENDOR_2}
    crossed = {(c.vendor, c.other_vendor) for c in move.changes}
    assert (VENDOR, VENDOR_2) in crossed and (VENDOR_2, VENDOR) in crossed


def test_an_exited_embargo_stands_at_the_cause_its_exit_records():
    ledger = _vendor_case()
    publish(ledger, "Pxa")
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        CM,
        embargo(),
        content="END_TIME_REACHED",
    )
    history, reached = derive_case(ledger.case_ledger())
    prefix = case_prefix(
        history,
        case_state_sequences(history).sequences,
        {p.participant: p.rm for p in reached.participants},
        reached.em(),
    )
    assert prefix is not None
    assert prefix.state.embargo_end is EmbargoEnd.OWN_TERMS
    assert prefix.history[-1] == frozenset(
        {Event(EventKind.EXIT), Event(EventKind.EXIT_OWN_TERMS)}
    )


def _exited_prefix(cause: str | None = None) -> JointState:
    """The joint state of a vendor case whose embargo ends early, for the
    recorded *cause* (none when ``None``)."""
    ledger = _vendor_case()
    removal = ("remove_embargo_event_from_case", "Remove", CM, embargo())
    if cause is None:
        ledger.add(*removal, content="EARLY")
    else:
        ledger.add(*removal, content="EARLY", terminationCause={"kind": cause})
    history, reached = derive_case(ledger.case_ledger())
    prefix = case_prefix(
        history,
        case_state_sequences(history).sequences,
        {p.participant: p.rm for p in reached.participants},
        reached.em(),
    )
    assert prefix is not None
    return prefix.state


@pytest.mark.parametrize(
    ("cause", "end"),
    [
        ("FIX_READY", EmbargoEnd.OWN_TERMS),
        ("FIX_DEPLOYED", EmbargoEnd.OWN_TERMS),
        ("THREAT_SIGNAL", EmbargoEnd.THREAT_SIGNAL),
        ("OTHER", EmbargoEnd.OTHER),
    ],
)
def test_an_early_exit_stands_at_what_its_recorded_cause_means(cause, end):
    """Fixes ready or deployed end an embargo on its own terms."""
    state = _exited_prefix(cause)
    assert (state.em, state.embargo_end) == (EM.EXITED, end)


def test_an_early_exit_with_no_recorded_cause_is_an_other_exit():
    state = _exited_prefix()
    assert state.embargo_end is EmbargoEnd.OTHER


def _terminate() -> EMMove:
    return EMMove(
        participant=OWNER,
        trigger=EM_Trigger.TERMINATE,
        source=EM.ACTIVE,
        destination=EM.EXITED,
    )


@pytest.mark.parametrize(
    ("vf", "end"),
    [(CS_vf.VF, EmbargoEnd.OWN_TERMS), (CS_vf.Vf, EmbargoEnd.OTHER)],
)
def test_an_owners_early_end_is_own_terms_once_every_fix_is_ready(vf, end):
    vendor = VendorPath(RM.ACCEPTED, vf, CS_d.d)
    prefix = WalkPrefix(JointState((vendor,), CS_pxa.pxa, EM.ACTIVE, None))
    step = joint_step(prefix, {VENDOR: 1}, _terminate())
    assert step.state.embargo_end is end


def test_a_move_the_joint_model_holds_no_step_for_says_why():
    vendor = VendorPath(RM.RECEIVED, CS_vf.Vf, CS_d.d)
    # pXa is ephemeral: publication must come next, so no RM move may.
    prefix = WalkPrefix(JointState((vendor,), CS_pxa.pXa, EM.NONE, None))
    validate = RMMove(
        participant=VENDOR, source=RM.RECEIVED, destination=RM.VALID
    )
    with pytest.raises(NoJointStep, match=r"allows no rm\.validate by"):
        joint_step(prefix, {VENDOR: 1}, validate)
    with pytest.raises(NoJointStep, match="moves no vendor's state"):
        joint_step(prefix, {}, validate)
    keep = EMMove(
        participant=OWNER,
        trigger=EM_Trigger.PROPOSE,
        source=EM.PROPOSED,
        destination=EM.PROPOSED,
    )
    with pytest.raises(NoJointStep, match="keeps the case's EM state"):
        joint_step(prefix, {VENDOR: 1}, keep)


def test_a_vendors_move_refused_from_an_ephemeral_state_says_so():
    ledger = _vendor_case()
    publish(ledger, "pXa")
    record = case_standing(ledger.case_ledger())
    move = _scored(record, VENDOR, "rm.validate")
    assert move.changes is None and move.unscored is not None
    assert "allows no rm.validate" in move.unscored
    publication = _scored(record, VENDOR, "cs.public_becomes_aware")
    assert publication.changes


def test_a_public_case_offers_no_embargo_proposal():
    """Once public, no embargo is proposed that could never start."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                OWNER,
                [status("owner-r", OWNER, "RECEIVED")],
                roles=("CASE_OWNER",),
            )
        ],
        with_embargo=False,
    )
    seat_vendor(ledger, VENDOR, "Vf")
    unpublished = case_standing(ledger.case_ledger())
    assert [m for m in unpublished.moves if m.move.name == "em.propose"]
    publish(ledger, "Pxa")
    record = case_standing(ledger.case_ledger())
    assert record.case is not None
    assert record.case.em is EM.NONE
    assert not [m for m in record.moves if m.move.name == "em.propose"]


@pytest.mark.parametrize(
    "scenario",
    sorted(p.parent.name for p in RECORDINGS_DIR.glob("*/case-actor.jsonl")),
)
def test_every_vendor_and_em_move_of_a_recording_cut_short_is_scored(
    scenario, tmp_path
):
    """Every 4th cut of every recording: a vendor's or an EM move changing
    state carries a number for every vendor desideratum.  The hand-built
    tests above hold the states a stride can step over."""
    path = RECORDINGS_DIR / scenario / "case-actor.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    for entries in range(1, len(lines) + 1, 4):
        cut = tmp_path / f"{entries}.jsonl"
        cut.write_text("\n".join(lines[:entries]) + "\n", encoding="utf-8")
        (ledger,) = read_case_ledgers([cut]).cases.values()
        record = case_standing(ledger)
        vendors = [p.participant for p in record.participants if p.score]
        for move in record.moves:
            vendors_move = move.move.participant in vendors or isinstance(
                move.move, EMMove
            )
            if move.advice or not vendors or not vendors_move:
                continue
            assert move.changes is not None, (entries, move.move.name)
            assert len(move.changes) == len(vendor_desiderata(len(vendors)))


def test_a_scored_move_holds_a_number_or_a_reason():
    move = CSMove(
        participant=VENDOR,
        event=CSEvent.P,
        source=CS.Vfdpxa,
        destination=CS.VfdPxa,
    )
    with pytest.raises(ValidationError, match="changes or the reason"):
        ScoredMove(move=move)
    advice = EMMove(
        participant=VENDOR,
        trigger=EM_Trigger.PROPOSE,
        source=EM.PROPOSED,
        destination=EM.PROPOSED,
    )
    with pytest.raises(ValidationError, match="advice carries no number"):
        ScoredMove(move=advice, unscored="no")
    assert ScoredMove(move=advice).advice


def test_a_record_with_a_gap_holds_no_scored_move(tmp_path):
    ledger = _vendor_case()
    publish(ledger, "Pxa")
    rows = ledger.entries[:1] + ledger.entries[2:]
    path: Path = tmp_path / "holed.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    (holed,) = read_case_ledgers([path]).cases.values()
    record = case_standing(holed)
    assert record.gap is not None and record.moves == []
