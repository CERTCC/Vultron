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


"""Move advice for one vendor, and the generated rules over it (ADR-0216,
SHD-05-007)."""

from fractions import Fraction

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    OWNER,
    VENDOR as VENDOR_1,
    Ledger,
    participant,
    seat_unnotified_vendor,
    status,
)
from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import required_next_cs_events
from vultron.core.states.em import EM, EM_TRIGGER_ROLES, EM_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules import (
    ANY_ROLE,
    VENDOR,
    Machine,
    MatchStatus,
    MoveVerdict,
    PositionKey,
    VendorScore,
    case_points,
    conditional_verdicts,
    generated_rules,
    group_positions,
    machine_of,
    move_advice_desiderata,
    point_at,
    point_prefix,
    vendor_points,
)
from vultron.measure.advice import Band, Part, advise, move_shifts, open_moves
from vultron.measure.standing import StandingGap, StandingRecord, case_standing
from vultron.measure.standing.joint import joint_step


def _key(point) -> tuple[RM, CS, EM]:
    p = point.position
    return (p.rm, p.cs, p.em)


def _bands_at(
    rule_move: str,
) -> dict[tuple[RM, CS, EM], set[tuple[Band, bool]]]:
    """Each position's bands for *rule_move*, over every point there."""
    found: dict[tuple[RM, CS, EM], set[tuple[Band, bool]]] = {}
    for point in vendor_points():
        for v in point.verdicts:
            if v.move.name == rule_move and v.score is not None:
                found.setdefault(_key(point), set()).add(
                    (v.score.band, v.forced)
                )
    return found


def test_each_position_and_open_set_of_one_vendor_is_read_once():
    keys = [(*_key(p), p.open_desiderata) for p in vendor_points()]
    assert len(keys) == len(set(keys))
    assert keys[0][:3] == (RM.START, CS.vfdpxa, EM.NONE)
    assert keys[0][3] == tuple(move_advice_desiderata())
    assert all(p.position.consent is None for p in vendor_points())
    positions = {_key(p) for p in vendor_points()}
    assert (RM.DEFERRED, CS.Vfdpxa, EM.NONE) in positions


def test_a_desideratum_is_open_until_either_of_its_events_happens():
    deferred = [
        p.open_desiderata
        for p in vendor_points()
        if _key(p) == (RM.DEFERRED, CS.Vfdpxa, EM.NONE)
    ]
    assert len(deferred) == 2
    accepted, never = sorted(deferred, key=len)
    assert "Ac_i≺P" in never
    assert "Ac_i≺P" not in accepted
    assert set(accepted) < set(never)


@pytest.mark.spec("SHD-05-007")
def test_each_verdict_is_the_band_of_a_case_whose_only_scope_is_the_vendor():
    checked = 0
    for point in vendor_points():
        prefix = point_prefix(point)
        advice = advise(
            move_shifts(prefix, open_moves(prefix)), lambda _: False
        )
        for verdict in point.verdicts:
            if verdict.score is None:
                continue
            step = joint_step(prefix, {VENDOR: 1}, verdict.move)
            assert advice[step].band is verdict.score.band, (point, verdict)
            checked += 1
    assert checked > len(vendor_points())


def test_one_vendors_band_is_never_a_trade_off():
    bands = {
        v.score.band
        for p in vendor_points()
        for v in p.verdicts
        if v.score is not None
    }
    assert bands == {Band.HARM_FREE, Band.UNHELPFUL}


def test_a_score_whose_band_its_deciding_part_does_not_give_is_refused():
    with pytest.raises(ValidationError, match="harm-free band"):
        VendorScore(
            band=Band.UNHELPFUL,
            deciding_part=Part.END,
            deciding_size=Fraction(1, 2),
            changes={},
        )


def test_a_live_vendor_not_yet_notified_stands_at_vfd_beside_the_case():
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
    seat_unnotified_vendor(ledger, VENDOR_1)
    (point,) = case_points(case_standing(ledger.case_ledger()))
    assert point.position.cs is CS.vfdpxa
    assert point.position.rm is RM.START
    assert point.position.consent is None
    (aware,) = [
        v for v in point.verdicts if v.move.name == "cs.vendor_becomes_aware"
    ]
    (receipt,) = [v for v in point.verdicts if v.move.name == "rm.receive"]
    assert aware.score is not None
    assert aware.score == receipt.score
    assert aware.move.participant == VENDOR_1


def test_a_record_with_a_gap_has_no_points():
    record = StandingRecord(
        case_id="c",
        end_confirmed=False,
        gap=StandingGap(missing_log_indices=[1]),
    )
    assert case_points(record) == ()


def test_a_verdict_holds_a_band_or_why_not():
    verdict = point_at(RM.START, CS.vfdpxa, EM.NONE).verdicts[0]
    with pytest.raises(ValidationError, match="a band or the reason"):
        MoveVerdict(move=verdict.move, roles=verdict.roles)


# --- SHD-05-015 to SHD-05-017: the generated rules ---


@pytest.mark.spec("SHD-05-015")
def test_each_generated_rules_patterns_hold_exactly_its_bands_positions():
    rules = generated_rules()
    assert rules
    for rule in rules:
        expected = {
            key
            for key, bands in _bands_at(rule.move).items()
            if bands == {(rule.band, rule.forced)}
        }
        covered = {
            _key(p)
            for p in vendor_points()
            if any(
                pattern.match(p.position).status is MatchStatus.MATCHED
                for pattern in rule.patterns
            )
        }
        assert covered == expected, rule.move
        assert all(not pattern.reads_consent for pattern in rule.patterns)


@pytest.mark.spec("SHD-05-015")
def test_one_generated_rule_for_each_scored_move_band_and_forced_mark():
    moves = {
        v.move.name
        for p in vendor_points()
        for v in p.verdicts
        if v.score is not None
    }
    expected = {
        (move, *only)
        for move in moves
        for bands in _bands_at(move).values()
        if len(bands) == 1
        for only in bands
    }
    found = [(r.move, r.band, r.forced) for r in generated_rules()]
    assert len(found) == len(set(found))
    assert set(found) == expected


@pytest.mark.spec("SHD-05-029")
def test_a_position_whose_band_depends_on_its_history_is_conditional():
    conditional = conditional_verdicts()
    assert conditional
    for verdict in conditional:
        key = (verdict.position.rm, verdict.position.cs, verdict.position.em)
        assert {b.band for b in verdict.branches} == {
            band for band, _ in _bands_at(verdict.move)[key]
        }
        opens = [frozenset(b.open) for b in verdict.branches]
        assert len(set(opens)) == len(opens)
    covered = {(v.move, v.position) for v in conditional}
    for move in {v.move for v in conditional}:
        for key, bands in _bands_at(move).items():
            in_table = (move, PositionKey(*key)) in covered
            assert in_table == (len({b for b, _ in bands}) > 1)


@pytest.mark.spec("SHD-05-029")
def test_accepting_a_deferred_report_is_good_only_if_it_was_never_accepted():
    (verdict,) = [
        v
        for v in conditional_verdicts()
        if v.move == "rm.accept"
        and v.position == PositionKey(RM.DEFERRED, CS.Vfdpxa, EM.NONE)
    ]
    by_band = {b.band: b for b in verdict.branches}
    assert "Ac_i≺P" in by_band[Band.HARM_FREE].open
    assert "Ac_i≺P" in by_band[Band.UNHELPFUL].settled
    assert "harm-free while" in verdict.caveat
    assert "unhelpful once" in verdict.caveat


@pytest.mark.spec("SHD-05-030")
def test_a_verdict_on_a_forced_event_is_marked_forced():
    for point in vendor_points():
        required = required_next_cs_events(point.position.cs)
        for v in point.verdicts:
            event = getattr(v.move, "event", None)
            assert v.forced == (event is not None and event in required)
    forced = {(r.move, r.band) for r in generated_rules() if r.forced}
    assert ("cs.public_becomes_aware", Band.UNHELPFUL) in forced


@pytest.mark.spec("SHD-05-016")
def test_each_generated_rule_carries_the_role_move_advice_gives_its_move():
    for rule in generated_rules():
        machine = machine_of(rule.move)
        if machine is Machine.EM:
            role = EM_TRIGGER_ROLES[EM_Trigger(rule.move.split(".")[1])]
            assert rule.role == (role or ANY_ROLE)
        else:
            assert rule.role is CVDRole.VENDOR


@pytest.mark.spec("SHD-05-017")
def test_no_generated_rule_names_a_move_move_advice_does_not_band():
    banded = {
        v.move.name
        for p in vendor_points()
        for v in p.verdicts
        if v.score is not None
    }
    for rule in generated_rules():
        assert rule.move in banded
        assert machine_of(rule.move) is not Machine.PEC
    names = {r.move for r in generated_rules()}
    assert "cs.exploit_made_public" not in names
    assert "cs.attacks_are_observed" not in names


def test_generated_rules_are_the_same_on_every_build():
    from vultron.measure.action_rules import rules_from

    assert rules_from(vendor_points()) == generated_rules()


def test_grouping_covers_the_targets_and_none_of_the_others():
    targets = [
        PositionKey(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE),
        PositionKey(RM.ACCEPTED, CS.VFdPxa, EM.NONE),
    ]
    others = [
        PositionKey(RM.ACCEPTED, CS.Vfdpxa, EM.ACTIVE),
        PositionKey(RM.DEFERRED, CS.VFdpxa, EM.ACTIVE),
    ]
    patterns = group_positions(targets, others)
    assert patterns
    for key in targets:
        assert any(_covers(p, key) for p in patterns)
    for key in others:
        assert not any(_covers(p, key) for p in patterns)


def test_a_part_that_does_not_reach_every_state_names_only_covered_ones():
    targets = [PositionKey(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE)]
    others = [PositionKey(RM.DEFERRED, CS.VFdpxa, EM.ACTIVE)]
    (pattern,) = group_positions(targets, others)
    assert pattern.rm == {RM.ACCEPTED}
    assert pattern.em is None
    assert pattern.cs == "......"


def test_a_position_both_target_and_other_is_refused():
    key = PositionKey(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE)
    with pytest.raises(ValueError, match="both targets and others"):
        group_positions([key], [key])


def _covers(pattern, key: PositionKey) -> bool:
    return (
        pattern.matches_cs(key.cs)
        and (pattern.rm is None or key.rm in pattern.rm)
        and (pattern.em is None or key.em in pattern.em)
    )


@pytest.mark.spec("SHD-05-005")
def test_each_authored_move_is_a_move_move_advice_can_list():
    from vultron.measure.action_rules import authored_rules

    listed = {v.move.name for p in vendor_points() for v in p.verdicts}
    for rule in authored_rules():
        move = rule.move
        if move is None:
            continue
        if machine_of(move) is Machine.PEC:
            # Move advice has no PEC moves yet (#6677): named by its trigger.
            continue
        assert move in listed, rule
