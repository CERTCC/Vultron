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


"""Move advice for one vendor, and the generated rules over it (ADR-0216
rule 5)."""

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
from vultron.core.states.em import EM, EM_TRIGGER_ROLES, EM_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules import (
    ANY_ROLE,
    VENDOR,
    Machine,
    MatchStatus,
    VendorScore,
    case_points,
    generated_rules,
    group_positions,
    machine_of,
    point_prefix,
    vendor_points,
)
from vultron.measure.action_rules.generated import _Key
from vultron.measure.advice import Band, Part, advise, move_shifts, open_moves
from vultron.measure.standing import case_standing
from vultron.measure.standing.joint import joint_step


def _key(point) -> tuple[RM, CS, EM]:
    p = point.position
    return (p.rm, p.cs, p.em)


def test_every_valid_position_of_one_vendor_is_read_once():
    keys = [_key(p) for p in vendor_points()]
    assert len(keys) == len(set(keys))
    assert (RM.START, CS.vfdpxa, EM.NONE) == keys[0]
    assert all(p.position.consent is None for p in vendor_points())


@pytest.mark.spec("SHD-05-007")
def test_each_verdict_is_the_band_of_a_case_whose_only_scope_is_the_vendor():
    checked = 0
    for point in vendor_points():
        prefix = point_prefix(point.position)
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
    names = {v.move.name for v in point.verdicts}
    assert "cs.vendor_becomes_aware" in names


# --- SHD-05-015 to SHD-05-017: the generated rules ---


@pytest.mark.spec("SHD-05-015")
def test_each_generated_rules_patterns_hold_exactly_its_bands_positions():
    rules = generated_rules()
    assert rules
    for rule in rules:
        expected = {
            _key(p)
            for p in vendor_points()
            if any(
                v.move.name == rule.move
                and v.score is not None
                and v.score.band is rule.band
                for v in p.verdicts
            )
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
def test_one_generated_rule_for_each_scored_move_and_band():
    expected = {
        (v.move.name, v.score.band)
        for p in vendor_points()
        for v in p.verdicts
        if v.score is not None
    }
    found = [(r.move, r.band) for r in generated_rules()]
    assert sorted(found) == sorted(expected)


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
        _Key(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE),
        _Key(RM.ACCEPTED, CS.VFdPxa, EM.NONE),
    ]
    others = [
        _Key(RM.ACCEPTED, CS.Vfdpxa, EM.ACTIVE),
        _Key(RM.DEFERRED, CS.VFdpxa, EM.ACTIVE),
    ]
    patterns = group_positions(targets, others)
    assert patterns
    for key in targets:
        assert any(_covers(p, key) for p in patterns)
    for key in others:
        assert not any(_covers(p, key) for p in patterns)


def test_a_part_that_does_not_reach_every_state_names_only_covered_ones():
    targets = [_Key(RM.ACCEPTED, CS.VFdpxa, EM.ACTIVE)]
    others = [_Key(RM.DEFERRED, CS.VFdpxa, EM.ACTIVE)]
    (pattern,) = group_positions(targets, others)
    assert pattern.rm == {RM.ACCEPTED}
    assert pattern.em is None
    assert pattern.cs == "......"


def _covers(pattern, key: _Key) -> bool:
    return (
        pattern.matches_cs(key.cs)
        and (pattern.rm is None or key.rm in pattern.rm)
        and (pattern.em is None or key.em in pattern.em)
    )
