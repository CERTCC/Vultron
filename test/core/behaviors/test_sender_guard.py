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

import inspect
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.core.behaviors import sender_entitlement
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderEntitlementConditionNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderIsCaseOwnerNode,
    SenderIsNoteAuthorNode,
    SenderIsOfferAddresseeNode,
    SenderIsOwnershipOffererNode,
    SenderIsOwnershipTransfereeNode,
    SenderIsProposalAddresseeNode,
    SenderIsRequestAddresseeNode,
    SenderMayAssertEmbargoNode,
    SenderRule,
    any_of,
)
from vultron.core.behaviors.sender_guard import (
    AddresseeRequest,
    CaseProposalRequest,
    OwnershipOfferRequest,
    ReportOfferRequest,
    SenderCheckContext,
    compose_sender_guard,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
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


# ---------------------------------------------------------------------------
# NAMED_ACTOR: one addressee kind, one small check per recorded request
# ---------------------------------------------------------------------------

REPORT_ID = "https://example.org/reports/sender-rule"
OFFER_ID = "https://example.org/activities/offer-sender-rule"
REPLY_ID = "https://example.org/activities/reply-sender-rule"


@pytest.mark.spec("HP-01-009")
@pytest.mark.parametrize(
    ("request_record", "case_id", "check"),
    [
        (
            CaseProposalRequest(report_id=REPORT_ID),
            None,
            SenderIsProposalAddresseeNode,
        ),
        (
            ReportOfferRequest(offer_id=OFFER_ID),
            None,
            SenderIsOfferAddresseeNode,
        ),
        (
            OwnershipOfferRequest(offer_id=OFFER_ID, reply_id=REPLY_ID),
            CASE_ID,
            SenderIsOwnershipTransfereeNode,
        ),
    ],
)
def test_named_actor_picks_the_check_for_the_record_holding_its_request(
    request_record: AddresseeRequest,
    case_id: str | None,
    check: type[SenderIsRequestAddresseeNode],
) -> None:
    """Each record has its own small check; all share the addressee base."""
    rule = (
        SenderRule.before_case(Kind.NAMED_ACTOR)
        if case_id is None
        else SenderRule.in_case(Kind.NAMED_ACTOR)
    )
    guard = compose_sender_guard(
        rule,
        SenderCheckContext(
            sender_id=VENDOR, case_id=case_id, request=request_record
        ),
    )
    assert type(guard) is check
    assert isinstance(guard, SenderIsRequestAddresseeNode)
    assert guard.guards_kind is Kind.NAMED_ACTOR


def test_named_actor_without_its_request_record_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="NAMED_ACTOR"):
        compose_sender_guard(
            SenderRule.in_case(Kind.NAMED_ACTOR),
            SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        )


def test_an_ownership_offer_check_without_a_case_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="case_id"):
        compose_sender_guard(
            SenderRule.before_case(Kind.NAMED_ACTOR),
            SenderCheckContext(
                sender_id=VENDOR,
                request=OwnershipOfferRequest(
                    offer_id=OFFER_ID, reply_id=REPLY_ID
                ),
            ),
        )


def _addressee_scenario(*records: PersistableModel) -> BTTestScenario:
    """A store holding *records*, and nothing else."""
    scenario = BTTestScenario(actor_id=OWNER)
    for record in records:
        scenario.dl.create(record)
    return scenario


def _run_addressee_check(
    scenario: BTTestScenario, request_record: AddresseeRequest, sender: str
) -> tuple[Status, str]:
    """Run the NAMED_ACTOR check for *request_record* in *scenario*."""
    guard = compose_sender_guard(
        SenderRule.before_case(Kind.NAMED_ACTOR),
        SenderCheckContext(sender_id=sender, request=request_record),
    )
    assert guard is not None
    result = scenario.run(guard, activity=SimpleNamespace(actor_id=sender))
    assert not result.internal_error, result.feedback_message
    return result.status, guard.feedback_message


def _proposal_link() -> VultronReportCaseLink:
    return VultronReportCaseLink(report_id=REPORT_ID, case_creator_id=VENDOR)


def _report_offer() -> VultronOfferRecord:
    return VultronOfferRecord(
        offer_id=OFFER_ID,
        report_id=REPORT_ID,
        offer_actor_id=OWNER,
        offer_to=[VENDOR],
    )


@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    ("request_record", "record", "spec"),
    [
        (
            CaseProposalRequest(report_id=REPORT_ID),
            _proposal_link,
            "CP-06-005",
        ),
        (ReportOfferRequest(offer_id=OFFER_ID), _report_offer, "RMB-08-004"),
    ],
)
def test_addressee_checks_compare_and_refuse_the_same_way(
    request_record: AddresseeRequest,
    record: Callable[[], PersistableModel],
    spec: str,
) -> None:
    """The base compares the sender with the recorded addressees and words
    every refusal alike, citing the record's own requirement."""
    scenario = _addressee_scenario(record())
    admitted, _ = _run_addressee_check(scenario, request_record, VENDOR)
    assert admitted == Status.SUCCESS
    refused, reason = _run_addressee_check(scenario, request_record, STRANGER)
    assert refused == Status.FAILURE
    assert f"Sender '{STRANGER}' is not" in reason
    assert f"('{VENDOR}')" in reason
    assert f"REFUSED ({spec}, HP-01-006)" in reason


def test_an_unrecorded_proposal_has_nothing_to_protect() -> None:
    status, _ = _run_addressee_check(
        _addressee_scenario(),
        CaseProposalRequest(report_id=REPORT_ID),
        STRANGER,
    )
    assert status == Status.SUCCESS


@pytest.mark.spec("RMB-08-004")
def test_an_unrecorded_report_offer_refuses_the_sender() -> None:
    status, reason = _run_addressee_check(
        _addressee_scenario(), ReportOfferRequest(offer_id=OFFER_ID), VENDOR
    )
    assert status == Status.FAILURE
    assert "No record of Offer" in reason


@pytest.mark.spec("CP-06-005")
def test_a_proposal_with_no_recorded_addressee_admits_nobody() -> None:
    status, reason = _run_addressee_check(
        _addressee_scenario(VultronReportCaseLink(report_id=REPORT_ID)),
        CaseProposalRequest(report_id=REPORT_ID),
        VENDOR,
    )
    assert status == Status.FAILURE
    assert "(nobody)" in reason


# ---------------------------------------------------------------------------
# CASE_OWNER against a recorded ownership-transfer Offer: the offerer
# ---------------------------------------------------------------------------


def test_case_owner_against_an_ownership_offer_is_the_offerer_check() -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderCheckContext(
            sender_id=OWNER,
            case_id=CASE_ID,
            request=OwnershipOfferRequest(
                offer_id=OFFER_ID, reply_id=REPLY_ID
            ),
        ),
    )
    assert isinstance(guard, SenderIsOwnershipOffererNode)
    assert guard.guards_kind is Kind.CASE_OWNER


# ---------------------------------------------------------------------------
# CASE_MANAGER: a required CASE_MANAGER does not pass through
# ---------------------------------------------------------------------------


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize(
    ("required", "admitted"), [(False, True), (True, False)]
)
def test_a_required_case_manager_refuses_a_case_this_store_lacks(
    required: bool, admitted: bool
) -> None:
    """Without the case there is no CASE_MANAGER to match: the bootstrap
    window passes through, a required CASE_MANAGER refuses."""
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_MANAGER),
        SenderCheckContext(
            sender_id=MANAGER,
            case_id=CASE_ID,
            case_manager_required=required,
        ),
    )
    assert guard is not None
    result = BTTestScenario(actor_id=REPLICA).run(
        guard, activity=SimpleNamespace(actor_id=MANAGER)
    )
    assert (result.status == Status.SUCCESS) is admitted
    if not admitted:
        assert "this store holds no case" in BTBridge.get_failure_reason(guard)


# ---------------------------------------------------------------------------
# AUTHOR: the author of the object being changed
# ---------------------------------------------------------------------------

NOTE_ID = "https://example.org/notes/sender-rule"


def _store_with_note(author: str) -> BTTestScenario:
    scenario = _store(MANAGER)
    scenario.dl.create(as_Note(id_=NOTE_ID, content="n", attributed_to=author))
    return scenario


@pytest.mark.spec("HP-01-009")
@pytest.mark.parametrize(
    ("sender", "admitted"),
    [(VENDOR, True), (REPLICA, False), (STRANGER, False)],
)
def test_author_kind_admits_only_the_objects_author(
    sender: str, admitted: bool
) -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.AUTHOR),
        SenderCheckContext(
            sender_id=sender, case_id=CASE_ID, authored_object_id=NOTE_ID
        ),
    )
    assert isinstance(guard, SenderIsNoteAuthorNode)
    assert guard.guards_kind is Kind.AUTHOR
    result = _store_with_note(VENDOR).run(
        guard, activity=SimpleNamespace(actor_id=sender)
    )
    assert not result.internal_error, result.feedback_message
    assert (result.status == Status.SUCCESS) is admitted


@pytest.mark.spec("CM-10-004")
def test_author_kind_refuses_an_author_no_longer_a_participant() -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.AUTHOR),
        SenderCheckContext(
            sender_id=STRANGER, case_id=CASE_ID, authored_object_id=NOTE_ID
        ),
    )
    assert guard is not None
    result = _store_with_note(STRANGER).run(
        guard, activity=SimpleNamespace(actor_id=STRANGER)
    )
    assert result.status == Status.FAILURE


def test_author_without_the_changed_object_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="authored_object_id"):
        compose_sender_guard(
            SenderRule.in_case(Kind.AUTHOR),
            SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        )


def test_author_without_a_case_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="case_id"):
        compose_sender_guard(
            SenderRule.before_case(Kind.AUTHOR),
            SenderCheckContext(sender_id=VENDOR, authored_object_id=NOTE_ID),
        )


# ---------------------------------------------------------------------------
# HP-01-009: the kinds are the closed vocabulary of sender standings
# ---------------------------------------------------------------------------

#: Kinds that are roles a participant holds; every other kind is a position.
ROLE_KINDS = frozenset({Kind.CASE_MANAGER, Kind.CASE_OWNER})

#: Condition nodes that are no one kind's guard: the factory's structural
#: refusals, and the two-kind embargo guard that #4437 piece 3 retires.
NOT_ONE_KINDS_GUARD: frozenset[type[SenderEntitlementConditionNode]] = (
    frozenset(
        {
            NoSenderAdmittedNode,
            SenderHoldsNoneOfNode,
            SenderMayAssertEmbargoNode,
        }
    )
)


@pytest.mark.spec("HP-01-009")
def test_no_position_kind_is_a_cvd_role() -> None:
    """A position held within one exchange never joins ``CVDRole``."""
    roles = {role.name for role in CVDRole}
    positions = set(Kind) - ROLE_KINDS
    assert {kind.name for kind in ROLE_KINDS} <= roles
    assert not {kind.name for kind in positions} & roles


def _module_guards() -> list[Any]:
    return [
        obj
        for _name, obj in inspect.getmembers(
            sender_entitlement, inspect.isclass
        )
        if obj.__module__ == sender_entitlement.__name__
        and hasattr(obj, "guards_kind")
        and obj is not SenderEntitlementConditionNode
        and not obj.__subclasses__()
    ]


@pytest.mark.spec("HP-01-009")
def test_every_sender_condition_node_guards_exactly_one_kind() -> None:
    """A check no kind names would be a position the docs never state."""
    unnamed = [
        cls.__name__
        for cls in _module_guards()
        if cls not in NOT_ONE_KINDS_GUARD
        and not isinstance(cls.guards_kind, Kind)
    ]
    assert not unnamed, f"condition nodes guarding no kind: {unnamed}"
    for cls in NOT_ONE_KINDS_GUARD:
        assert cls.guards_kind is None


@pytest.mark.spec("HP-01-009")
def test_every_kind_but_any_actor_has_a_guard() -> None:
    guarded = {cls.guards_kind for cls in _module_guards()} - {None}
    assert guarded == set(Kind) - {Kind.ANY_ACTOR}


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
