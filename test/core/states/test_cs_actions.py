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


"""The CVD action table under ``vultron/core/states/`` (#6515).

The legacy pattern table in
``vultron.core.case_states.patterns.potential_actions`` is the oracle
(ADR-0060): over every valid compound state the two give the same actions
in the same order.

The oracle reads any six-character string, the invalid ``vfDpxa`` included,
and answers it (#3355).  The table here reads only a `CS` member, so the
equality covers the 32 valid states and no more; the invalid one has no
member to ask about.
"""

import pytest

from vultron.core.case_states.patterns.potential_actions import action
from vultron.core.case_states.validations import valid_states
from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.cs_actions import (
    CS_ACTION_RULES,
    CSActionRule,
    _rule,
    cs_actions,
)
from vultron.core.states.cs_invariants import CSEvent, cs_happened_events


def test_the_oracle_and_the_enum_name_the_same_valid_states():
    assert sorted(valid_states()) == sorted(CS.__members__)


@pytest.mark.spec("CSB-17-001")
@pytest.mark.parametrize("state", list(CS), ids=lambda s: s.name)
def test_the_table_gives_the_legacy_actions_in_every_valid_state(state):
    assert list(cs_actions(state)) == action(state.name)


def test_the_invalid_state_vfDpxa_has_no_member_to_ask_about():
    """The legacy oracle answers ``vfDpxa`` (#3355); the table here cannot
    be asked, because no `CS` member names it."""
    assert "vfDpxa" not in CS.__members__


def test_the_table_keeps_the_legacy_patterns_in_order():
    from vultron.core.case_states.patterns.potential_actions import _ACTIONS

    assert [(r.pattern, r.actions) for r in CS_ACTION_RULES] == [
        (pattern, tuple(actions)) for pattern, actions in _ACTIONS.items()
    ]


def test_a_rule_matches_by_the_events_its_pattern_names():
    rule = _rule("V..p.a", Actions.PUBLISH_VULNERABILITY)
    assert rule.occurred == {CSEvent.V}
    assert rule.pending == {CSEvent.P, CSEvent.A}
    assert rule.matches(CS.VFDpXa)  # X is a wildcard position
    assert rule.matches(CS.VFDpxa)
    assert not rule.matches(CS.vfdpxa)
    assert not rule.matches(CS.VfdPxa)
    assert not rule.matches(CS.VfdpxA)


def test_an_all_wildcard_rule_matches_every_state():
    rule = CSActionRule("......", (Actions.CLOSE_CASE,))
    assert all(rule.matches(state) for state in CS)


@pytest.mark.parametrize(
    "pattern", ["", "vfdpx", "vfdpxaa", "fvdpxa", "vfdpq.", "VFDPX?"]
)
def test_a_malformed_pattern_is_refused(pattern):
    with pytest.raises(ValueError, match="action-rule pattern"):
        _rule(pattern, Actions.CLOSE_CASE)


@pytest.mark.parametrize("pattern", ["vfdpx", "vfdpq."])
def test_a_rule_built_directly_refuses_a_malformed_pattern(pattern):
    with pytest.raises(ValueError, match="action-rule pattern"):
        CSActionRule(pattern, (Actions.CLOSE_CASE,))


def test_a_rule_with_no_action_is_refused():
    with pytest.raises(ValueError, match="names no action"):
        _rule("......")


def test_an_action_two_rules_share_is_listed_once():
    actions = cs_actions(CS.VfdPXA)
    assert len(actions) == len(set(actions))
    assert Actions.PUBLISH_VULNERABILITY in actions


@pytest.mark.parametrize(
    ("state", "happened"),
    [
        (CS.vfdpxa, set()),
        (CS.VfdPxa, {CSEvent.V, CSEvent.P}),
        (CS.VFDPXA, set(CSEvent)),
    ],
)
def test_the_events_a_state_has_had(state, happened):
    assert cs_happened_events(state) == happened
