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

"""The full sender rules that moved out of their trees (#4437 piece 3, AC-4).

Each declaration below used to be a floor, with the real rule in a
tree-local guard.  The rule is now the declaration, and the receive-tree
factory composes the guard from it (HP-01-008).  For every declaration and
each addressee side, an entitled sender is admitted and an unentitled one is
refused.
"""

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.core.behaviors.report.prioritize_tree import (
    create_engage_case_tree,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_invalidate_report_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    AuthoredNote,
    SenderCheckContext,
    compose_sender_guard,
    embargo_sender_context,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.use_cases.received.actor.suggest import (
    OfferActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case.engage_defer import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.announce import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.invite import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.remove import (
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report import (
    InvalidateReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/widened-rules"
NOTE_ID = f"{CASE_ID}/notes/n1"
MANAGER = "https://example.org/actors/case-manager"
OWNER = "https://example.org/actors/owner"
VENDOR = "https://example.org/actors/vendor"
REPLICA = "https://example.org/actors/replica"
INERT = "https://example.org/actors/inert-invitee"
STRANGER = "https://example.org/actors/stranger"

Kind = SenderEntitlementKind
ContextFor = Callable[[str], SenderCheckContext]


def _plain(sender: str) -> SenderCheckContext:
    return SenderCheckContext(sender_id=sender, case_id=CASE_ID)


def _note(sender: str) -> SenderCheckContext:
    return SenderCheckContext(
        sender_id=sender,
        case_id=CASE_ID,
        authored_object=AuthoredNote(note_id=NOTE_ID),
    )


def _embargo(sender: str) -> SenderCheckContext:
    return embargo_sender_context(sender, CASE_ID)


def _store(receiver: str) -> BTTestScenario:
    """*receiver*'s store: the case, its roster, and VENDOR's note.

    VENDOR and REPLICA are active participants; INERT holds a stub Invite it
    has not answered, so the case lists it but it is not active (CM-10-004).
    """
    scenario = BTTestScenario(actor_id=receiver)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Widened rules case")
    seed_case_manager_participant(scenario.dl, case, MANAGER)
    seed_case_owner_participant(scenario.dl, case, OWNER)
    seed_case_participant(scenario.dl, case, VENDOR, [CVDRole.VENDOR])
    seed_case_participant(scenario.dl, case, REPLICA)
    seed_case_participant(scenario.dl, case, INERT, [CVDRole.VENDOR])
    scenario.dl.create(case)
    inert = scenario.dl.read(case.actor_participant_index[INERT])
    assert isinstance(inert, CaseParticipant)
    inert.joined = False
    scenario.dl.save(inert)
    scenario.dl.create(as_Note(id_=NOTE_ID, content="n", attributed_to=VENDOR))
    return scenario


def _store_without_manager(receiver: str) -> BTTestScenario:
    """*receiver*'s store holding a case that names no CASE_MANAGER yet."""
    scenario = BTTestScenario(actor_id=receiver)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Unmanaged case")
    seed_case_owner_participant(scenario.dl, case, OWNER)
    seed_case_participant(scenario.dl, case, VENDOR, [CVDRole.VENDOR])
    seed_case_participant(scenario.dl, case, REPLICA)
    scenario.dl.create(case)
    scenario.dl.create(as_Note(id_=NOTE_ID, content="n", attributed_to=VENDOR))
    return scenario


def _admits(
    rule: SenderRule,
    context: ContextFor,
    receiver: str,
    sender: str,
    store: Callable[[str], BTTestScenario] = _store,
) -> bool:
    guard = compose_sender_guard(rule, context(sender))
    assert guard is not None
    result = store(receiver).run(
        guard, activity=SimpleNamespace(actor_id=sender)
    )
    assert not result.internal_error, result.feedback_message
    return result.status == Status.SUCCESS


def _cases(
    rule: SenderRule,
    context: ContextFor,
    *,
    at_manager: tuple[str, str],
    at_participant: tuple[str, str],
    marks: tuple[str, ...],
    label: str,
) -> list[object]:
    """One param per (side, entitled-or-not) for a declaration."""
    spec_marks = [pytest.mark.spec(spec_id) for spec_id in marks]
    entitled_cm, unentitled_cm = at_manager
    entitled_p, unentitled_p = at_participant
    return [
        pytest.param(
            rule,
            context,
            receiver,
            sender,
            admitted,
            id=f"{label}-{side}-{'entitled' if admitted else 'unentitled'}",
            marks=spec_marks,
        )
        for side, receiver, sender, admitted in (
            ("at-manager", MANAGER, entitled_cm, True),
            ("at-manager", MANAGER, unentitled_cm, False),
            ("at-participant", REPLICA, entitled_p, True),
            ("at-participant", REPLICA, unentitled_p, False),
        )
    ]


_PARTICIPANT_MOVE = ("HP-01-008", "PCR-03-001", "CM-31-004", "CM-31-011")

CASES = [
    # The note's author or the Case Owner at the CASE_MANAGER, which a
    # participant alone takes the removal from (CM-30-001, PCR-03-001).
    *_cases(
        RemoveNoteFromCaseReceivedUseCase.sender_entitlement,
        _note,
        at_manager=(VENDOR, REPLICA),
        at_participant=(MANAGER, VENDOR),
        marks=("HP-01-008", "CM-30-001", "PCR-03-001"),
        label="remove-note-author",
    ),
    *_cases(
        RemoveNoteFromCaseReceivedUseCase.sender_entitlement,
        _note,
        at_manager=(OWNER, STRANGER),
        at_participant=(MANAGER, OWNER),
        marks=("HP-01-008", "CM-30-001", "PCR-03-001"),
        label="remove-note-owner",
    ),
    *_cases(
        AddCaseParticipantToCaseReceivedUseCase.sender_entitlement,
        _plain,
        at_manager=(OWNER, VENDOR),
        at_participant=(MANAGER, OWNER),
        marks=_PARTICIPANT_MOVE,
        label="add-participant",
    ),
    *_cases(
        RemoveCaseParticipantFromCaseReceivedUseCase.sender_entitlement,
        _plain,
        at_manager=(OWNER, VENDOR),
        at_participant=(MANAGER, OWNER),
        marks=_PARTICIPANT_MOVE,
        label="remove-participant",
    ),
    *_cases(
        AddReportToCaseReceivedUseCase.sender_entitlement,
        _plain,
        at_manager=(OWNER, VENDOR),
        at_participant=(MANAGER, OWNER),
        marks=("HP-01-008", "CM-30-002", "PCR-03-001"),
        label="add-report",
    ),
    # An active participant proposes to the CASE_MANAGER, which relays the
    # Invite; a participant takes the Invite from the CASE_MANAGER alone.
    *_cases(
        InviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        _embargo,
        at_manager=(VENDOR, INERT),
        at_participant=(MANAGER, VENDOR),
        marks=("HP-01-008", "EP-09-003", "CM-10-004", "PCR-08-001"),
        label="embargo-invite",
    ),
    *_cases(
        InviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        _embargo,
        at_manager=(MANAGER, STRANGER),
        at_participant=(MANAGER, OWNER),
        marks=("HP-01-008", "EP-09-003", "PCR-08-001"),
        label="embargo-invite-relay",
    ),
    # The Case Owner decides the embargo; the CASE_MANAGER acts on its own
    # Remove too, and a participant takes the change from it alone.
    *_cases(
        RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement,
        _embargo,
        at_manager=(OWNER, VENDOR),
        at_participant=(MANAGER, OWNER),
        marks=("HP-01-008", "EP-09-005", "PCR-03-001"),
        label="embargo-remove",
    ),
    *_cases(
        RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement,
        _embargo,
        at_manager=(MANAGER, STRANGER),
        at_participant=(MANAGER, VENDOR),
        marks=("HP-01-008", "EP-09-005", "PCR-03-001"),
        label="embargo-remove-delegated",
    ),
    *_cases(
        AnnounceEmbargoEventToCaseReceivedUseCase.sender_entitlement,
        _embargo,
        at_manager=(MANAGER, OWNER),
        at_participant=(MANAGER, OWNER),
        marks=("HP-01-008", "EP-09-003", "PCR-03-001"),
        label="embargo-announce",
    ),
    # Any participant record on the case, on both sides, as the trees
    # checked (PARTICIPANT).
    *_cases(
        OfferActorToCaseReceivedUseCase.sender_entitlement,
        _plain,
        at_manager=(VENDOR, STRANGER),
        at_participant=(VENDOR, STRANGER),
        marks=("HP-01-008", "CM-16-001"),
        label="offer-actor",
    ),
    *_cases(
        AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement,
        _plain,
        at_manager=(VENDOR, STRANGER),
        at_participant=(VENDOR, STRANGER),
        marks=("HP-01-008", "CM-10-004"),
        label="add-participant-status",
    ),
]


@pytest.mark.parametrize(
    ("rule", "context", "receiver", "sender", "admitted"), CASES
)
def test_declared_rule_admits_exactly_its_side(
    rule: SenderRule,
    context: ContextFor,
    receiver: str,
    sender: str,
    admitted: bool,
) -> None:
    assert _admits(rule, context, receiver, sender) is admitted


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("HP-01-009")
@pytest.mark.parametrize(
    ("kind", "sender", "admitted"),
    [
        (Kind.PARTICIPANT, VENDOR, True),
        (Kind.PARTICIPANT, INERT, True),
        (Kind.ACTIVE_PARTICIPANT, VENDOR, True),
        (Kind.ACTIVE_PARTICIPANT, INERT, False),
    ],
    ids=["listed-active", "listed-inert", "active-active", "active-inert"],
)
def test_an_inert_participant_holds_participant_but_not_active_participant(
    kind: SenderEntitlementKind, sender: str, admitted: bool
) -> None:
    """Any record on the case is ``PARTICIPANT``; only an active one is
    ``ACTIVE_PARTICIPANT`` (CM-10-004)."""
    assert _admits(SenderRule.in_case(kind), _plain, MANAGER, sender) is (
        admitted
    )


#: Declarations relabelled from ``ACTIVE_PARTICIPANT`` to ``PARTICIPANT``
#: (#4437): each tree admitted any participant the case lists, and still does.
RELABELLED = {
    "validate-report": ValidateReportReceivedUseCase,
    "invalidate-report": InvalidateReportReceivedUseCase,
    "engage-case": EngageCaseReceivedUseCase,
    "defer-case": DeferCaseReceivedUseCase,
    "offer-actor": OfferActorToCaseReceivedUseCase,
    "add-participant-status": AddParticipantStatusToParticipantReceivedUseCase,
}


@pytest.mark.spec("HP-01-008")
@pytest.mark.spec("HP-01-009")
@pytest.mark.parametrize("receiver", [MANAGER, REPLICA], ids=["cm", "replica"])
@pytest.mark.parametrize(
    ("sender", "admitted"),
    [(INERT, True), (VENDOR, True), (STRANGER, False)],
    ids=["inert", "active", "stranger"],
)
@pytest.mark.parametrize(
    "use_case", RELABELLED.values(), ids=RELABELLED.keys()
)
def test_relabelled_declaration_admits_any_listed_participant(
    use_case: type, receiver: str, sender: str, admitted: bool
) -> None:
    """Relabelling to ``PARTICIPANT`` changed no admission: an inert invitee
    the case lists is still admitted, and an unlisted actor still refused."""
    rule = use_case.sender_entitlement  # type: ignore[attr-defined]
    assert rule == SenderRule.in_case(Kind.PARTICIPANT)
    assert _admits(rule, _plain, receiver, sender) is admitted


def _relabelled_trees() -> dict[str, tuple[type, Callable[[], object]]]:
    """The relabelled use cases whose tree once placed its own sender guard
    and now takes it from the factory (#4696)."""
    request = SimpleNamespace(
        actor_id=VENDOR,
        report_id="https://example.org/reports/r",
        activity_id="https://example.org/activities/a",
    )
    return {
        "engage-case": (
            EngageCaseReceivedUseCase,
            lambda: create_engage_case_tree(
                case_id=CASE_ID,
                actor_id=VENDOR,
                sender_rule=EngageCaseReceivedUseCase.sender_entitlement,
            ),
        ),
        "invalidate-report": (
            InvalidateReportReceivedUseCase,
            lambda: create_invalidate_report_received_tree(
                request,  # type: ignore[arg-type]
                CASE_ID,
                sender_rule=InvalidateReportReceivedUseCase.sender_entitlement,
            ),
        ),
    }


@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize("label", list(_relabelled_trees()))
def test_relabelled_tree_guard_checks_the_declared_kind(label: str) -> None:
    """The guard the factory composes for the tree checks the kind its use
    case declares, so the declaration and the tree cannot drift apart."""
    use_case, build = _relabelled_trees()[label]
    rule = use_case.sender_entitlement  # type: ignore[attr-defined]
    tree = build()
    kinds = {
        node.guards_kind
        for node in tree.iterate()  # type: ignore[attr-defined]
        if getattr(node, "guards_kind", None) is not None
    }
    assert kinds == {Kind.PARTICIPANT}
    assert kinds <= rule.at_case_manager and kinds <= rule.at_participant


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize(
    "rule",
    [
        InviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement,
        AnnounceEmbargoEventToCaseReceivedUseCase.sender_entitlement,
    ],
    ids=["invite", "remove", "announce"],
)
def test_embargo_rule_refuses_the_case_manager_where_the_case_is_unheld(
    rule: SenderRule,
) -> None:
    """With no case to check standing against, an embargo sender is refused.

    The pass-through a CASE_MANAGER check allows during the bootstrap window
    does not apply to embargo state (Regime 1, ADR-0087).
    """
    guard = compose_sender_guard(rule, _embargo(MANAGER))
    assert guard is not None
    result = BTTestScenario(actor_id=REPLICA).run(
        guard, activity=SimpleNamespace(actor_id=MANAGER)
    )
    assert result.status == Status.FAILURE


def test_to_case_manager_states_the_case_manager_at_a_participant() -> None:
    rule = SenderRule.to_case_manager(Kind.AUTHOR, Kind.CASE_OWNER)
    assert rule.at_case_manager == {Kind.AUTHOR, Kind.CASE_OWNER}
    assert rule.at_participant == {Kind.CASE_MANAGER}
    assert rule.outside_case == frozenset()


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize(
    ("sender", "admitted"),
    [(MANAGER, True), (OWNER, False)],
    ids=["case-manager", "case-owner"],
)
def test_receiver_side_is_the_exact_case_manager_id(
    sender: str, admitted: bool
) -> None:
    """The receiver's side is read by exact id, as the effect gates read it.

    A receiver whose id differs from the CASE_MANAGER's only by a trailing
    slash is a participant here, so only the CASE_MANAGER is admitted.  The
    trees' CASE_MANAGER-gated effects compare the same way, so an owner
    admitted at that receiver would have reached no effect either.
    """
    rule = RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement
    assert _admits(rule, _embargo, f"{MANAGER}/", sender) is admitted


_EMBARGO_RULES = [
    pytest.param(
        InviteToEmbargoOnCaseReceivedUseCase.sender_entitlement, id="invite"
    ),
    pytest.param(
        RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement,
        id="remove",
    ),
    pytest.param(
        AnnounceEmbargoEventToCaseReceivedUseCase.sender_entitlement,
        id="announce",
    ),
]


@pytest.mark.spec("PCR-03-001")
@pytest.mark.parametrize("rule", _EMBARGO_RULES)
@pytest.mark.parametrize("sender", [MANAGER, OWNER], ids=["manager", "owner"])
def test_embargo_rule_refuses_every_sender_where_the_case_names_no_manager(
    rule: SenderRule, sender: str
) -> None:
    """A case with no CASE_MANAGER leaves no standing to check (ADR-0087)."""
    assert not _admits(
        rule, _embargo, REPLICA, sender, store=_store_without_manager
    )


_BOOTSTRAP_RULES = [
    pytest.param(
        RemoveNoteFromCaseReceivedUseCase.sender_entitlement,
        _note,
        id="remove-note",
    ),
    pytest.param(
        AddCaseParticipantToCaseReceivedUseCase.sender_entitlement,
        _plain,
        id="add-participant",
    ),
    pytest.param(
        RemoveCaseParticipantFromCaseReceivedUseCase.sender_entitlement,
        _plain,
        id="remove-participant",
    ),
    pytest.param(
        AddReportToCaseReceivedUseCase.sender_entitlement,
        _plain,
        id="add-report",
    ),
]


@pytest.mark.spec("SYNC-15-001")
@pytest.mark.parametrize(("rule", "context"), _BOOTSTRAP_RULES)
def test_case_content_rule_passes_through_before_the_case_names_a_manager(
    rule: SenderRule, context: ContextFor
) -> None:
    """With no CASE_MANAGER known yet the guard defers to the bootstrap path.

    The CASE_MANAGER check passes through during the bootstrap window, as
    the retired role-scoped guard did, so the tree's later guards decide.
    """
    assert _admits(
        rule, context, REPLICA, STRANGER, store=_store_without_manager
    )


@pytest.mark.spec("HP-01-008")
def test_participant_status_with_no_case_is_refused() -> None:
    """The status rule states no side outside a case, so no sender passes."""
    rule = AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement
    guard = compose_sender_guard(
        rule, SenderCheckContext(sender_id=VENDOR, case_id=None)
    )
    assert guard is not None
    result = _store(MANAGER).run(
        guard, activity=SimpleNamespace(actor_id=VENDOR)
    )
    assert not result.internal_error, result.feedback_message
    assert result.status == Status.FAILURE
