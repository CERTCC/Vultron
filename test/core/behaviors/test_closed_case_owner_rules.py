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

"""Every ``CASE_OWNER`` use case refuses a closed Case Owner (CM-23-018).

A Case Owner can reach RM ``CLOSED`` while its case stays open (a status
update declaring it, an owner ``Leave`` whose later commit fails, a ``Reject``
of the full-case Invite after an ownership transfer).  It has then left and
may act on nothing further, so the guard the factory composes for the
``CASE_OWNER`` kind refuses it, for each use case that declares the kind
(#4746).  Each use case's own declared rule is composed with the context its
handler builds, at the CASE_MANAGER.
"""

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.test_widened_sender_rules import (
    CASE_ID,
    MANAGER,
    OWNER,
    _admits,
    _embargo,
    _note,
    _plain,
    _store,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    OwnershipOfferRequest,
    SenderCheckContext,
    compose_sender_guard,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.case_participant_role import (
    OfferCaseParticipantRoleReceivedUseCase,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.core.use_cases.received.actor.ownership import (
    ProposeCaseOwnershipTransferReceivedUseCase,
    UndoCaseOwnershipTransferReceivedUseCase,
)
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
    CloseCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

OFFER_ID = f"{CASE_ID}/activities/ownership-offer"
UNDO_ID = f"{CASE_ID}/activities/ownership-undo"

ContextFor = Callable[[str], SenderCheckContext]


def _new_ownership_proposal(sender: str) -> SenderCheckContext:
    return SenderCheckContext(
        sender_id=sender,
        case_id=CASE_ID,
        ownership_proposal_id=OFFER_ID,
        case_manager_required=True,
    )


def _ownership_withdrawal(sender: str) -> SenderCheckContext:
    return SenderCheckContext(
        sender_id=sender,
        case_id=CASE_ID,
        request=OwnershipOfferRequest(offer_id=OFFER_ID, reply_id=UNDO_ID),
        case_manager_required=True,
    )


#: Each ``CASE_OWNER`` use case, the context its handler checks the sender
#: in, and whether an open owner passes that context with no other record
#: (a withdrawal also needs the Offer it withdraws, so it does not).
CASE_OWNER_USE_CASES: dict[str, tuple[type, ContextFor, bool]] = {
    "accept-offer-case-participant": (
        AcceptOfferCaseParticipantReceivedUseCase,
        _plain,
        True,
    ),
    "reject-offer-case-participant": (
        RejectOfferCaseParticipantReceivedUseCase,
        _plain,
        True,
    ),
    "offer-participant-role": (
        OfferCaseParticipantRoleReceivedUseCase,
        _plain,
        True,
    ),
    "remove-note": (RemoveNoteFromCaseReceivedUseCase, _note, True),
    "propose-ownership": (
        ProposeCaseOwnershipTransferReceivedUseCase,
        _new_ownership_proposal,
        True,
    ),
    "undo-ownership": (
        UndoCaseOwnershipTransferReceivedUseCase,
        _ownership_withdrawal,
        False,
    ),
    "add-participant": (
        AddCaseParticipantToCaseReceivedUseCase,
        _plain,
        True,
    ),
    "remove-participant": (
        RemoveCaseParticipantFromCaseReceivedUseCase,
        _plain,
        True,
    ),
    "add-report": (AddReportToCaseReceivedUseCase, _plain, True),
    "activate-embargo": (ActivateEmbargoOnCaseReceivedUseCase, _embargo, True),
    "reject-embargo-proposal": (
        RejectEmbargoProposalOnCaseReceivedUseCase,
        _embargo,
        True,
    ),
    "remove-embargo": (
        RemoveEmbargoEventFromCaseReceivedUseCase,
        _embargo,
        True,
    ),
}


#: The one ``CASE_OWNER`` use case a closed owner still passes the sender
#: guard for: its ``Leave`` repeat finishes the case's closure (CM-23-002,
#: CM-23-018), and the tree's closed-sender door guard decides the repeat.
CLOSING_CASE_OWNER_USE_CASES: frozenset[type] = frozenset(
    {CloseCaseReceivedUseCase}
)


def _closing_owner(sender: str) -> SenderCheckContext:
    return SenderCheckContext(
        sender_id=sender, case_id=CASE_ID, closing_case_owner=True
    )


def _closed_owner_store(receiver: str) -> BTTestScenario:
    """*receiver*'s store, with the Case Owner at RM ``CLOSED`` on the case."""
    scenario = _store(receiver)
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


def _rule(use_case: type) -> SenderRule:
    rule = use_case.sender_entitlement  # type: ignore[attr-defined]
    assert isinstance(rule, SenderRule)
    return rule


def test_the_list_names_every_case_owner_use_case() -> None:
    """A new ``CASE_OWNER`` use case joins the list, so it is tested here."""
    declaring = {
        entry.use_case_class
        for entry in SEMANTIC_REGISTRY
        if isinstance(
            rule := getattr(entry.use_case_class, "sender_entitlement", None),
            SenderRule,
        )
        and SenderEntitlementKind.CASE_OWNER in rule.at_case_manager
    }
    assert declaring == {
        uc for uc, _, _ in CASE_OWNER_USE_CASES.values()
    } | set(CLOSING_CASE_OWNER_USE_CASES)


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("CM-23-002")
def test_a_closed_case_owner_still_passes_the_leave_guard() -> None:
    """Its repeated Leave finishes the case's closure; the close-case
    tree's closed-sender door guard, not the sender guard, decides it."""
    guard = compose_sender_guard(
        _rule(CloseCaseReceivedUseCase), _closing_owner(OWNER)
    )
    assert guard is not None

    result = _closed_owner_store(MANAGER).run(
        guard, activity=SimpleNamespace(actor_id=OWNER)
    )

    assert not result.internal_error, result.feedback_message
    assert result.status == Status.SUCCESS


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize("label", list(CASE_OWNER_USE_CASES))
def test_a_closed_case_owner_is_refused_at_the_case_manager(
    label: str,
) -> None:
    use_case, context, _ = CASE_OWNER_USE_CASES[label]
    guard = compose_sender_guard(_rule(use_case), context(OWNER))
    assert guard is not None

    result = _closed_owner_store(MANAGER).run(
        guard, activity=SimpleNamespace(actor_id=OWNER)
    )

    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE
    reason = BTBridge.get_failure_reason(guard)
    assert "already closed" in reason or "none of the standings" in reason


@pytest.mark.spec("CM-23-018")
@pytest.mark.parametrize(
    "label",
    [
        label
        for label, (_, _, open_ok) in CASE_OWNER_USE_CASES.items()
        if open_ok
    ],
)
def test_an_open_case_owner_is_still_admitted(label: str) -> None:
    use_case, context, _ = CASE_OWNER_USE_CASES[label]
    assert _admits(_rule(use_case), context, MANAGER, OWNER)
