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


"""The action-rule model and the authored table (ADR-0216, SHD-05-001 to SHD-05-006)."""

from typing import Any

import pytest
from pydantic import ValidationError

from test.measure.action_rules.builders import (
    ACTION_RULES_GROUP,
    make_rule,
    rule_fields,
)
from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.cs_actions import CS_ACTION_RULES, CSPattern
from vultron.core.states.em import EM, EM_TRANSITIONS, EM_Trigger
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules import (
    ACTION_MOVES,
    ANY_ROLE,
    NO_STATE_ACTIONS,
    AuthoredRule,
    ConsentReading,
    Machine,
    MatchStatus,
    Position,
    ProposalConsent,
    RuleNumbers,
    RulePattern,
    SourcePair,
    authored_rules,
    cs_action_pairs,
    machine_of,
    move_advice_desiderata,
    rule_label,
    rule_number,
    trigger_of,
)

pytestmark = ACTION_RULES_GROUP

_C = EmbargoConsentState


def _position(**parts: Any) -> Position:
    fields: dict[str, Any] = {
        "vendor": "v",
        "rm": RM.ACCEPTED,
        "cs": CS.VFdpxa,
        "em": EM.ACTIVE,
        "consent": ConsentReading(
            in_force=_C.AGREED,
            proposals=(ProposalConsent(proposal="p1", state=_C.INVITED),),
        ),
    }
    fields.update(parts)
    return Position(**fields)


_rule = make_rule


# --- SHD-05-001: a rule reads each part of one vendor's position ---


_PARTS: list[tuple[RulePattern, Position, Position]] = [
    (
        RulePattern(rm=frozenset({RM.ACCEPTED})),
        _position(),
        _position(rm=RM.DEFERRED),
    ),
    (RulePattern(cs="VF...."), _position(), _position(cs=CS.Vfdpxa)),
    (
        RulePattern(em=frozenset({EM.ACTIVE})),
        _position(),
        _position(em=EM.REVISE),
    ),
    (
        RulePattern(in_force=frozenset({_C.AGREED})),
        _position(),
        _position(consent=ConsentReading(in_force=_C.DECLINED)),
    ),
    (
        RulePattern(proposal=frozenset({_C.INVITED})),
        _position(),
        _position(
            consent=ConsentReading(
                proposals=(ProposalConsent(proposal="p1", state=_C.AGREED),)
            )
        ),
    ),
]


@pytest.mark.spec("SHD-05-001")
@pytest.mark.parametrize(
    ("pattern", "holds", "lacks"),
    _PARTS,
    ids=["rm", "cs", "em", "pec-in-force", "pec-proposal"],
)
def test_each_part_matches_only_a_position_holding_a_named_state(
    pattern, holds, lacks
):
    assert pattern.match(holds).status is MatchStatus.MATCHED
    assert pattern.match(lacks).status is MatchStatus.UNMATCHED


@pytest.mark.spec("SHD-05-001")
def test_a_part_that_matches_any_state_matches_every_position():
    any_pattern = RulePattern()
    positions = [holds for _, holds, _ in _PARTS] + [
        lacks for _, _, lacks in _PARTS
    ]
    assert all(
        any_pattern.match(p).status is MatchStatus.MATCHED for p in positions
    )


def test_an_empty_part_is_refused():
    with pytest.raises(ValidationError, match="names at least one state"):
        RulePattern(em=frozenset())


def test_a_malformed_cs_pattern_is_refused():
    with pytest.raises(ValidationError, match="action-rule pattern"):
        RulePattern(cs="vfdpx")


def test_no_embargo_in_force_matches_no_in_force_set():
    pattern = RulePattern(in_force=frozenset(_C))
    position = _position(consent=ConsentReading(in_force=None))
    assert pattern.match(position).status is MatchStatus.UNMATCHED


# --- SHD-05-003: a part the reading does not hold is undecided ---


@pytest.mark.spec("SHD-05-003")
@pytest.mark.parametrize(
    "pattern",
    [
        RulePattern(in_force=frozenset({_C.AGREED})),
        RulePattern(proposal=frozenset({_C.INVITED})),
    ],
    ids=["in-force", "proposal"],
)
def test_a_pec_part_over_a_reading_with_no_consent_is_undecided(pattern):
    match = pattern.match(_position(consent=None))
    assert match.status is MatchStatus.UNDECIDED
    assert match.proposals == ()


def test_a_part_that_fails_unmatches_even_beside_an_unknown_part():
    pattern = RulePattern(
        em=frozenset({EM.NONE}), proposal=frozenset({_C.INVITED})
    )
    match = pattern.match(_position(consent=None))
    assert match.status is MatchStatus.UNMATCHED


# --- SHD-05-020: an open-proposal part matches once per proposal ---


@pytest.mark.spec("SHD-05-020")
def test_a_proposal_part_matches_once_for_each_matching_proposal():
    consent = ConsentReading(
        proposals=(
            ProposalConsent(proposal="p1", state=_C.AGREED),
            ProposalConsent(proposal="p2", state=_C.INVITED),
        )
    )
    pattern = RulePattern(proposal=frozenset({_C.INVITED}))
    match = pattern.match(_position(consent=consent))
    assert match.status is MatchStatus.MATCHED
    assert match.proposals == ("p2",)


# --- SHD-05-004: roles, one action, desiderata from the list ---


@pytest.mark.spec("SHD-05-004")
@pytest.mark.parametrize(
    ("fields", "dropped", "message"),
    [
        ({}, "roles", r"roles\n  Field required"),
        ({"roles": frozenset()}, None, "at least one role"),
        ({}, "action", r"action\n  Field required"),
        (
            {"action": (Actions.MONITOR_FOR_ATTACKS, Actions.CLOSE_CASE)},
            None,
            "action",
        ),
        ({}, "reason", r"reason\n  Field required"),
        ({"reason": ""}, None, "reason"),
        ({"desiderata": ("V_i≺F_j",)}, None, "not in the move-advice"),
        ({"desiderata": ("E≺X",)}, None, "not in the move-advice"),
        ({"desiderata": ("D≺P", "D≺P")}, None, "more than once"),
    ],
    ids=[
        "no-role",
        "empty-role-set",
        "no-action",
        "two-actions",
        "no-reason",
        "empty-reason",
        "multi-party-desideratum",
        "equivalent-desideratum",
        "repeated-desideratum",
    ],
)
def test_a_rule_without_roles_one_action_and_listed_desiderata_is_refused(
    fields, dropped, message
):
    base = rule_fields(**fields)
    if dropped is not None:
        del base[dropped]
    with pytest.raises(ValidationError, match=message):
        AuthoredRule(**base)


def test_a_rule_names_a_role_set_or_any_role():
    assert _rule(roles=ANY_ROLE).roles_label == "any"
    named = _rule(roles=frozenset({CVDRole.COORDINATOR, CVDRole.REPORTER}))
    assert named.roles_label == "REPORTER, COORDINATOR"


@pytest.mark.spec("SHD-05-004")
def test_a_rule_with_a_reason_and_no_desideratum_is_accepted():
    rule = _rule(reason="Housekeeping: no action required", desiderata=())
    assert rule.desiderata == ()
    assert not rule.measured
    assert _rule().measured


@pytest.mark.spec("SHD-05-004")
def test_every_authored_rule_has_a_reason_and_listed_desiderata():
    listed = move_advice_desiderata()
    assert listed, "the move-advice list is not empty"
    for rule in authored_rules():
        assert rule.reason
        assert set(rule.desiderata) <= set(listed)
    assert any(not r.measured for r in authored_rules())
    assert any(r.measured for r in authored_rules())


def _sourced(action: Actions) -> list[AuthoredRule]:
    return [
        r
        for r in authored_rules()
        if r.source is not None and r.source.action is action
    ]


@pytest.mark.parametrize(
    "action",
    [
        Actions.CLOSE_CASE,
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        Actions.INITIATE_EMBARGO_TERMINATION,
        Actions.MONITOR_FOR_ADDITIONAL_ATTACKS,
        Actions.PUBLISH_DETECTION_FOR_EXPLOITS,
        Actions.PUBLISH_DETECTION_FOR_ATTACKS,
        Actions.PUBLICIZE_MITIGATION,
    ],
    ids=lambda a: a.name,
)
def test_a_rule_whose_reason_orders_no_events_names_no_desideratum(action):
    """The user's review of #6676 (D8, D10 to D13, D16)."""
    rules = _sourced(action)
    assert rules
    assert all(not r.measured for r in rules)


def test_every_publication_rule_names_its_actions_member():
    """A public exploit makes the public aware, but that is not a
    publication (#6676, D10), so no publication rule names the P move."""
    publications = {
        a for a, m in ACTION_MOVES.items() if m == "cs.public_becomes_aware"
    }
    for rule in authored_rules():
        if rule.source is not None and rule.source.action in publications:
            assert rule.action is rule.source.action, rule


# --- SHD-05-005, SHD-05-018, SHD-05-019: moves and actions ---


def test_a_rule_naming_no_move_is_refused():
    with pytest.raises(ValidationError, match="names no move"):
        _rule(action="cs.publish")


@pytest.mark.spec("SHD-05-018")
def test_each_authored_action_is_a_move_name_or_an_actions_member():
    for rule in authored_rules():
        if isinstance(rule.action, str):
            assert machine_of(rule.action) in Machine
        else:
            assert isinstance(rule.action, Actions)


@pytest.mark.spec("SHD-05-019")
def test_each_mapped_name_is_a_move_and_the_publications_map_to_p():
    for move in ACTION_MOVES.values():
        assert machine_of(move) in (Machine.RM, Machine.CS, Machine.EM)
    publications = [
        Actions.PUBLISH_VULNERABILITY,
        Actions.PUBLISH_FIX,
        Actions.PUBLISH_MITIGATION,
        Actions.PUBLISH_DETECTION_FOR_EXPLOITS,
        Actions.PUBLISH_DETECTION_FOR_ATTACKS,
        Actions.PUBLICIZE_PUBLISHED_EXPLOITS,
        Actions.PUBLICIZE_MITIGATION,
    ]
    for action in publications:
        assert ACTION_MOVES[action] == "cs.public_becomes_aware"
    assert ACTION_MOVES[Actions.PUBLISH_EXPLOIT_CODE] == (
        "cs.exploit_made_public"
    )
    assert ACTION_MOVES[Actions.CLOSE_CASE] == "rm.close"


@pytest.mark.spec("SHD-05-019")
def test_every_carried_action_is_mapped_or_changes_no_state():
    assert not set(ACTION_MOVES) & NO_STATE_ACTIONS
    for rule in authored_rules():
        if isinstance(rule.action, Actions):
            assert (
                rule.action in ACTION_MOVES or rule.action in NO_STATE_ACTIONS
            ), rule


# --- SHD-05-006, SHD-05-022: the carry-over ---


@pytest.mark.spec("SHD-05-006")
def test_the_source_pairs_are_the_cs_action_rules_less_the_vep_pair():
    expected = {
        (rule.pattern, action)
        for rule in CS_ACTION_RULES
        for action in rule.actions
    } - {("vfdpx.", Actions.INITIATE_VEP_USGOV)}
    carried = {
        (rule.source.pattern, rule.source.action)
        for rule in authored_rules()
        if rule.source is not None
    }
    assert carried == expected


@pytest.mark.spec("SHD-05-006")
def test_no_two_authored_rules_hold_the_same_source_pattern_roles_and_action():
    keys = [
        (rule.source, rule.pattern, rule.roles, rule.action)
        for rule in authored_rules()
    ]
    assert len(keys) == len(set(keys))


@pytest.mark.spec("SHD-05-022")
def test_each_authored_rule_records_a_held_source_pair_or_is_new():
    pairs = cs_action_pairs()
    for rule in authored_rules():
        if rule.source is not None:
            assert (rule.source.pattern, rule.source.action) in pairs


@pytest.mark.spec("SHD-05-022")
def test_a_source_pair_the_cs_rules_do_not_hold_is_refused():
    with pytest.raises(ValidationError, match="holds no pair"):
        SourcePair(pattern="......", action=Actions.CLOSE_CASE)


# --- SHD-05-023: never widened ---


@pytest.mark.spec("SHD-05-023")
@pytest.mark.parametrize("state", list(CS), ids=lambda s: s.name)
def test_a_carried_rule_matches_a_cs_state_only_where_its_source_does(state):
    for rule in authored_rules():
        if rule.source is None or not rule.pattern.matches_cs(state):
            continue
        assert CSPattern(rule.source.pattern).matches(state), rule


@pytest.mark.spec("SHD-05-023")
def test_a_carried_rule_wider_than_its_source_is_refused():
    with pytest.raises(ValidationError, match="never widened"):
        _rule(
            pattern=RulePattern(cs="......"),
            source=SourcePair(
                pattern=".....a", action=Actions.MONITOR_FOR_ATTACKS
            ),
        )


# --- SHD-05-026, SHD-05-027: EM and RM moves exist where they match ---


@pytest.mark.spec("SHD-05-026")
def test_each_em_move_rule_matches_only_its_moves_source_states():
    found = 0
    for rule in authored_rules():
        move = rule.move
        if move is None or machine_of(move) is not Machine.EM:
            continue
        found += 1
        sources = {
            s for s, _ in EM_TRANSITIONS[EM_Trigger(move.split(".")[1])]
        }
        assert rule.pattern.em is not None
        assert rule.pattern.em <= sources, rule
    assert found


@pytest.mark.spec("SHD-05-026")
@pytest.mark.parametrize(
    "em", [None, frozenset({EM.NONE})], ids=["any", "outside"]
)
def test_an_em_move_rule_outside_the_moves_sources_is_refused(em):
    with pytest.raises(ValidationError, match=r"em\.terminate"):
        _rule(action="em.terminate", pattern=RulePattern(em=em))


@pytest.mark.spec("SHD-05-027")
def test_each_close_case_rule_names_rm_close_and_skips_a_closed_report():
    closes = [
        r
        for r in authored_rules()
        if r.source is not None and r.source.action is Actions.CLOSE_CASE
    ]
    assert len(closes) == 4
    for rule in closes:
        assert rule.action == "rm.close"
        accepted = _position(
            rm=RM.ACCEPTED, cs=CS[rule.pattern.cs], consent=None
        )
        closed = _position(rm=RM.CLOSED, cs=CS[rule.pattern.cs], consent=None)
        assert rule.pattern.match(accepted).status is MatchStatus.MATCHED
        assert rule.pattern.match(closed).status is MatchStatus.UNMATCHED


@pytest.mark.spec("SHD-05-027")
def test_an_rm_close_rule_that_matches_a_closed_report_is_refused():
    with pytest.raises(ValidationError, match="CLOSED"):
        _rule(
            action="rm.close",
            pattern=RulePattern(rm=frozenset(RM) - {RM.START}),
        )


def test_a_pec_move_rule_needs_a_pec_part_its_move_exists_from():
    with pytest.raises(ValidationError, match="needs a PEC part"):
        _rule(action="pec.agree")
    with pytest.raises(ValidationError, match="AGREED"):
        _rule(
            action="pec.agree",
            pattern=RulePattern(proposal=frozenset({_C.AGREED})),
        )
    rule = _rule(
        action="pec.agree",
        pattern=RulePattern(proposal=frozenset({_C.INVITED})),
    )
    assert rule.move == "pec.agree"


def test_a_pec_move_rule_whose_in_force_part_it_cannot_leave_is_refused():
    with pytest.raises(ValidationError, match="from in-force PEC AGREED"):
        _rule(
            action="pec.agree",
            pattern=RulePattern(in_force=frozenset({_C.AGREED})),
        )
    rule = _rule(
        action="pec.agree",
        pattern=RulePattern(in_force=frozenset({_C.INVITED})),
    )
    assert rule.move == "pec.agree"


def test_the_r27_split_reads_em_and_drops_exited():
    negotiate = Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO
    split = [
        r
        for r in authored_rules()
        if r.source is not None and r.source.action is negotiate
    ]
    by_em = {
        em: sorted(str(r.action) for r in split if r.pattern.em == {em})
        for em in EM
    }
    assert by_em[EM.NONE] == ["em.propose"]
    assert by_em[EM.ACTIVE] == ["em.propose"]
    for em in (EM.PROPOSED, EM.REVISE):
        assert by_em[em] == [
            "em.accept",
            "em.propose",
            "em.reject",
            "pec.agree",
            "pec.decline",
        ]
    assert by_em[EM.EXITED] == []


def test_the_embargo_rules_carry_the_terms_advice():
    """Accept the shorter proposal, extend by revision, propose shorter
    terms, and reject rarely (#6676, D14)."""
    negotiate = _sourced(Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO)
    rejects = [
        r for r in negotiate if r.action in ("em.reject", "pec.decline")
    ]
    assert rejects
    assert all("rarely" in r.reason and not r.measured for r in rejects)
    shorter = [
        r
        for r in negotiate
        if r.action == "em.propose" and r.pattern.em != {EM.NONE}
    ]
    assert {next(iter(r.pattern.em or ())) for r in shorter} == {
        EM.PROPOSED,
        EM.ACTIVE,
        EM.REVISE,
    }


def test_a_move_name_splits_into_its_machine_and_trigger():
    assert machine_of("em.propose") is Machine.EM
    assert trigger_of("em.propose") == "propose"
    assert trigger_of("cs.fix_is_ready") == "fix_is_ready"
    with pytest.raises(ValueError, match="names no move"):
        trigger_of("em.no_such_trigger")


# --- labels the docs and the page share ---


def test_a_pattern_label_names_each_part_that_names_states():
    pattern = RulePattern(
        cs="VFdp..",
        rm=frozenset({RM.DEFERRED, RM.ACCEPTED}),
        em=frozenset({EM.ACTIVE}),
        in_force=frozenset({EmbargoConsentState.AGREED}),
        proposal=frozenset({EmbargoConsentState.INVITED}),
    )
    assert pattern.label == (
        "VFdp.. · RM DEFERRED, ACCEPTED · EM ACTIVE"
        " · in-force PEC AGREED · proposal PEC INVITED"
    )
    assert RulePattern().label == "......"


@pytest.mark.parametrize(
    ("fields", "carried", "label"),
    [
        (
            {"action": Actions.MONITOR_FOR_ATTACKS},
            Actions.MONITOR_FOR_ATTACKS,
            "Monitor for attacks",
        ),
        (
            {
                "action": "cs.fix_is_ready",
                "roles": frozenset({CVDRole.VENDOR}),
                "pattern": RulePattern(cs="Vfd..."),
                "source": SourcePair(
                    pattern="Vfd...", action=Actions.CREATE_FIX
                ),
            },
            Actions.CREATE_FIX,
            "Create fix (cs.fix_is_ready)",
        ),
        ({"action": "cs.fix_is_deployed"}, None, "cs.fix_is_deployed"),
    ],
    ids=["action", "carried-move", "new-move"],
)
def test_an_action_label_names_the_action_and_any_move(fields, carried, label):
    rule = make_rule(**fields)
    assert rule.carried_action == carried
    assert rule.action_label == label


def test_a_rule_is_numbered_by_its_place_in_the_table():
    rules = authored_rules()
    assert rule_number(rules[0], rules) == 1
    assert rule_label(rule_number(rules[-1], rules)) == f"Rule {len(rules)}"
    with pytest.raises(ValueError):
        rule_number(make_rule(), rules[:1])


def test_a_numbered_table_numbers_each_rule_object_once():
    rules = authored_rules()
    number = RuleNumbers(rules)
    assert [number(r) for r in rules] == list(range(1, len(rules) + 1))
    twin = make_rule()
    same = make_rule()
    assert twin == same
    numbered = RuleNumbers([twin, same])
    assert (numbered(twin), numbered(same)) == (1, 2)
    with pytest.raises(ValueError):
        numbered(make_rule())
