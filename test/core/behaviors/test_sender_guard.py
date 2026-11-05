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

"""A sender guard composed from a declared :class:`SenderRule` (HP-01-025).

An any-of rule admits a sender holding any one of its kinds, and a two-sided
rule admits, on each side, exactly the kinds that side names.
"""

import importlib
import inspect
import logging
import pkgutil
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, get_args

import py_trees
import pytest
from py_trees.common import Status

from test.architecture._received_tree_builds import built_received_trees
from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from test.support.received import TEST_SENDER_POSITION, with_evidence
from vultron.core.behaviors import sender_entitlement
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.leave_case_trigger_tree import (
    create_leave_case_trigger_tree,
)
from vultron.core.behaviors.case.nodes.carried_snapshot import (
    StoreEmbeddedParticipantsNode,
)
from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderClosureNotRecordedNode,
    SenderEntitlementConditionNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderIsActiveLedgerParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
    SenderIsNoteAuthorNode,
    SenderIsOfferAddresseeNode,
    SenderIsOfferingCaseOwnerNode,
    SenderIsOwnershipOffererNode,
    SenderIsOwnershipTransfereeNode,
    SenderIsProposalAddresseeNode,
    SenderIsProposalAuthorNode,
    SenderIsRequestAddresseeNode,
    SenderRule,
    any_of,
    failure_is_the_refusal,
    in_declaration_order,
    refuse_by_placement,
)
from vultron.core.behaviors.sender_guard import (
    AddresseeRequest,
    AuthoredCaseProposal,
    AuthoredNote,
    AuthoredObject,
    AuthoredParticipantRecord,
    CaseProposalRequest,
    ClosedSenderCheck,
    LedgerActivityContext,
    OwnershipOfferRequest,
    ReportOfferRequest,
    SenderCheckContext,
    closed_sender_door,
    compose_sender_guard,
    sender_guard_refused,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import EngageCaseReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
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
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Sender rule case"
    )
    seed_case_manager_participant(scenario.dl, case, MANAGER)
    seed_case_owner_participant(scenario.dl, case, OWNER)
    seed_case_participant(scenario.dl, case, VENDOR)
    seed_case_participant(scenario.dl, case, REPLICA)
    scenario.dl.create(case)
    return scenario


def _owner_role_check(
    guard: py_trees.behaviour.Behaviour | None,
) -> py_trees.behaviour.Behaviour:
    """The role check of a composed ``CASE_OWNER`` guard on a case.

    The factory composes the closure check ahead of it (CM-23-018).
    """
    assert isinstance(guard, py_trees.composites.Sequence)
    closure, role = guard.children
    assert isinstance(closure, SenderClosureNotRecordedNode)
    return role


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
# HP-01-023, HP-01-024: an any-of rule and a two-sided rule
# ---------------------------------------------------------------------------

ANY_OF = SenderRule.in_case(Kind.CASE_OWNER, Kind.CASE_MANAGER)


@pytest.mark.spec("HP-01-008", "HP-01-023")
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


@pytest.mark.spec("HP-01-008", "HP-01-024")
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


@pytest.mark.spec("HP-01-008", "HP-01-024")
def test_an_empty_side_admits_no_one() -> None:
    rule = SenderRule(at_case_manager=any_of(Kind.CASE_OWNER))
    assert _admits(rule, MANAGER, OWNER) is True
    assert _admits(rule, REPLICA, MANAGER) is False


def test_same_kinds_on_both_case_sides_compose_without_a_side_check() -> None:
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderCheckContext(sender_id=OWNER, case_id=CASE_ID),
    )
    assert isinstance(_owner_role_check(guard), SenderIsCaseOwnerNode)


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
    role = _owner_role_check(guard)
    assert isinstance(role, SenderIsOwnershipOffererNode)
    assert role.guards_kind is Kind.CASE_OWNER


@pytest.mark.spec("CM-21-019")
def test_case_owner_for_a_new_ownership_offer_is_the_offering_owner_check() -> (
    None
):
    """A new Offer's own id selects the check that also admits its
    recorded sender's redelivery (HP-01-003); without it, the role alone."""
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderCheckContext(
            sender_id=OWNER, case_id=CASE_ID, ownership_proposal_id=OFFER_ID
        ),
    )
    role = _owner_role_check(guard)
    assert isinstance(role, SenderIsOfferingCaseOwnerNode)
    assert role.guards_kind is Kind.CASE_OWNER


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
            sender_id=sender,
            case_id=CASE_ID,
            authored_object=AuthoredNote(note_id=NOTE_ID),
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
            sender_id=STRANGER,
            case_id=CASE_ID,
            authored_object=AuthoredNote(note_id=NOTE_ID),
        ),
    )
    assert guard is not None
    result = _store_with_note(STRANGER).run(
        guard, activity=SimpleNamespace(actor_id=STRANGER)
    )
    assert result.status == Status.FAILURE


def test_author_without_the_changed_object_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="authored_object"):
        compose_sender_guard(
            SenderRule.in_case(Kind.AUTHOR),
            SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        )


# The case proposal's author: the proposer this CASE_MANAGER recorded for the
# proposal id, which the sender chose (CP-05-006, #4719).

PROPOSAL_ID = "https://example.org/proposals/sender-rule"


def _proposal_author_guard(sender: str) -> py_trees.behaviour.Behaviour:
    guard = compose_sender_guard(
        SenderRule.before_case(Kind.AUTHOR),
        SenderCheckContext(
            sender_id=sender,
            authored_object=AuthoredCaseProposal(proposal_id=PROPOSAL_ID),
        ),
    )
    assert isinstance(guard, SenderIsProposalAuthorNode)
    assert guard.guards_kind is Kind.AUTHOR
    return guard


def _admission(proposer: str) -> CaseProposalAdmissionRecord:
    return CaseProposalAdmissionRecord(
        proposal_id=PROPOSAL_ID, case_actor_id=MANAGER, proposer_uri=proposer
    )


def _decline(proposer: str) -> CaseProposalDeclineRecord:
    return CaseProposalDeclineRecord(
        proposal_id=PROPOSAL_ID, case_actor_id=MANAGER, proposer_uri=proposer
    )


def _stored_proposal(proposer: str) -> as_CaseProposal:
    """The proposal as the Accept or Reject path stores it, read on its own:
    CP-05-010 counts a stored proposal as recording it."""
    return as_CaseProposal(
        id_=PROPOSAL_ID,
        attributed_to=proposer,
        object_=gen_report(),
        target=MANAGER,
    )


@pytest.mark.spec("HP-01-009")
@pytest.mark.spec("CP-05-010")
@pytest.mark.parametrize(
    ("records", "sender", "admitted"),
    [
        ((), STRANGER, True),
        ((_admission(VENDOR),), VENDOR, True),
        ((_admission(VENDOR),), STRANGER, False),
        ((_decline(VENDOR),), VENDOR, True),
        ((_decline(VENDOR),), STRANGER, False),
        ((_admission(VENDOR), _decline(VENDOR)), STRANGER, False),
        ((_stored_proposal(VENDOR),), VENDOR, True),
        ((_stored_proposal(VENDOR),), STRANGER, False),
        ((_stored_proposal(VENDOR + "/"),), VENDOR, True),
    ],
    ids=[
        "new-proposal",
        "admitted-proposer",
        "admitted-for-another",
        "declined-proposer",
        "declined-for-another",
        "both-records-for-another",
        "stored-proposal-proposer",
        "stored-proposal-for-another",
        "stored-proposal-trailing-slash",
    ],
)
def test_author_kind_admits_only_a_proposals_recorded_proposer(
    records: tuple[PersistableModel, ...], sender: str, admitted: bool
) -> None:
    scenario = _store(MANAGER)
    for record in records:
        scenario.dl.create(record)
    result = scenario.run(
        _proposal_author_guard(sender),
        activity=SimpleNamespace(actor_id=sender),
    )
    assert not result.internal_error, result.feedback_message
    assert (result.status == Status.SUCCESS) is admitted
    if not admitted:
        assert VENDOR in result.feedback_message
        assert "HP-01-006" in result.feedback_message


class _FailingReads:
    """A store whose reads fail, standing in for a store error."""

    def read(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("store unavailable")


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CP-05-010")
def test_a_store_error_never_admits_the_proposal_sender() -> None:
    """A read error propagates: it fails the tree, which refuses, and the
    guard never answers ``SUCCESS`` because it could not tell."""
    guard = _proposal_author_guard(STRANGER)
    assert isinstance(guard, SenderIsProposalAuthorNode)
    guard.datalayer = _FailingReads()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="store unavailable"):
        guard.update()


def test_author_without_a_case_is_a_wiring_error() -> None:
    with pytest.raises(VultronWiringError, match="case_id"):
        compose_sender_guard(
            SenderRule.before_case(Kind.AUTHOR),
            SenderCheckContext(
                sender_id=VENDOR, authored_object=AuthoredNote(note_id=NOTE_ID)
            ),
        )


# ---------------------------------------------------------------------------
# CM-23-018: every ACTIVE_PARTICIPANT guard refuses a sender that may not act
# ---------------------------------------------------------------------------

_VENDOR_PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"


def _leave(record: CaseParticipant) -> None:
    """The vendor's closure recorded: its RM is ``CLOSED`` (CM-23-001)."""
    record.participant_statuses.append(
        ParticipantStatus(
            context=CASE_ID,
            attributed_to=VENDOR,
            rm=RmDimension(state=RM.CLOSED),
        )
    )


def _uninvite(record: CaseParticipant) -> None:
    """The vendor has not joined, so it is inert (CM-10-004)."""
    record.joined = False


def _remove(record: CaseParticipant) -> None:
    """The vendor carries the removal fact (CM-31-001)."""
    record.removal_activity = f"{CASE_ID}/activities/remove-vendor"


_MAY_NOT_ACT = pytest.mark.parametrize(
    "standing",
    [_leave, _uninvite, _remove],
    ids=["closed", "inert", "removed"],
)


def _store_where_vendor(
    standing: Callable[[CaseParticipant], None] | None,
) -> BTTestScenario:
    """The CASE_MANAGER's store, the vendor's record changed by *standing*."""
    scenario = _store_with_note(VENDOR)
    if standing is not None:
        record = scenario.dl.read(_VENDOR_PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        standing(record)
        scenario.dl.save(record)
    return scenario


def _composed_vendor_guard(kind: Kind) -> py_trees.behaviour.Behaviour:
    guard = compose_sender_guard(
        SenderRule.in_case(kind),
        SenderCheckContext(
            sender_id=VENDOR,
            case_id=CASE_ID,
            authored_object=AuthoredNote(note_id=NOTE_ID),
        ),
    )
    assert guard is not None
    return guard


#: Each guard of the ACTIVE_PARTICIPANT standing, built for the vendor.
_VENDOR_GUARDS = pytest.mark.parametrize(
    "make_guard",
    [
        lambda: _composed_vendor_guard(Kind.ACTIVE_PARTICIPANT),
        lambda: _composed_vendor_guard(Kind.AUTHOR),
    ],
    ids=["active-participant", "note-author"],
)


@pytest.mark.spec("CM-23-018", "CM-23-020")
@_VENDOR_GUARDS
def test_each_active_participant_guard_admits_an_active_open_sender(
    make_guard: Callable[[], py_trees.behaviour.Behaviour],
) -> None:
    """Control: the vendor, active and not closed, is admitted by each guard."""
    result = _store_where_vendor(None).run(
        make_guard(), activity=SimpleNamespace(actor_id=VENDOR)
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.SUCCESS, result.feedback_message


@pytest.mark.spec("CM-23-018", "CM-23-020", "CM-10-004")
@_MAY_NOT_ACT
@_VENDOR_GUARDS
@pytest.mark.spec("CM-23-054")
def test_each_active_participant_guard_refuses_a_sender_that_may_not_act(
    make_guard: Callable[[], py_trees.behaviour.Behaviour],
    standing: Callable[[CaseParticipant], None],
) -> None:
    """A closed, an inert and a removed sender each fail every guard."""
    result = _store_where_vendor(standing).run(
        make_guard(), activity=SimpleNamespace(actor_id=VENDOR)
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE


@pytest.mark.spec("CM-23-018")
@pytest.mark.parametrize(
    ("standing", "admitted"),
    [(None, True), (_leave, False), (_uninvite, True), (_remove, True)],
    ids=["open", "closed", "inert", "removed"],
)
def test_participant_kind_refuses_only_a_closed_sender(
    standing: Callable[[CaseParticipant], None] | None, admitted: bool
) -> None:
    """``PARTICIPANT`` admits any listed record but one at RM CLOSED.

    An inert or removed participant keeps the standing (#4437); a closed one
    has left the case and may act on nothing further (CM-23-018).
    """
    result = _store_where_vendor(standing).run(
        _composed_vendor_guard(Kind.PARTICIPANT),
        activity=SimpleNamespace(actor_id=VENDOR),
    )
    assert not result.internal_error, result.feedback_message
    assert (result.status == Status.SUCCESS) is admitted


@pytest.mark.spec("CM-23-018")
def test_participant_kind_reads_closure_from_the_record_it_found() -> None:
    """A closed sender is refused even when the index does not list it.

    The roster lookup finds the record by scanning the participants, so the
    closure is read from that record, not looked up again through
    ``actor_participant_index``: the two lookups cannot disagree.
    """
    scenario = _store_where_vendor(_leave)
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    case.actor_participant_index.pop(VENDOR)
    scenario.dl.save(case)
    result = scenario.run(
        _composed_vendor_guard(Kind.PARTICIPANT),
        activity=SimpleNamespace(actor_id=VENDOR),
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE
    assert "RM CLOSED" in (result.feedback_message or "")


@pytest.mark.spec("CM-23-018", "SYNC-03-005")
@pytest.mark.spec("CM-23-048")
def test_ledger_peer_kind_composes_the_resync_guard() -> None:
    """``LEDGER_PEER`` is guarded by the bare active check of SYNC-03-005."""
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.LEDGER_PEER),
        SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
    )
    assert isinstance(guard, SenderIsActiveLedgerParticipantNode)
    assert guard.guards_kind is Kind.LEDGER_PEER


# ---------------------------------------------------------------------------
# HP-01-009: the kinds are the closed vocabulary of sender standings
# ---------------------------------------------------------------------------

#: Kinds that are roles a participant holds; every other kind is a position.
ROLE_KINDS = frozenset({Kind.CASE_MANAGER, Kind.CASE_OWNER})

#: Condition nodes that are no one kind's guard: the factory's structural
#: refusals.
NOT_ONE_KINDS_GUARD: frozenset[type[SenderEntitlementConditionNode]] = (
    frozenset({NoSenderAdmittedNode, SenderHoldsNoneOfNode})
)


@pytest.mark.spec("HP-01-009")
def test_no_position_kind_is_a_cvd_role() -> None:
    """A position held within one exchange never joins ``CVDRole``."""
    roles = {role.name for role in CVDRole}
    positions = set(Kind) - ROLE_KINDS
    assert {kind.name for kind in ROLE_KINDS} <= roles
    assert not {kind.name for kind in positions} & roles


def _reraise_import_error(name: str) -> None:
    """``walk_packages`` error hook: a failed import must not shrink the scan."""
    raise  # noqa: PLE0704


def _module_guards() -> list[Any]:
    """Every leaf guard class defined anywhere in the sender-entitlement package."""
    modules = [sender_entitlement] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(
            sender_entitlement.__path__,
            f"{sender_entitlement.__name__}.",
            onerror=_reraise_import_error,
        )
    ]
    return [
        obj
        for module in modules
        for _name, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__
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
@pytest.mark.spec("HP-01-018")
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


@pytest.mark.spec("HP-01-007")
def test_factory_takes_no_sender_guard_built_by_a_tree() -> None:
    """The guard comes from the declared rule alone (HP-01-025, #4437)."""
    parameters = inspect.signature(create_receive_activity_tree).parameters
    assert "sender_guard" not in parameters


def test_factory_rejects_a_context_naming_another_case() -> None:
    """A tree that commits judges the sender against the case it commits to."""
    with pytest.raises(VultronWiringError, match="names case"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=f"{CASE_ID}/other",
            precondition_guards=[],
            sender_rule=ANY_OF,
            sender_context=SenderCheckContext(
                sender_id=VENDOR, case_id=CASE_ID
            ),
        )


def test_a_tree_that_commits_nothing_judges_the_context_case() -> None:
    """A notice tree (no commit) checks the sender against the case its
    activity names, as the received ``Announce(EmbargoEvent)`` tree does."""
    tree = create_receive_activity_tree(
        name="RuleTreeBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=ANY_OF,
        sender_context=SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
    )

    # intake, post-close, addressee door, sender guard, and the answer to
    # the sender's ledger position in that case (SYNC-18-007)
    assert len(tree.children) == 5


def test_factory_rejects_a_context_without_a_rule() -> None:
    with pytest.raises(VultronWiringError, match="without a sender_rule"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=None,
            precondition_guards=[],
            sender_context=SenderCheckContext(sender_id=VENDOR),
        )


# ---------------------------------------------------------------------------
# CM-23-018: a closed Case Owner holds no CASE_OWNER standing
# ---------------------------------------------------------------------------


def _close_participant(
    scenario: BTTestScenario, actor_id: str
) -> BTTestScenario:
    """Record *actor_id*'s closure (RM ``CLOSED``) on the open case."""
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    record = scenario.dl.read(case.actor_participant_index[actor_id])
    assert isinstance(record, CaseParticipant)
    record.participant_statuses.append(
        ParticipantStatus(
            context=CASE_ID,
            attributed_to=actor_id,
            rm=RmDimension(state=RM.CLOSED),
        )
    )
    scenario.dl.save(record)
    return scenario


def _close_owner(scenario: BTTestScenario) -> BTTestScenario:
    """Record the Case Owner's closure (RM ``CLOSED``) on the open case."""
    return _close_participant(scenario, OWNER)


#: Every shape of ``CASE_OWNER`` check the factory composes on a case.
_OWNER_CONTEXTS = {
    "role": SenderCheckContext(sender_id=OWNER, case_id=CASE_ID),
    "new-ownership-offer": SenderCheckContext(
        sender_id=OWNER, case_id=CASE_ID, ownership_proposal_id=OFFER_ID
    ),
    "ownership-offer-withdrawal": SenderCheckContext(
        sender_id=OWNER,
        case_id=CASE_ID,
        request=OwnershipOfferRequest(offer_id=OFFER_ID, reply_id=REPLY_ID),
    ),
}


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    "rule",
    [
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderRule.to_case_manager(Kind.CASE_OWNER),
    ],
    ids=["in-case", "to-case-manager"],
)
@pytest.mark.parametrize("label", list(_OWNER_CONTEXTS))
def test_a_closed_case_owner_is_refused(rule: SenderRule, label: str) -> None:
    """An owner whose closure the case records may act on nothing (#4746)."""
    guard = compose_sender_guard(rule, _OWNER_CONTEXTS[label])
    assert guard is not None
    result = _close_owner(_store(MANAGER)).run(
        guard, activity=SimpleNamespace(actor_id=OWNER)
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE
    assert "already closed" in BTBridge.get_failure_reason(guard)


@pytest.mark.spec("CM-23-018")
def test_an_open_case_owner_is_still_admitted() -> None:
    assert _admits(SenderRule.in_case(Kind.CASE_OWNER), MANAGER, OWNER)


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("HP-01-008")
def test_a_closed_owner_holding_another_kind_is_refused_naming_every_kind() -> (
    None
):
    """In an any-of side the closed owner falls through to the last arm."""
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER, Kind.CASE_MANAGER),
        SenderCheckContext(sender_id=OWNER, case_id=CASE_ID),
    )
    assert guard is not None
    result = _close_owner(_store(MANAGER)).run(
        guard, activity=SimpleNamespace(actor_id=OWNER)
    )
    assert result.status == Status.FAILURE
    assert "none of the standings" in BTBridge.get_failure_reason(guard)


@pytest.mark.spec("RSH-01-002")
@pytest.mark.spec("CM-23-003")
def test_the_case_owner_standing_read_still_asks_the_role_alone() -> None:
    """``SenderIsCaseOwnerNode`` is unchanged: the Leave, suggest-actor,
    status and embargo trees read it to pick an arm, closed owner or not."""
    node = SenderIsCaseOwnerNode(sender_actor_id=OWNER, case_id=CASE_ID)
    result = _close_owner(_store(MANAGER)).run(node)
    assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# A case resolved at run time (#4696)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-008", "SYNC-13-006", "SYNC-03-005")
@pytest.mark.parametrize(
    ("kind", "node_type"),
    [
        (Kind.CASE_MANAGER, SenderIsCaseManagerNode),
        (Kind.LEDGER_PEER, SenderIsActiveLedgerParticipantNode),
    ],
)
def test_ledger_context_composes_the_in_case_guard(
    kind: SenderEntitlementKind, node_type: type
) -> None:
    """A ledger activity's guard is the in-case side's, not ``outside_case``:
    its node reads the case from the entry the activity carries."""
    guard = compose_sender_guard(
        SenderRule.in_case(kind), LedgerActivityContext()
    )
    assert isinstance(guard, node_type)
    assert getattr(guard, "_case_id", None) is None


@pytest.mark.spec("HP-01-008")
def test_ledger_context_refuses_a_kind_that_needs_the_case_at_build_time() -> (
    None
):
    with pytest.raises(VultronWiringError, match="read from a ledger"):
        compose_sender_guard(
            SenderRule.in_case(Kind.PARTICIPANT), LedgerActivityContext()
        )


@pytest.mark.spec("HP-01-008")
def test_ledger_context_refuses_a_two_sided_rule() -> None:
    with pytest.raises(VultronWiringError, match="same kinds"):
        compose_sender_guard(TWO_SIDED, LedgerActivityContext())


def test_factory_rejects_a_ledger_context_on_a_tree_with_a_case() -> None:
    with pytest.raises(VultronWiringError, match="names case"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=CASE_ID,
            precondition_guards=[],
            sender_rule=SenderRule.in_case(Kind.CASE_MANAGER),
            sender_context=LedgerActivityContext(),
        )


class _ResolveCase(CaseResolving, py_trees.behaviour.Behaviour):
    """A read-only step standing in for a case resolution."""

    def update(self) -> Status:
        return Status.SUCCESS


@pytest.mark.spec("HP-01-008", "CLP-10-010")
def test_case_resolution_runs_just_before_the_sender_guard() -> None:
    """The steps that resolve the case run after the post-close guard and
    before the guard composed from the rule, so an activity about a case
    this store lacks is refused as such (#2255)."""
    resolve = _ResolveCase(name="ResolveCase")
    tree = create_receive_activity_tree(
        name="RuleTreeBT",
        case_id=CASE_ID,
        precondition_guards=[],
        sender_rule=SenderRule.in_case(Kind.PARTICIPANT),
        sender_context=SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
        case_resolution=[resolve],
    )
    names = [child.name for child in tree.children]
    at = names.index("ResolveCase")
    assert names[at - 2] == "CaseOpenToExternalWrites"
    assert names[at - 1] == "ActivityAddressedToReceiverNode"
    assert names[at + 1] == "SenderIsParticipantNode"


def test_factory_rejects_a_case_resolution_without_a_rule() -> None:
    with pytest.raises(VultronWiringError, match="only with a sender_rule"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=CASE_ID,
            precondition_guards=[],
            case_resolution=[_ResolveCase(name="ResolveCase")],
        )


@pytest.mark.spec("HP-01-006")
def test_factory_rejects_a_case_resolution_that_writes() -> None:
    """The steps run before the sender guard, so a write there would let an
    unentitled sender leave state behind."""
    writer = StoreEmbeddedParticipantsNode(
        as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="snapshot"
        ),
        CASE_ID,
    )
    with pytest.raises(VultronWiringError, match="may only read"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=CASE_ID,
            precondition_guards=[],
            sender_rule=SenderRule.in_case(Kind.PARTICIPANT),
            sender_context=SenderCheckContext(
                sender_id=VENDOR, case_id=CASE_ID
            ),
            case_resolution=[writer],
        )


class _ResolvingEmitter(
    CaseResolving, EmitCapable, py_trees.behaviour.Behaviour
):
    """A step marked as resolving that can also emit."""

    def update(self) -> Status:
        return Status.SUCCESS


class _UnmarkedStep(py_trees.behaviour.Behaviour):
    """A step without the CaseResolving marker, such as an unmarked writer."""

    def update(self) -> Status:
        return Status.SUCCESS


@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    "step",
    [
        _ResolvingEmitter(name="Emitter"),
        _UnmarkedStep(name="Unmarked"),
        py_trees.composites.Sequence(
            name="Wrapped", memory=False, children=[_UnmarkedStep(name="U")]
        ),
    ],
    ids=["emitter", "unmarked-leaf", "unmarked-leaf-in-a-composite"],
)
def test_factory_admits_only_read_only_case_resolving_steps(
    step: py_trees.behaviour.Behaviour,
) -> None:
    """Not every writer is marked, so a step is admitted by its marker."""
    with pytest.raises(VultronWiringError, match="may only read"):
        create_receive_activity_tree(
            name="RuleTreeBT",
            case_id=CASE_ID,
            precondition_guards=[],
            sender_rule=SenderRule.in_case(Kind.PARTICIPANT),
            sender_context=SenderCheckContext(
                sender_id=VENDOR, case_id=CASE_ID
            ),
            case_resolution=[step],
        )


class _Refuse(py_trees.behaviour.Behaviour):
    """A precondition guard that refuses."""

    def update(self) -> Status:
        return Status.FAILURE


def _participant_tree(
    sender: str, guards: list[py_trees.behaviour.Behaviour]
) -> py_trees.composites.Sequence:
    return create_receive_activity_tree(
        name="RuleTreeBT",
        case_id=CASE_ID,
        precondition_guards=guards,
        sender_rule=SenderRule.in_case(Kind.PARTICIPANT),
        sender_context=SenderCheckContext(sender_id=sender, case_id=CASE_ID),
    )


@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    ("sender", "guards", "refused", "status"),
    [
        (STRANGER, [], True, Status.FAILURE),
        (VENDOR, [], False, Status.SUCCESS),
        (VENDOR, [_Refuse(name="Refuse")], False, Status.FAILURE),
    ],
    ids=["unentitled-sender", "entitled-sender", "a-later-guard-refuses"],
)
def test_sender_guard_refused_names_only_the_sender_guards_refusal(
    sender: str,
    guards: list[py_trees.behaviour.Behaviour],
    refused: bool,
    status: Status,
) -> None:
    tree = _participant_tree(sender, guards)
    event = with_evidence(
        EngageCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            activity_id="https://example.org/activities/engage-guard",
            actor_id=sender,
            object_=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_=CASE_ID,
                name="Sender rule case",
            ),
            semantic_type=MessageSemantics.ENGAGE_CASE,
            activity=VultronActivity(
                id_="https://example.org/activities/engage-guard",
                type_="Join",
                actor=sender,
                to=[MANAGER],
            ),
        )
    )
    result = _store(MANAGER).run(tree, activity=event)
    assert result.status == status
    assert sender_guard_refused(tree) is refused


# ---------------------------------------------------------------------------
# A check a later arm can overrule logs no refusal (#5460)
# ---------------------------------------------------------------------------


#: The one function every sender check logs its refusal reason from
#: (``refuse_by_placement``), so a line is recognised by the rule that chose
#: its level rather than by its node class or its wording (#5786).
_REFUSAL_FUNC = refuse_by_placement.__name__


def _refusal_lines(
    caplog: pytest.LogCaptureFixture, node_class: type
) -> list[logging.LogRecord]:
    """Every line *node_class* logged from the shared refusal helper.

    Keyed on the helper rather than on the logger: ``py_trees`` writes its own
    ``tick()``/``stop()`` lines to the same per-class logger.
    """
    name = f"{node_class.__module__}.{node_class.__name__}"
    return [
        record
        for record in caplog.records
        if record.name == name and record.funcName == _REFUSAL_FUNC
    ]


def _all_refusal_lines(
    caplog: pytest.LogCaptureFixture,
) -> list[logging.LogRecord]:
    """Every line any sender check logged from the shared refusal helper."""
    return [
        record for record in caplog.records if record.funcName == _REFUSAL_FUNC
    ]


def _refusals_logged(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Every captured message a reader would read as a refusal (WARNING+)."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    ]


def _case_manager_checks(
    guard: py_trees.behaviour.Behaviour | None,
) -> list[SenderIsCaseManagerNode]:
    """Every ``CASE_MANAGER`` check inside the composed *guard*."""
    assert guard is not None
    return [
        node
        for node in guard.iterate()
        if isinstance(node, SenderIsCaseManagerNode)
    ]


def _only_case_manager_check(
    guard: py_trees.behaviour.Behaviour | None,
) -> SenderIsCaseManagerNode:
    found = _case_manager_checks(guard)
    assert len(found) == 1, found
    return found[0]


@pytest.mark.spec("HP-01-006", "HP-01-023", "SL-03-002")
def test_a_kind_a_later_arm_overrules_logs_no_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The Case Owner's activity reaches the CASE_MANAGER: the ``CASE_MANAGER``
    arm fails, the ``CASE_OWNER`` arm admits it, and nothing was refused, so
    the first arm's line is DEBUG and carries no ``REFUSED`` wording (#5460).
    """
    guard = compose_sender_guard(
        ANY_OF, SenderCheckContext(sender_id=OWNER, case_id=CASE_ID)
    )
    assert guard is not None
    check = _only_case_manager_check(guard)
    assert failure_is_the_refusal(check) is False
    with caplog.at_level(logging.DEBUG):
        result = _store(MANAGER).run(
            guard, activity=SimpleNamespace(actor_id=OWNER)
        )
    assert result.status == Status.SUCCESS
    lines = _refusal_lines(caplog, SenderIsCaseManagerNode)
    assert len(lines) == 1, [record.getMessage() for record in lines]
    assert lines[0].levelno == logging.DEBUG
    assert "REFUSED" not in lines[0].getMessage()
    assert "is not the CASE_MANAGER" in lines[0].getMessage()
    # Stripping the REFUSED group keeps the CASE_MANAGER it resolved, which
    # is the whole diagnostic the deleted WARNING carried as "expected '<id>'".
    assert f"which is '{MANAGER}'" in lines[0].getMessage()
    assert _refusals_logged(caplog) == []


@pytest.mark.spec("HP-01-006", "SL-03-002")
def test_the_lone_kind_of_a_side_still_logs_its_refusal_at_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``CASE_MANAGER`` alone on the side is the guard's whole answer, so its
    FAILURE is the tree's refusal and stays at WARNING (#5460)."""
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_MANAGER),
        SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
    )
    assert guard is not None
    check = _only_case_manager_check(guard)
    assert failure_is_the_refusal(check) is True
    with caplog.at_level(logging.DEBUG):
        result = _store(REPLICA).run(
            guard, activity=SimpleNamespace(actor_id=VENDOR)
        )
    assert result.status == Status.FAILURE
    lines = _refusal_lines(caplog, SenderIsCaseManagerNode)
    assert [record.levelno for record in lines] == [logging.WARNING]
    assert "REFUSED (HP-01-006)" in lines[0].getMessage()
    assert f"which is '{MANAGER}'" in lines[0].getMessage()
    assert (
        BTBridge.get_failure_reason(guard)
        == lines[0].getMessage().split(": ", 1)[1]
    )


@pytest.mark.spec("HP-01-006", "HP-01-023", "SL-03-002")
def test_an_any_of_side_still_logs_one_refusal_for_a_sender_it_refuses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Demoting an overruled arm to DEBUG keeps the refusal signal: the side's
    last arm names every standing it accepts, at WARNING (BT-13-001)."""
    guard = compose_sender_guard(
        ANY_OF, SenderCheckContext(sender_id=STRANGER, case_id=CASE_ID)
    )
    assert guard is not None
    with caplog.at_level(logging.DEBUG):
        result = _store(MANAGER).run(
            guard, activity=SimpleNamespace(actor_id=STRANGER)
        )
    assert result.status == Status.FAILURE
    refusals = _refusals_logged(caplog)
    assert len(refusals) == 1, refusals
    assert "none of the standings" in refusals[0]
    assert [
        record.levelno
        for record in _refusal_lines(caplog, SenderIsCaseManagerNode)
    ] == [logging.DEBUG]


def _side_guard(
    guard: py_trees.behaviour.Behaviour | None, rule: SenderRule, side: str
) -> py_trees.behaviour.Behaviour:
    """The part of the composed *guard* that judges *rule*'s *side*.

    A two-sided rule dispatches on the receiver's side, so each side's kinds
    are the last child of their arm; anything else composes one guard.
    """
    assert guard is not None
    if side == "outside_case" or rule.at_case_manager == rule.at_participant:
        return guard
    arm_name = (
        "AtCaseManager" if side == "at_case_manager" else "AtParticipant"
    )
    arm = next(child for child in guard.children if child.name == arm_name)
    return arm.children[-1]


def _declared_case_manager_sides() -> list[tuple[str, str, SenderRule]]:
    """Every (use case, side, rule) whose side names ``CASE_MANAGER``."""
    sides = ("at_case_manager", "at_participant", "outside_case")
    found: list[tuple[str, str, SenderRule]] = []
    for entry in SEMANTIC_REGISTRY:
        use_case = entry.use_case_class
        rule = getattr(use_case, "sender_entitlement", None)
        if use_case is None or not isinstance(rule, SenderRule):
            continue
        found.extend(
            (use_case.__name__, side, rule)
            for side in sides
            if Kind.CASE_MANAGER in getattr(rule, side)
        )
    return found


@pytest.mark.spec("HP-01-006", "HP-01-023", "SL-03-002")
def test_every_declared_side_places_the_case_manager_check_knowingly() -> None:
    """Each received rule naming ``CASE_MANAGER`` composes a check that knows
    whether its own FAILURE refuses the sender: ``False`` where the side names
    another kind that may still admit it, ``True`` where it is the side's
    whole answer.  Read from the composed guards, so a rule that gains or
    loses a kind moves with it, and recorded per side rather than counted, so
    no subject is lost to a rename (#5460)."""
    overruled: dict[str, bool] = {}
    final: dict[str, bool] = {}
    for name, side, rule in _declared_case_manager_sides():
        guard = compose_sender_guard(
            rule,
            SenderCheckContext(
                sender_id=VENDOR,
                case_id=None if side == "outside_case" else CASE_ID,
                invite_id="https://example.org/activities/invite",
                request=CaseProposalRequest(report_id=REPORT_ID),
                authored_object=AuthoredNote(note_id=NOTE_ID),
            ),
        )
        checks = _case_manager_checks(_side_guard(guard, rule, side))
        assert checks, f"{name}.{side} composed no CASE_MANAGER check"
        answers = {failure_is_the_refusal(check) for check in checks}
        if len(getattr(rule, side)) > 1:
            overruled[f"{name}.{side}"] = answers == {False}
        else:
            final[f"{name}.{side}"] = answers == {True}
    assert overruled, "no declared side names CASE_MANAGER beside another kind"
    assert final, "no declared side names CASE_MANAGER alone"
    assert [row for row, ok in overruled.items() if not ok] == []
    assert [row for row, ok in final.items() if not ok] == []


# ---------------------------------------------------------------------------
# One refusal per refused sender, on every declared any-of side (#5786)
# ---------------------------------------------------------------------------


def _multi_kind_sides() -> list[tuple[str, str, SenderRule]]:
    """Every (use case, side, rule) whose side names more than one kind.

    Derived from ``SEMANTIC_REGISTRY``, not from a list, so a rule that gains
    a kind joins the subjects and one that loses one leaves them.  The
    CASE_MANAGER pair ``{CASE_OWNER, CASE_MANAGER}`` the first version of this
    assertion used is the one pair whose non-last arm already logged nothing
    above DEBUG, so it could not have failed (#5786).
    """
    sides = ("at_case_manager", "at_participant", "outside_case")
    found: dict[tuple[str, str], SenderRule] = {}
    for entry in SEMANTIC_REGISTRY:
        use_case = entry.use_case_class
        rule = getattr(use_case, "sender_entitlement", None)
        if use_case is None or not isinstance(rule, SenderRule):
            continue
        for side in sides:
            if len(getattr(rule, side)) > 1:
                found.setdefault((use_case.__name__, side), rule)
    return [(name, side, found[name, side]) for name, side in sorted(found)]


#: The authored objects an ``AUTHOR`` side is ticked with: the factory picks a
#: different check for each (``_author_node``), so a side naming ``AUTHOR`` is
#: ticked once per shape rather than once for a guessed one.  ``AuthoredObject``
#: has a third member, ``AuthoredCaseProposal``, left out for the reason
#: ``test_every_authored_shape_is_ticked_or_excused`` states and pins.
_AUTHORED_SHAPES: dict[str, AuthoredNote | AuthoredParticipantRecord] = {
    "note": AuthoredNote(note_id=NOTE_ID),
    "participant-record": AuthoredParticipantRecord(
        participant_id=_VENDOR_PARTICIPANT_ID
    ),
}


#: The authored object a side's ``AUTHOR`` kind is asked about, or ``None`` on
#: a side that names no ``AUTHOR`` kind.
_AuthoredShape = AuthoredNote | AuthoredParticipantRecord | None


def _any_of_side_rows() -> list[tuple[str, SenderRule, str, _AuthoredShape]]:
    """Every any-of side to tick, with the authored object its kinds need."""
    rows: list[tuple[str, SenderRule, str, _AuthoredShape]] = []
    for name, side, rule in _multi_kind_sides():
        if Kind.AUTHOR in getattr(rule, side):
            rows.extend(
                (f"{name}.{side}[{label}]", rule, side, authored)
                for label, authored in _AUTHORED_SHAPES.items()
            )
        else:
            rows.append((f"{name}.{side}", rule, side, None))
    return rows


def _receiver_for(side: str) -> str:
    """The actor whose store judges *side*'s arm of a two-sided rule."""
    return VENDOR if side == "at_participant" else MANAGER


@pytest.mark.spec("HP-01-009", "SL-03-002")
def test_every_authored_shape_is_ticked_or_excused() -> None:
    """``_AUTHORED_SHAPES`` covers every authored object but the excused one.

    ``_author_node`` dispatches on the authored object's type, so a member of
    ``AuthoredObject`` that ``_AUTHORED_SHAPES`` does not carry is an
    ``AUTHOR`` arm whose log level the test below never asserts — and it would
    go unverified in silence rather than failing (#5535).  Asked of the union
    itself, so a fourth member fails here and has to be decided.

    ``AuthoredCaseProposal`` is the one excused, because ticking it would
    assert the wrong thing: ``SenderIsProposalAuthorNode`` returns SUCCESS for
    a sender the store records no proposer for, so the side would admit the
    stranger and the refusal this test is about would never happen.  The only
    side naming that shape is a lone ``AUTHOR`` side, whose arm is the guard's
    whole answer, so its level is WARNING either way.
    """
    excused = {AuthoredCaseProposal}
    assert (
        set(get_args(AuthoredObject))
        == {type(shape) for shape in _AUTHORED_SHAPES.values()} | excused
    )


@pytest.mark.spec("HP-01-006", "HP-01-023", "SL-03-002", "SL-03-003")
def test_every_any_of_side_logs_one_refusal_for_a_sender_it_refuses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sender no arm of an any-of side admits gets one WARNING, and it is
    the side's last arm naming every standing the side accepts (BT-13-001).

    Asked of every multi-kind side ``SEMANTIC_REGISTRY`` declares rather than
    of one chosen pair, because the pair the first version of this assertion
    chose was the only one whose earlier arms were already quiet: for the
    other four the same assertion saw two WARNINGs (#5786).  Each arm that
    did log is recorded per side, so no subject is lost to a count (#3984).
    """
    stores: dict[str, BTTestScenario] = {}
    rows = _any_of_side_rows()
    assert len(rows) > 1, "no declared side names more than one kind"
    warnings: dict[str, list[str]] = {}
    overruled: dict[str, list[tuple[int, bool]]] = {}
    for label, rule, side, authored in rows:
        guard = compose_sender_guard(
            rule,
            SenderCheckContext(
                sender_id=STRANGER,
                case_id=None if side == "outside_case" else CASE_ID,
                invite_id="https://example.org/activities/invite",
                request=CaseProposalRequest(report_id=REPORT_ID),
                authored_object=authored,
            ),
        )
        assert guard is not None, f"{label} composed no guard"
        receiver = _receiver_for(side)
        if receiver not in stores:
            # One store per receiver: seeding a second store for the same
            # actor id in one test re-creates its participant records.
            stores[receiver] = _store(receiver)
        scenario = stores[receiver]
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            result = scenario.run(
                guard, activity=SimpleNamespace(actor_id=STRANGER)
            )
        assert result.status == Status.FAILURE, label
        warnings[label] = _refusals_logged(caplog)
        # Every other arm that logged: its level, and whether its line still
        # claims a refusal.  Both must be (DEBUG, no REFUSED) — SL-03-003.
        overruled[label] = [
            (record.levelno, "REFUSED" in record.getMessage())
            for record in _all_refusal_lines(caplog)
            if not record.name.endswith(SenderHoldsNoneOfNode.__name__)
        ]
        kinds = ", ".join(
            kind.name for kind in in_declaration_order(getattr(rule, side))
        )
        assert BTBridge.get_failure_reason(guard) == (
            "Sender holds none of the standings this activity accepts"
            f" ({kinds}) — REFUSED (HP-01-006, HP-01-023)"
        ), label

    assert {
        label: lines for label, lines in warnings.items() if len(lines) != 1
    } == {}, "a refused sender drew more than one WARNING"
    assert {
        label: lines
        for label, lines in warnings.items()
        if "none of the standings" not in lines[0]
    } == {}, "the one WARNING is not the arm naming every standing"
    # Before judging the overruled arms' levels, require that some arm was
    # overruled at all: `any()` over an empty list is False, so a DEBUG branch
    # that went silent would pass the next assertion while proving nothing of
    # SL-03-003 (the demoted arm must still record its reason, minus REFUSED).
    assert {
        label: seen for label, seen in overruled.items() if not seen
    } == {}, (
        "a side logged nothing from an overruled arm, so SL-03-003 is unpinned"
    )
    assert {
        label: seen
        for label, seen in overruled.items()
        if any(level != logging.DEBUG or refused for level, refused in seen)
    } == {}, "an overruled arm logged above DEBUG, or still claimed a refusal"


@pytest.mark.spec("CM-23-018", "ID-05-003", "SL-03-001")
def test_the_closed_sender_check_keeps_its_info_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``SenderClosureNotRecordedNode`` stays at INFO wherever it sits.

    Its FAILURE is not a refusal — the handler reports a repeat of a closing
    act ``SKIPPED`` (ID-05-003) — so SL-03-002's WARNING-or-DEBUG choice does
    not apply to it, and the reason is in its docstring.  It carries no
    ``REFUSED`` wording, so nothing reads it as the tree's answer either
    (SL-03-003).  Ticked in both placements it has, which
    ``failure_is_the_refusal`` is asserted to read differently: a level taken
    from the placement would have moved with them, and this one does not.
    """
    scenario = _close_owner(_store(MANAGER))
    logger_name = (
        f"{SenderClosureNotRecordedNode.__module__}"
        f".{SenderClosureNotRecordedNode.__name__}"
    )
    seen: dict[str, list[tuple[int, bool]]] = {}
    for label, rule in (
        ("lone-side", SenderRule.in_case(Kind.CASE_OWNER)),
        ("any-of-arm", SenderRule.in_case(Kind.CASE_OWNER, Kind.PARTICIPANT)),
    ):
        guard = compose_sender_guard(
            rule, SenderCheckContext(sender_id=OWNER, case_id=CASE_ID)
        )
        assert guard is not None
        closure = [
            node
            for node in guard.iterate()
            if isinstance(node, SenderClosureNotRecordedNode)
        ]
        assert len(closure) == 1, label
        assert failure_is_the_refusal(closure[0]) is (label == "lone-side")
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            result = scenario.run(
                guard, activity=SimpleNamespace(actor_id=OWNER)
            )
        assert result.status == Status.FAILURE, label
        seen[label] = [
            (record.levelno, "REFUSED" in record.getMessage())
            for record in caplog.records
            if record.name == logger_name
            and "already closed" in record.getMessage()
        ]
    assert seen == {
        "lone-side": [(logging.INFO, False)],
        "any-of-arm": [(logging.INFO, False)],
    }


# ---------------------------------------------------------------------------
# A lone CASE_OWNER side logs its refusal; an overruled arm does not (#5845)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006", "SL-03-002", "BT-13-001")
def test_a_lone_case_owner_side_logs_its_refusal_at_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``CASE_OWNER`` alone on the side is the guard's whole answer, so a
    sender that does not hold the role draws one WARNING, and it carries the
    reason ``BTBridge.get_failure_reason`` reports (BT-13-001).

    Until #5845 this side logged nothing above DEBUG: the node recorded the
    reason on ``feedback_message`` and never asked the placement rule, so a
    real refusal by a live lone-``CASE_OWNER`` side — the Add(Report),
    Add/Remove(CaseParticipant), Offer(CaseParticipantRole) and the two
    owner embargo decisions among them — was invisible to a reader and to
    ``expect_no_sender_refusals``.
    """
    guard = compose_sender_guard(
        SenderRule.in_case(Kind.CASE_OWNER),
        SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID),
    )
    assert guard is not None
    check = _owner_role_check(guard)
    assert isinstance(check, SenderIsCaseOwnerNode)
    assert failure_is_the_refusal(check) is True
    with caplog.at_level(logging.DEBUG):
        result = _store(MANAGER).run(
            guard, activity=SimpleNamespace(actor_id=VENDOR)
        )
    assert result.status == Status.FAILURE
    lines = _refusal_lines(caplog, SenderIsCaseOwnerNode)
    assert [record.levelno for record in lines] == [logging.WARNING]
    assert "is not the Case Owner" in lines[0].getMessage()
    assert "REFUSED (HP-01-006)" in lines[0].getMessage()
    assert (
        BTBridge.get_failure_reason(guard)
        == lines[0].getMessage().split(": ", 1)[1]
    )
    # The one line above DEBUG in the whole tick, so the refusal is neither
    # missing nor doubled by a second line stating the same thing.
    assert _refusals_logged(caplog) == [lines[0].getMessage()]


@pytest.mark.spec("HP-01-006", "HP-01-023", "SL-03-002", "SL-03-003")
def test_an_overruled_case_owner_arm_logs_debug_without_refusal_wording(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Inside an any-of side the ``CASE_OWNER`` arm refuses no one: the side's
    last arm names every standing it accepts, so the arm's own line is DEBUG
    and drops the ``REFUSED`` group (SL-03-002, SL-03-003)."""
    guard = compose_sender_guard(
        ANY_OF, SenderCheckContext(sender_id=VENDOR, case_id=CASE_ID)
    )
    assert guard is not None
    with caplog.at_level(logging.DEBUG):
        result = _store(MANAGER).run(
            guard, activity=SimpleNamespace(actor_id=VENDOR)
        )
    assert result.status == Status.FAILURE
    lines = _refusal_lines(caplog, SenderIsCaseOwnerNode)
    assert [record.levelno for record in lines] == [logging.DEBUG]
    assert "is not the Case Owner" in lines[0].getMessage()
    assert "REFUSED" not in lines[0].getMessage()
    refusals = _refusals_logged(caplog)
    assert len(refusals) == 1, refusals
    assert "none of the standings" in refusals[0]


# ---------------------------------------------------------------------------
# Where the CASE_OWNER check is read as a standing, not as a door (#5845)
# ---------------------------------------------------------------------------


def _owner_check_placements() -> dict[tuple[str, str, str], bool]:
    """Each tree-placed ``SenderIsCaseOwnerNode``, and the walk's answer.

    Read from the built trees, so a placement a helper or a nested factory
    makes is seen exactly as it runs, and keyed by (factory, parent, node
    name) rather than counted, so a moved or renamed placement names itself
    rather than being lost to a tally (#3984, #5535).  The Leave trigger tree
    is built beside the received corpus because it reuses the same close
    guards on the trigger side, where no received tree would reach them.

    Not *every* built placement: ``built_received_trees`` synthesizes each
    factory's ``sender_rule`` as ``SenderRule.in_case(CASE_MANAGER)``, so a
    ``CASE_OWNER`` door the factory would compose from a use case's declared
    rule is never built here — including all fourteen lone-``CASE_OWNER``
    sides.  Those are doors, and a door's FAILURE *is* the tree's refusal by
    design (``test_sender_guard_failure_is_the_tree_refusal.py`` pins that).
    What this census is for is the other kind: a placement a tree hard-codes
    to read the standing and pick a branch.
    """
    trees: dict[str, py_trees.behaviour.Behaviour] = {
        f"{module.rsplit('/', 1)[-1]}:{factory}": tree
        for (module, factory), tree in built_received_trees().items()
    }
    trees["leave_case_trigger_tree.py:create_leave_case_trigger_tree"] = (
        create_leave_case_trigger_tree(
            actor_id=OWNER,
            case_id=CASE_ID,
            activity_builder=lambda _case_id: [],
            result_out={},
        )
    )
    found: dict[tuple[str, str, str], bool] = {}
    for site, tree in trees.items():
        for node in tree.iterate():
            if not isinstance(node, SenderIsCaseOwnerNode):
                continue
            parent = node.parent
            assert parent is not None, f"{site}: {node.name} has no parent"
            found[site, parent.name, node.name] = failure_is_the_refusal(node)
    return found


#: The tree-placed ``SenderIsCaseOwnerNode`` reads whose FAILURE the walk
#: reads as the tree's whole answer, so the check logs it at WARNING.  Every
#: other placement is a standing read that picks an arm, and sits under a
#: Selector with a later sibling or under an ``Inverter``, so its branch
#: choice is DEBUG — which is why routing this node onto the shared rule
#: (#5845) did not have to give the standing reads a rule of their own.
#:
#: An entry here is a standing read logging ``REFUSED`` at WARNING for a
#: branch it merely did not take, so each one needs a ground.  One qualifies
#: today.  The closed-sender door's read was the other until #5917 placed it
#: ahead of the closure check it shares the door with; the door itself is
#: still the refusal, which is what
#: ``test_sender_guard_failure_is_the_tree_refusal.py`` pins.
_OWNER_CHECK_IS_THE_REFUSAL = {
    # The CM-23-011 decline arm, last child of ``CloseOrDecline``.  Its
    # FAILURE picks no branch that can rescue the delivery: the arm ticks
    # only once the close arm has already failed, so the tree refuses the
    # Leave whatever this check answers, and a WARNING states a real
    # outcome even though the standing it names is not the whole cause —
    # the reason the handler reports is the close arm's CM-23-010 one.
    # Moving it is a tree change, outside this check's package: #5903.
    (
        "factory.py:create_close_case_received_tree",
        "DeclineOwnerCloseIfEmbargoed",
        "CheckIsCaseOwnerForClose",
    ),
}


@pytest.mark.spec("SL-03-002", "RSH-01-002")
def test_every_case_owner_standing_read_is_placed_below_the_refusal() -> None:
    """A ``CASE_OWNER`` check ticked to pick an arm logs its non-match at DEBUG.

    The node is both a sender door and a standing read (RSH-01-002): the
    suggest-actor, Leave, status and embargo trees tick it to choose a
    branch.  Routing its non-match onto the shared refusal rule (#5845)
    gives each of those the level its own placement implies, so this records
    which placements the walk calls the tree's answer.  A new standing read
    that lands in one of those positions would log ``REFUSED`` at WARNING
    for a branch it merely did not take, and has to be decided here.
    """
    placements = _owner_check_placements()
    assert len(placements) > 1, (
        "no built tree places a CASE_OWNER check, so this proved nothing;"
        " the corpus or the node's placement has moved"
    )
    assert {
        site for site, is_refusal in placements.items() if is_refusal
    } == _OWNER_CHECK_IS_THE_REFUSAL
    assert {
        site for site, is_refusal in placements.items() if not is_refusal
    }, "every CASE_OWNER placement is a door, so no standing read is pinned"


# ---------------------------------------------------------------------------
# The closed-sender door's CASE_OWNER read refuses no one (#5917)
# ---------------------------------------------------------------------------


def _closed_sender_door() -> py_trees.behaviour.Behaviour:
    """The real door, under the root Sequence the factory places it in.

    The walk climbs to the root, so the door has to be a child of one for
    ``failure_is_the_refusal`` to answer what it answers in production
    (HP-01-025).
    """
    door = closed_sender_door(
        CASE_ID,
        ClosedSenderCheck(sender_id=VENDOR, case_owner_completes=True),
    )
    py_trees.composites.Sequence(
        name="CloseCaseBT", memory=True, children=[door]
    )
    return door


@pytest.mark.spec("SL-03-002", "SL-03-003", "CM-23-018", "ID-05-003")
def test_the_closed_sender_doors_owner_read_claims_no_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A closed non-owner's repeat draws no line claiming a sender refusal.

    The door's act closes the case, so the handler reports a closed
    sender's repeat ``SKIPPED``, never ``REFUSED`` (CM-23-049, ID-05-003) —
    ``case_owner_completes`` is set by the Leave tree alone, whose use case
    passes ``closes=True``.  Until #5917 the ``CASE_OWNER`` read was the
    Selector's **last** arm, so the walk called its FAILURE the tree's whole
    answer and it logged ``REFUSED (HP-01-006)`` at WARNING on exactly that
    run: a refusal line on a run that refused nothing, which is the line
    #5460 and #5786 removed.  Placed first, its FAILURE picks a branch the
    closure check can still admit, so the line is DEBUG with the refusal
    wording stripped, and the arm that speaks last is the one
    ``closed_sender_turned_away`` reports.
    """
    door = _closed_sender_door()
    read, closure = door.children
    assert isinstance(read, SenderIsCaseOwnerNode)
    assert isinstance(closure, SenderClosureNotRecordedNode)
    assert failure_is_the_refusal(door) is True
    assert failure_is_the_refusal(read) is False

    with caplog.at_level(logging.DEBUG):
        result = _close_participant(_store(MANAGER), VENDOR).run(
            door, activity=SimpleNamespace(actor_id=VENDOR)
        )

    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE
    # The door's own reason, the one the handler reports — not the read's.
    assert "already closed" in BTBridge.get_failure_reason(door)
    lines = _refusal_lines(caplog, SenderIsCaseOwnerNode)
    assert [record.levelno for record in lines] == [logging.DEBUG]
    assert "REFUSED" not in lines[0].getMessage()
    # Nothing a reader or ``expect_no_sender_refusals`` takes as a refusal.
    assert _refusals_logged(caplog) == []


@pytest.mark.spec("CM-23-002", "CM-23-018")
def test_the_closed_sender_door_still_admits_a_closing_case_owner() -> None:
    """Reading the standing first did not change what the door answers.

    The door is the same disjunction either way (CM-23-002): a Case Owner
    whose own closure the case records may still complete it, and the read
    now says so before the closure check is asked.
    """
    door = closed_sender_door(
        CASE_ID,
        ClosedSenderCheck(sender_id=OWNER, case_owner_completes=True),
    )
    py_trees.composites.Sequence(
        name="CloseCaseBT", memory=True, children=[door]
    )
    result = _close_participant(_store(MANAGER), OWNER).run(
        door, activity=SimpleNamespace(actor_id=OWNER)
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.SUCCESS


class _Leaf(py_trees.behaviour.Behaviour):
    """A bare leaf, to place in a shape and ask where its FAILURE lands."""

    def update(self) -> Status:
        return Status.FAILURE


@pytest.mark.spec("SL-03-002")
@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ("bare", True),
        ("selector-first", False),
        ("selector-last", True),
        ("sequence", True),
        ("inverted", False),
        ("nested-in-a-selector-arm", False),
    ],
)
def test_failure_is_the_refusal_reads_the_shape_above_the_node(
    shape: str, expected: bool
) -> None:
    """A Selector with a later sibling, or any decorator, means something above
    this node can still turn its FAILURE into an admission; a Sequence and the
    root pass it on (#5460)."""
    node = _Leaf(name="Check")
    if shape == "selector-first":
        py_trees.composites.Selector(
            name="S", memory=False, children=[node, _Leaf(name="Next")]
        )
    elif shape == "selector-last":
        py_trees.composites.Selector(
            name="S", memory=False, children=[_Leaf(name="Prev"), node]
        )
    elif shape == "sequence":
        py_trees.composites.Sequence(
            name="Q", memory=False, children=[node, _Leaf(name="Next")]
        )
    elif shape == "inverted":
        py_trees.decorators.Inverter(name="Not", child=node)
    elif shape == "nested-in-a-selector-arm":
        arm = py_trees.composites.Sequence(
            name="Arm", memory=False, children=[node]
        )
        py_trees.composites.Selector(
            name="S", memory=False, children=[arm, _Leaf(name="Next")]
        )
    assert failure_is_the_refusal(node) is expected
