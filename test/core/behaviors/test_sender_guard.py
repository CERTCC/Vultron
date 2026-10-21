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
from test.support.received import with_evidence
from vultron.core.behaviors import sender_entitlement
from vultron.core.behaviors.bridge import BTBridge
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
)
from vultron.core.behaviors.sender_guard import (
    AddresseeRequest,
    AuthoredCaseProposal,
    AuthoredNote,
    CaseProposalRequest,
    LedgerActivityContext,
    OwnershipOfferRequest,
    ReportOfferRequest,
    SenderCheckContext,
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
    case = as_VulnerabilityCase(id_=CASE_ID, name="Sender rule case")
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
    """The proposal as the Accept or Reject path stores it, with no record:
    a store written before the admission record existed."""
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


@pytest.mark.spec("CM-23-018")
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


@pytest.mark.spec("CM-23-018", "CM-10-004")
@_MAY_NOT_ACT
@_VENDOR_GUARDS
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


@pytest.mark.spec("HP-01-007")
def test_factory_takes_no_sender_guard_built_by_a_tree() -> None:
    """The guard comes from the declared rule alone (HP-01-008, #4437)."""
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

    # intake, post-close, addressee door, sender guard
    assert len(tree.children) == 4


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


def _close_owner(scenario: BTTestScenario) -> BTTestScenario:
    """Record the Case Owner's closure (RM ``CLOSED``) on the open case."""
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    record = scenario.dl.read(case.actor_participant_index[OWNER])
    assert isinstance(record, CaseParticipant)
    record.participant_statuses.append(
        ParticipantStatus(
            context=CASE_ID,
            attributed_to=OWNER,
            rm=RmDimension(state=RM.CLOSED),
        )
    )
    scenario.dl.save(record)
    return scenario


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
        as_VulnerabilityCase(id_=CASE_ID, name="snapshot"), CASE_ID
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
    ("sender", "guards", "refused"),
    [
        (STRANGER, [], True),
        (VENDOR, [], False),
        (VENDOR, [_Refuse(name="Refuse")], False),
    ],
    ids=["unentitled-sender", "entitled-sender", "a-later-guard-refuses"],
)
def test_sender_guard_refused_names_only_the_sender_guards_refusal(
    sender: str, guards: list[py_trees.behaviour.Behaviour], refused: bool
) -> None:
    tree = _participant_tree(sender, guards)
    event = with_evidence(
        EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-guard",
            actor_id=sender,
            object_=as_VulnerabilityCase(id_=CASE_ID, name="Sender rule case"),
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
    assert result.status == Status.FAILURE
    assert sender_guard_refused(tree) is refused
