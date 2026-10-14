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

"""A sender guard composed from a declared :class:`SenderRule` (HP-01-008).

An any-of rule admits a sender holding any one of its kinds, and a two-sided
rule admits, on each side, exactly the kinds that side names.
"""

from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderIsCaseOwnerNode,
    SenderRule,
    any_of,
)
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
    compose_sender_guard,
)
from vultron.errors import VultronWiringError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/sender-rule"
MANAGER = "https://example.org/actors/case-manager"
OWNER = "https://example.org/actors/owner"
VENDOR = "https://example.org/actors/vendor"
REPLICA = "https://example.org/actors/replica"
STRANGER = "https://example.org/actors/stranger"

Kind = SenderEntitlementKind


def _store(receiver: str) -> BTTestScenario:
    """*receiver*'s store holding the case: MANAGER, OWNER, VENDOR, REPLICA."""
    scenario = BTTestScenario(actor_id=receiver)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Sender rule case")
    seed_case_manager_participant(scenario.dl, case, MANAGER)
    seed_case_owner_participant(scenario.dl, case, OWNER)
    seed_case_participant(scenario.dl, case, VENDOR)
    seed_case_participant(scenario.dl, case, REPLICA)
    scenario.dl.create(case)
    return scenario


def _admits(rule: SenderRule, receiver: str, sender: str) -> bool:
    """Whether the guard composed from *rule* admits *sender* at *receiver*."""
    guard = compose_sender_guard(
        rule, SenderCheckContext(sender_id=sender, case_id=CASE_ID)
    )
    assert guard is not None
    result = _store(receiver).run(
        guard, activity=SimpleNamespace(actor_id=sender)
    )
    assert not result.internal_error, result.feedback_message
    return result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# The rule value
# ---------------------------------------------------------------------------


def test_rule_with_no_side_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one side"):
        SenderRule()


def test_any_actor_cannot_share_a_side() -> None:
    with pytest.raises(ValueError, match="ANY_ACTOR"):
        SenderRule.before_case(Kind.ANY_ACTOR, Kind.CASE_OWNER)


def test_side_must_hold_kinds() -> None:
    with pytest.raises(ValueError, match="frozenset"):
        SenderRule(at_case_manager=frozenset({"CASE_OWNER"}))  # type: ignore[arg-type]


def test_in_case_states_both_case_sides() -> None:
    rule = SenderRule.in_case(Kind.CASE_OWNER)
    assert rule.at_case_manager == rule.at_participant == {Kind.CASE_OWNER}
    assert rule.outside_case == frozenset()
    assert rule.kinds == {Kind.CASE_OWNER}


def test_rule_is_frozen() -> None:
    rule = SenderRule.in_case(Kind.CASE_OWNER)
    with pytest.raises(AttributeError):
        rule.at_case_manager = any_of(Kind.CASE_MANAGER)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# HP-01-008: an any-of rule and a two-sided rule
# ---------------------------------------------------------------------------

ANY_OF = SenderRule.in_case(Kind.CASE_OWNER, Kind.CASE_MANAGER)


@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize(
    ("sender", "admitted"),
    [(OWNER, True), (MANAGER, True), (VENDOR, False), (STRANGER, False)],
)
def test_any_of_rule_admits_a_sender_holding_any_one_kind(
    sender: str, admitted: bool
) -> None:
    assert _admits(ANY_OF, MANAGER, sender) is admitted


#: At the CASE_MANAGER the Case Owner; at a participant the CASE_MANAGER.
TWO_SIDED = SenderRule(
    at_case_manager=any_of(Kind.CASE_OWNER),
    at_participant=any_of(Kind.CASE_MANAGER),
)


@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize(
    ("receiver", "sender", "admitted"),
    [
        # The CASE_MANAGER side admits exactly the Case Owner.
        (MANAGER, OWNER, True),
        (MANAGER, VENDOR, False),
        (MANAGER, STRANGER, False),
        # The participant side admits exactly the CASE_MANAGER.
        (REPLICA, MANAGER, True),
        (REPLICA, OWNER, False),
        (REPLICA, VENDOR, False),
    ],
)
def test_two_sided_rule_admits_exactly_each_sides_kinds(
    receiver: str, sender: str, admitted: bool
) -> None:
    assert _admits(TWO_SIDED, receiver, sender) is admitted


@pytest.mark.spec("HP-01-006")
def test_any_of_refusal_names_every_kind_the_side_accepts() -> None:
    guard = compose_sender_guard(
        ANY_OF, SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID)
    )
    assert isinstance(guard, py_trees.composites.Selector)
    assert isinstance(guard.children[-1], SenderHoldsNoneOfNode)
    result = _store(MANAGER).run(
        guard, activity=SimpleNamespace(actor_id=VENDOR)
    )
    assert result.status == Status.FAILURE
    reason = BTBridge.get_failure_reason(guard)
    assert "none of the standings" in reason
    assert "CASE_MANAGER, CASE_OWNER" in reason


@pytest.mark.spec("HP-01-008")
def test_an_empty_side_admits_no_one() -> None:
    rule = SenderRule(at_case_manager=any_of(Kind.CASE_OWNER))
    assert _admits(rule, MANAGER, OWNER) is True
    assert _admits(rule, REPLICA, MANAGER) is False


def test_same_kinds_on_both_case_sides_compose_without_a_side_check() -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderCheckContext(sender_id=OWNER, case_id=CASE_ID),
    )
    assert isinstance(guard, SenderIsCaseOwnerNode)


# ---------------------------------------------------------------------------
# An activity that names no case: the outside-case side
# ---------------------------------------------------------------------------


def test_any_actor_before_a_case_composes_no_guard() -> None:
    guard = compose_sender_guard(
        SenderRule.before_case(Kind.ANY_ACTOR),
        SenderCheckContext(sender_id=STRANGER),
    )
    assert guard is None


@pytest.mark.spec("HP-01-006")
def test_case_rule_refuses_an_activity_that_names_no_case() -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.ACTIVE_PARTICIPANT),
        SenderCheckContext(sender_id=VENDOR),
    )
    assert isinstance(guard, NoSenderAdmittedNode)
    result = _store(MANAGER).run(guard)
    assert result.status == Status.FAILURE
    reason = BTBridge.get_failure_reason(guard)
    assert "a receiver that holds no case for it" in reason


def test_invitee_without_an_invite_id_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="invite_id"):
        compose_sender_guard(
            SenderRule.in_case(Kind.INVITEE),
            SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        )


def test_named_actor_has_no_factory_guard_yet() -> None:
    with pytest.raises(VultronWiringError, match="NAMED_ACTOR"):
        compose_sender_guard(
            SenderRule.in_case(Kind.NAMED_ACTOR),
            SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        )


# ---------------------------------------------------------------------------
# The factory composes the guard from the rule
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
def test_factory_refusal_names_the_missing_standing() -> None:
    tree = create_receive_activity_tree(
        name="RuleTreeBT",
        case_id=CASE_ID,
        precondition_guards=[],
        sender_rule=TWO_SIDED,
        sender_context=SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
    )
    guard = next(
        n
        for n in tree.iterate()
        if isinstance(n, py_trees.composites.Sequence)
        and n.name == "SenderRuleGuard"
    )
    activity = SimpleNamespace(actor_id=VENDOR)
    result = _store(MANAGER).run(guard, activity=activity)
    assert result.status == Status.FAILURE
    reason = BTBridge.get_failure_reason(guard)
    assert "is not the Case Owner" in reason


def test_factory_rejects_a_rule_without_a_context() -> None:
    with pytest.raises(VultronWiringError, match="sender_context"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=None,
            precondition_guards=[],
            sender_rule=ANY_OF,
        )


def test_factory_rejects_a_rule_and_a_guard_together() -> None:
    with pytest.raises(VultronWiringError, match="not both"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=None,
            precondition_guards=[],
            sender_guard=NoSenderAdmittedNode(side="nobody"),
            sender_rule=ANY_OF,
            sender_context=SenderCheckContext(sender_id=VENDOR),
        )


def test_factory_rejects_a_context_naming_another_case() -> None:
    with pytest.raises(VultronWiringError, match="names case"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=None,
            precondition_guards=[],
            sender_rule=ANY_OF,
            sender_context=SenderCheckContext(
                sender_id=VENDOR, case_id=CASE_ID
            ),
        )


def test_factory_rejects_a_context_without_a_rule() -> None:
    with pytest.raises(VultronWiringError, match="without a sender_rule"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=None,
            precondition_guards=[],
            sender_context=SenderCheckContext(sender_id=VENDOR),
        )
