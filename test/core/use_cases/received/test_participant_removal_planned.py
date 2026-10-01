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
"""Planned participant removal and reinstatement (ADR-0115, CM-30).

Strict-``xfail`` goal tests planned under #2257; each test names the issue
that implements it.  Every test starts from a CASE_MANAGER store holding a
case with the CASE_MANAGER, a Case Owner, a joined vendor that is
``SIGNATORY`` to the active embargo, and a second joined vendor.

- CM-30-001 — removal keeps the record and makes the participant inert.
- CM-30-003 — the case publishes a computed ``activeParticipants``.
- CM-30-004 — only the Case Owner may remove, and never the manager or owner.
- CM-30-005 — one ledger entry, under a canonical signature.
- CM-30-006 — a direct notice to the removed participant.
- CM-30-007 — replicas apply the removal from its ledger entry.
- CM-30-008 — removal leaves embargo consent untouched.
- CM-30-009 — a removed signatory is told when the embargo is terminated.
- CM-30-010 — a paused replica ignores an embargo-ending notice from a
  non-manager.
- CM-30-011 — ``Add(CaseParticipant)`` reinstates, and only reinstates.
- CM-30-012 — no ``Add(CaseParticipant)`` after a stub-Invite acceptance.
- CM-30-013 — a removed participant is not sent an embargo Invite.

Activities are routed the way the inbox routes them (``route_received``), so
a test keeps working when the implementation adds new semantics.  See
``notes/case-joining.md`` § "Removal and reinstatement".
"""

from dataclasses import dataclass
from typing import Any, cast

import py_trees
import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.actor.test_case_joining_planned import (
    route_received,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import _as_id, days_from_now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    remove_embargo_from_case_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Service,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/case-removal-1"
MANAGER = "https://example.org/actors/case-actor-removal"
OWNER = "https://example.org/actors/owner-removal"
VENDOR = "https://example.org/actors/vendor-removal"
OTHER = "https://example.org/actors/other-removal"
EMBARGO_ID = f"{CASE_ID}/embargo_events/active"

_REMOVAL = "ADR-0115 participant removal (CM-30). Tracked by #2257."


@dataclass
class _RemovalCase:
    """A CASE_MANAGER store holding the case and its four participants."""

    dl: SqliteDataLayer
    case: as_VulnerabilityCase

    def read_case(self) -> as_VulnerabilityCase:
        case = self.dl.read(CASE_ID)
        assert isinstance(case, as_VulnerabilityCase)
        return case

    def participant(self, actor_id: str) -> CaseParticipant:
        participant = self.dl.read(_participant_id(actor_id))
        assert isinstance(participant, CaseParticipant)
        return participant

    def route(self, activity: Any) -> HandlerResult:
        return route_received(self.dl, activity, receiving_actor_id=MANAGER)

    def remove(self, actor_id: str, *, by: str = OWNER) -> HandlerResult:
        return self.route(
            remove_participant_from_case_activity(
                self.participant(actor_id), target=CASE_ID, actor=by
            )
        )

    def ledger(self) -> list[CaseLedgerEntry]:
        return [
            entry
            for entry in self.dl.list_objects("CaseLedgerEntry")
            if isinstance(entry, CaseLedgerEntry) and entry.case_id == CASE_ID
        ]

    def activities_to(self, type_: str, actor_id: str) -> list[Any]:
        """Activities of *type_* the manager authored and addressed to *actor_id*."""
        return [
            obj
            for obj in self.dl.list_objects(type_)
            if _as_id(getattr(obj, "actor", None)) == MANAGER
            and actor_id in [_as_id(t) for t in getattr(obj, "to", None) or []]
        ]


def _participant_id(actor_id: str) -> str:
    return f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}"


def _record(
    actor_id: str, roles: list[CVDRole], pec: PEC = PEC.SIGNATORY
) -> CaseParticipant:
    return CaseParticipant(
        id_=_participant_id(actor_id),
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=roles,
        embargo_consent_state=pec,
        accepted_embargo_ids=[EMBARGO_ID] if pec is PEC.SIGNATORY else [],
    )


def _seed(dl: SqliteDataLayer) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="CASE-REMOVAL", attributed_to=OWNER
    )
    dl.create(as_Service(id_=MANAGER, context=CASE_ID))
    for actor_id in (OWNER, VENDOR, OTHER):
        dl.create(as_Organization(id_=actor_id))
    seed_case_manager_participant(dl, case, MANAGER)
    for actor_id, roles in (
        (OWNER, [CVDRole.CASE_OWNER, CVDRole.VENDOR]),
        (VENDOR, [CVDRole.VENDOR]),
        (OTHER, [CVDRole.VENDOR]),
    ):
        record = _record(actor_id, roles)
        dl.create(record)
        case.case_participants.append(record.id_)
        case.actor_participant_index[actor_id] = record.id_
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
    )
    dl.create(embargo)
    case.append_case_status(em_state=EM.ACTIVE)
    case.active_embargo = EMBARGO_ID
    dl.create(case)
    return case


@pytest.fixture
def removal_case() -> _RemovalCase:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    return _RemovalCase(dl=dl, case=_seed(dl))


@pytest.mark.xfail(strict=True, reason=f"CM-30-001: {_REMOVAL}")
@pytest.mark.spec("CM-30-001")
def test_removal_keeps_the_record_on_the_roster(removal_case) -> None:
    """Removal withdraws entitlement; the record, and its index entry, stay."""
    result = removal_case.remove(VENDOR)

    assert result.disposition is HandlerDisposition.APPLIED
    case = removal_case.read_case()
    assert _participant_id(VENDOR) in [
        getattr(p, "id_", p) for p in case.case_participants
    ]
    assert case.actor_participant_index.get(VENDOR) == _participant_id(VENDOR)


@pytest.mark.xfail(strict=True, reason=f"CM-30-003: {_REMOVAL}")
@pytest.mark.spec("CM-30-003")
def test_case_publishes_active_participants_and_round_trips(
    removal_case,
) -> None:
    """``activeParticipants`` is computed, published, and read back cleanly."""
    removal_case.remove(VENDOR)
    case = removal_case.read_case()

    dumped = case.model_dump(by_alias=True, mode="json")
    assert "activeParticipants" in dumped
    active = {getattr(p, "id_", p) for p in dumped["activeParticipants"]}
    assert _participant_id(VENDOR) not in active
    assert _participant_id(OTHER) in active
    assert as_VulnerabilityCase.model_validate(dumped) == case


@pytest.mark.xfail(strict=True, reason=f"CM-30-004: {_REMOVAL}")
@pytest.mark.spec("CM-30-004")
@pytest.mark.parametrize(
    ("sender", "removed"),
    [
        pytest.param(OTHER, VENDOR, id="non-owner-sender"),
        pytest.param(OWNER, MANAGER, id="removes-the-case-manager"),
        pytest.param(OWNER, OWNER, id="removes-the-case-owner"),
    ],
)
def test_removal_is_refused_unless_the_owner_removes_a_removable_participant(
    removal_case, sender: str, removed: str
) -> None:
    """Only the Case Owner may remove, and never the manager or the owner."""
    removed_record = (
        removal_case.dl.read(f"{CASE_ID}/participants/case-manager")
        if removed == MANAGER
        else removal_case.participant(removed)
    )
    assert isinstance(removed_record, CaseParticipant)

    result = removal_case.route(
        remove_participant_from_case_activity(
            removed_record, target=CASE_ID, actor=sender
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED


@pytest.mark.xfail(strict=True, reason=f"CM-30-004: {_REMOVAL}")
@pytest.mark.spec("CM-30-004")
def test_a_second_removal_is_skipped(removal_case) -> None:
    """Removing an already-removed participant is a no-op, reported as such."""
    assert removal_case.remove(VENDOR).disposition is (
        HandlerDisposition.APPLIED
    )
    # Today the first removal deletes the record, so the second is skipped
    # for the wrong reason; removal must keep it (CM-30-001).
    assert VENDOR in removal_case.read_case().actor_participant_index
    second = removal_case.remove(VENDOR)

    assert second.disposition is HandlerDisposition.SKIPPED


@pytest.mark.xfail(strict=True, reason=f"CM-30-005: {_REMOVAL}")
@pytest.mark.spec("CM-30-005")
def test_removal_is_one_canonical_ledger_entry_by_the_owner(
    removal_case,
) -> None:
    """The owner's received ``Remove`` is the single entry for the move."""
    from vultron.core.behaviors.sync.nodes.canonical_entry import (
        _CANONICAL_PAYLOAD_SIGNATURES,
    )

    assert ("Remove", "CaseParticipant") in _CANONICAL_PAYLOAD_SIGNATURES
    before = len(removal_case.ledger())

    removal_case.remove(VENDOR)

    added = removal_case.ledger()[before:]
    assert len(added) == 1, [e.event_type for e in added]
    assert added[0].payload_snapshot.get("actor") == OWNER


@pytest.mark.xfail(strict=True, reason=f"CM-30-006: {_REMOVAL}")
@pytest.mark.spec("CM-30-006")
def test_removed_participant_is_sent_a_direct_remove_naming_it(
    removal_case,
) -> None:
    """The manager tells the removed party, crediting the Case Owner."""
    removal_case.remove(VENDOR)

    notices = removal_case.activities_to("Remove", VENDOR)
    assert len(notices) == 1
    assert getattr(notices[0], "attributed_to", None) == OWNER


@pytest.mark.xfail(strict=True, reason=f"CM-30-007: {_REMOVAL}")
@pytest.mark.spec("CM-30-007")
def test_announce_tree_has_a_removal_replay_node() -> None:
    """A replica applies removal from the ledger entry, not the direct notice.

    Structural goal: the replay slot's node names carry ``Remove`` and
    ``Participant`` (for example ``IsRemoveCaseParticipantEventNode``); the
    implementation may rename it and update this test.
    """
    from vultron.core.behaviors.sync.announce_tree import (
        create_announce_log_entry_tree,
    )

    names = [
        type(node).__name__
        for node in create_announce_log_entry_tree().iterate()
    ]
    assert any("Remove" in n and "Participant" in n for n in names), names


@pytest.mark.xfail(strict=True, reason=f"CM-30-008: {_REMOVAL}")
@pytest.mark.spec("CM-30-008")
def test_removal_leaves_embargo_consent_untouched(removal_case) -> None:
    """A removed signatory stays bound by the embargo it accepted."""
    removal_case.remove(VENDOR)

    case = removal_case.read_case()
    assert VENDOR in case.actor_participant_index
    participant = removal_case.participant(VENDOR)
    assert participant.embargo_consent_state == PEC.SIGNATORY
    assert participant.accepted_embargo_ids == [EMBARGO_ID]


@pytest.mark.xfail(strict=True, reason=f"CM-30-009: {_REMOVAL}")
@pytest.mark.spec("CM-30-009")
def test_removed_signatory_is_sent_the_termination(removal_case) -> None:
    """Terminating the embargo sends the removed signatory a direct ET."""
    removal_case.remove(VENDOR)
    assert VENDOR in removal_case.read_case().actor_participant_index
    embargo = removal_case.dl.read(EMBARGO_ID)
    assert isinstance(embargo, as_EmbargoEvent)

    removal_case.route(
        remove_embargo_from_case_activity(embargo, origin=CASE_ID, actor=OWNER)
    )

    assert removal_case.activities_to("Remove", VENDOR), (
        "no Remove(EmbargoEvent) reached the removed signatory"
    )


@pytest.mark.xfail(strict=True, reason=f"CM-30-010: {_REMOVAL}")
@pytest.mark.spec("CM-30-010")
def test_paused_replica_ignores_an_ending_notice_from_a_non_manager() -> None:
    """Only the CASE_MANAGER's notice moves a paused replica's embargo."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    _seed(dl)
    embargo = dl.read(EMBARGO_ID)
    assert isinstance(embargo, as_EmbargoEvent)

    route_received(
        dl,
        remove_embargo_from_case_activity(
            embargo, origin=CASE_ID, actor=OTHER
        ),
        receiving_actor_id=VENDOR,
    )

    case = dl.read(CASE_ID)
    assert isinstance(case, as_VulnerabilityCase)
    assert case.active_embargo is not None


@pytest.mark.xfail(strict=True, reason=f"CM-30-011: {_REMOVAL}")
@pytest.mark.spec("CM-30-011")
def test_owner_add_reinstates_a_removed_participant(removal_case) -> None:
    """``Add(CaseParticipant)`` from the owner reverses a removal."""
    removal_case.remove(VENDOR)
    participant = removal_case.participant(VENDOR)

    result = removal_case.route(
        add_participant_to_case_activity(
            participant, target=CASE_ID, actor=OWNER
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED
    dumped = removal_case.read_case().model_dump(by_alias=True, mode="json")
    active = {getattr(p, "id_", p) for p in dumped["activeParticipants"]}
    assert _participant_id(VENDOR) in active


@pytest.mark.xfail(strict=True, reason=f"CM-30-011: {_REMOVAL}")
@pytest.mark.spec("CM-30-011")
def test_add_naming_a_participant_that_is_not_removed_is_refused(
    removal_case,
) -> None:
    """``Add`` only reinstates; it is not a way to seat a member."""
    result = removal_case.route(
        add_participant_to_case_activity(
            removal_case.participant(OTHER), target=CASE_ID, actor=OWNER
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED


@pytest.mark.xfail(strict=True, reason=f"CM-30-012: {_REMOVAL}")
@pytest.mark.spec("CM-30-012")
def test_accept_invite_tree_emits_no_add_case_participant() -> None:
    """Replicas learn of a new member from the ``Accept(Invite)`` entry."""
    from vultron.core.behaviors.case.accept_invite_tree import (
        create_accept_invite_actor_to_case_tree,
    )

    names = [
        type(node).__name__
        for node in create_accept_invite_actor_to_case_tree(
            case_id=CASE_ID, invitee_id=VENDOR
        ).iterate()
    ]
    assert "EmitAddCaseParticipantNode" not in names


@pytest.mark.xfail(strict=True, reason=f"CM-30-013: {_REMOVAL}")
@pytest.mark.spec("CM-30-013")
def test_removed_participant_is_not_invited_to_an_embargo_revision() -> None:
    """The embargo-Invite recipients exclude a removed participant."""
    from vultron.core.behaviors.embargo.nodes.relay import (
        CollectEmbargoInviteRecipientsNode,
    )

    scenario = BTTestScenario(MANAGER)
    removal = _RemovalCase(dl=scenario.dl, case=_seed(scenario.dl))
    removal.remove(VENDOR)
    assert VENDOR in removal.read_case().actor_participant_index

    scenario.run(
        CollectEmbargoInviteRecipientsNode(case_id=CASE_ID, proposer_id=OWNER)
    )

    recipients = cast(
        list[str],
        py_trees.blackboard.Blackboard.storage["/embargo_invite_recipients"],
    )
    assert OTHER in recipients
    assert VENDOR not in recipients
