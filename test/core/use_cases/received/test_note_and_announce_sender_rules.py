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

"""The sender rules of the note and ``Announce(VulnerabilityCase)`` use cases.

``Add(Note)`` goes from an active participant to the CASE_MANAGER, and a
replica takes it from the CASE_MANAGER alone (CM-23-018, PCR-03-001):

- a sender with no standing, or one whose closure the case records, is
  ``REFUSED`` with nothing committed, attached or sent (HP-01-006,
  CM-23-018);
- because the tree has a sender guard, the CASE_MANAGER runs its embargo
  end-time check first, so an overdue embargo is ended by an entitled
  sender's note and never by an unentitled one's (CLP-10-025, EMB-13-003).

``Announce(VulnerabilityCase)`` goes from the CASE_MANAGER to a participant
replica, which admits it only from the CASE_MANAGER it has trusted for the
case: the one its bootstrap recorded on a completed ``ReportCaseLink``, which
ordinary traffic never replaces (CBT-01-006, CBT-02-003), else the one its
replica names, else the one its stub Invite recorded (PCR-03-001,
PCR-03-004).
"""

from datetime import datetime, timedelta
from typing import Any, cast

import pytest

from test.support.embargo_register import (
    activate,
    agree_to_active_embargo,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    ClockDecision,
    ClockDecisionStage,
)
from vultron.core.behaviors.note.add_note_received_tree import (
    create_add_note_to_case_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderIsCaseManagerNode,
    SenderRule,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    CaseParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import AddNoteToCaseReceivedUseCase
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_REPORT_ID = "https://example.org/reports/report-4785"


class _World:
    """One actor's store holding a case with an embargo in force.

    The store belongs to the CASE_MANAGER unless *store_owner* names the
    finder, whose store is a participant replica of the same case.  The
    finder is an active participant (a signatory to the embargo), unless
    *finder_closed* records its closure.  The embargo ends at *end_time*.
    """

    def __init__(
        self,
        end_time: datetime | None = None,
        store_owner: str = "manager",
        finder_closed: bool = False,
    ) -> None:
        self.manager = as_Service(name="Vendor Co")
        self.finder = as_Service(name="Finder Co")
        self.stranger = as_Service(name="Stranger Co")
        owner_id = (
            self.manager.id_ if store_owner == "manager" else self.finder.id_
        )
        self.receiver_id = owner_id
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        for actor in (self.manager, self.finder, self.stranger):
            self.dl.create(actor)
        case = VulnerabilityCase(
            name="Note sender rule case", attributed_to=self.manager.id_
        )
        self.embargo = as_EmbargoEvent(
            context=case.id_,
            end_time=end_time or now_utc() + timedelta(days=30),
        )
        manager_p = VendorParticipant(
            attributed_to=self.manager.id_, context=case.id_
        )
        manager_p.add_role(CVDRole.CASE_MANAGER)
        finder_p = ReporterParticipant(
            attributed_to=self.finder.id_, context=case.id_
        )
        if finder_closed:
            finder_p = finder_p.model_copy(
                update={
                    "participant_statuses": [
                        *finder_p.participant_statuses,
                        ParticipantStatus(
                            context=case.id_,
                            attributed_to=self.finder.id_,
                            rm=RmDimension(state=RM.CLOSED),
                            cvd_role=[CVDRole.REPORTER],
                        ),
                    ]
                }
            )
        case.case_participants = [manager_p.id_, finder_p.id_]
        case.actor_participant_index = {
            self.manager.id_: manager_p.id_,
            self.finder.id_: finder_p.id_,
        }
        activate(case, self.embargo.id_)
        self.case_id = case.id_
        self.finder_participant_id = finder_p.id_
        for obj in (case, self.embargo, manager_p, finder_p):
            self.dl.create(obj)
        write_consent_rows(self.dl, case)
        # The finder is a signatory, so it is an active participant
        # (CM-10-004); the closed one stays closed (CM-23-018).
        agree_to_active_embargo(
            self.dl, self.case(), self.manager.id_, self.finder.id_
        )

    # -- reads ---------------------------------------------------------------

    def case(self) -> VulnerabilityCase:
        return cast(VulnerabilityCase, self.dl.read(self.case_id))

    def ledger_size(self) -> int:
        return len(ledger_entries(self.dl, self.case_id))

    def outbox(self) -> list[str]:
        return list(self.dl.outbox_list())

    def notes(self) -> list[str]:
        return [str(n) for n in self.case().notes]

    # -- received activities ---------------------------------------------------

    def _ports(self) -> dict[str, Any]:
        return {
            "trigger_activity": TriggerActivityAdapter(self.dl),
            "sync_port": SyncActivityAdapter(self.dl),
            "wire_render_port": As2WireRenderAdapter(),
        }

    def _event(self, activity: Any) -> Any:
        return extract_event(activity).model_copy(
            update={"receiving_actor_id": self.receiver_id}
        )

    def add_note_from(self, sender_id: str) -> tuple[HandlerResult, str]:
        note = as_Note(content="A note", context=self.case_id)
        # Addressed to this store, so the addressee door guard admits it
        # and the sender guard is what decides (HP-01-005).
        activity = add_note_to_case_activity(
            note,
            target=as_VulnerabilityCase(id_=self.case_id),
            actor=sender_id,
            to=[self.receiver_id],
        )
        result = AddNoteToCaseReceivedUseCase(
            self.dl, self._event(activity), **self._ports()
        ).execute()
        return result, note.id_


def _overdue() -> datetime:
    return now_utc() - timedelta(minutes=5)


# ---------------------------------------------------------------------------
# The declarations (HP-01-007, HP-01-008)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize(
    ("use_case", "rule"),
    [
        pytest.param(
            AddNoteToCaseReceivedUseCase,
            SenderRule.to_case_manager(
                SenderEntitlementKind.ACTIVE_PARTICIPANT
            ),
            id="add-note",
        ),
        pytest.param(
            AnnounceVulnerabilityCaseReceivedUseCase,
            SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER),
            id="announce-case",
        ),
    ],
)
def test_use_case_declares_its_sender_rule(
    use_case: type, rule: SenderRule
) -> None:
    assert use_case.sender_entitlement == rule  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Add(Note)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CLP-10-025")
def test_note_from_a_stranger_is_refused_and_changes_nothing() -> None:
    """Refused before the end-time check: an overdue embargo stays, and
    nothing is stored, attached, committed or sent."""
    world = _World(end_time=_overdue())
    before = world.ledger_size()

    result, note_id = world.add_note_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "is not an active participant" in (result.reason or "")
    assert note_id not in world.notes()
    assert world.case().em_state is EM.ACTIVE
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("HP-01-006")
def test_note_from_a_closed_sender_is_refused_and_changes_nothing() -> None:
    """A participant whose closure the case records may act on nothing
    further; the shared predicate refuses it (CM-23-018)."""
    world = _World(finder_closed=True)
    before = world.ledger_size()

    result, note_id = world.add_note_from(world.finder.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "has left it" in (result.reason or "")
    assert note_id not in world.notes()
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("PCR-03-001")
def test_note_at_a_replica_from_a_non_manager_is_refused() -> None:
    """A replica takes case content from the CASE_MANAGER alone."""
    world = _World(store_owner="finder")

    result, note_id = world.add_note_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert note_id not in world.notes()
    assert world.outbox() == []


@pytest.mark.spec("PCR-03-001")
@pytest.mark.spec("CLP-10-017")
def test_add_note_at_a_replica_from_a_non_manager_stores_no_note() -> None:
    """The refused sender's inline note is not kept (CLP-10-017)."""
    world = _World(store_owner="finder")

    _, note_id = world.add_note_from(world.stranger.id_)

    assert world.dl.read(note_id) is None


@pytest.mark.spec("PCR-03-001")
@pytest.mark.spec("HP-01-005")
def test_add_note_at_a_replica_from_the_manager_passes_the_sender_guard() -> (
    None
):
    """The CASE_MANAGER's ``Add(Note)`` passes a replica's sender guard; the
    replica is not the CASE_MANAGER, so it attaches nothing and reports the
    missing role, never a sender refusal (HP-01-005)."""
    world = _World(store_owner="finder")
    before = world.ledger_size()

    result, note_id = world.add_note_from(world.manager.id_)

    reason = result.reason or ""
    assert result.disposition is HandlerDisposition.REFUSED
    assert reason.startswith("not the CASE_MANAGER of case")
    assert "HP-01-006" not in reason
    assert note_id not in world.notes()
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("CM-23-018")
def test_note_from_an_active_participant_is_attached() -> None:
    world = _World()

    result, note_id = world.add_note_from(world.finder.id_)

    assert result.disposition is HandlerDisposition.APPLIED
    assert note_id in world.notes()


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("EMB-13-003")
def test_note_from_a_participant_ends_an_overdue_embargo() -> None:
    world = _World(end_time=_overdue())

    world.add_note_from(world.finder.id_)

    case = world.case()
    assert case.active_embargo_id is None
    assert case.em_state is EM.EXITED


# ---------------------------------------------------------------------------
# Announce(VulnerabilityCase)
# ---------------------------------------------------------------------------


class _Replica:
    """A participant's store after the bootstrap ``Create(VulnerabilityCase)``.

    The bootstrap seeded the replica from the CASE_MANAGER's snapshot and
    recorded that CASE_MANAGER's address on the completed ``ReportCaseLink``
    (CBT-01-006).  With *roster_manager*, the replica's roster has since come
    to name that actor as CASE_MANAGER instead, while the link still names
    the one the bootstrap trusted.  Without *roster_names_manager*, the
    roster names no CASE_MANAGER at all, so only the link names one.
    """

    def __init__(
        self,
        roster_manager: str | None = None,
        roster_names_manager: bool = True,
    ) -> None:
        self.manager_id = "https://example.org/actors/case-actor"
        self.receiver_id = "https://example.org/actors/finder"
        self.dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.receiver_id
        )
        case = VulnerabilityCase(
            name="Bootstrapped case", attributed_to=self.manager_id
        )
        holder = roster_manager or self.manager_id
        manager_p = (
            CaseParticipant(
                attributed_to=holder,
                context=case.id_,
                case_roles=[CVDRole.CASE_MANAGER],
            )
            if roster_names_manager
            else CaseParticipant(
                attributed_to=self.receiver_id,
                context=case.id_,
                case_roles=[CVDRole.REPORTER],
            )
        )
        case.add_participant(manager_p)
        self.case_id = case.id_
        self.dl.create(manager_p)
        self.dl.create(case)
        self.dl.save(
            VultronReportCaseLink(
                report_id=_REPORT_ID,
                case_id=case.id_,
                case_creator_id=self.manager_id,
                case_manager_id=self.manager_id,
            )
        )

    def case_name(self) -> str | None:
        return cast(VulnerabilityCase, self.dl.read(self.case_id)).name

    def announce_from(self, sender_id: str) -> HandlerResult:
        snapshot = as_VulnerabilityCase(
            id_=self.case_id,
            name="Announced snapshot",
            attributed_to=self.manager_id,
        )
        activity = announce_vulnerability_case_activity(
            snapshot,
            actor=sender_id,
            to=[self.receiver_id],
            context=self.case_id,
        )
        event = cast(
            AnnounceVulnerabilityCaseReceivedEvent,
            extract_event(activity).model_copy(
                update={"receiving_actor_id": self.receiver_id}
            ),
        )
        return AnnounceVulnerabilityCaseReceivedUseCase(
            self.dl, event
        ).execute()


@pytest.mark.spec("PCR-03-001")
@pytest.mark.spec("CBT-01-006")
def test_announce_from_the_report_case_link_address_is_admitted() -> None:
    """The address the completed ``ReportCaseLink`` records is trusted on its
    own: the roster names no CASE_MANAGER and no stub Invite recorded an
    anchor, so the link is the only source that admits the Announce."""
    replica = _Replica(roster_names_manager=False)
    link = replica.dl.read(VultronReportCaseLink.build_id(_REPORT_ID))
    assert isinstance(link, VultronReportCaseLink)
    assert link.case_manager_id == replica.manager_id

    result = replica.announce_from(replica.manager_id)

    assert result.disposition is HandlerDisposition.APPLIED
    assert replica.case_name() == "Announced snapshot"


@pytest.mark.spec("CBT-02-003")
@pytest.mark.spec("PCR-03-004")
def test_the_bootstrap_trusted_manager_is_not_replaced_by_the_roster() -> None:
    """The link records the CASE_MANAGER the bootstrap trusted, which
    ordinary traffic never replaces: an Announce from an actor the roster
    has come to name is refused with nothing seeded, and the trusted one's is
    applied (CBT-02-003)."""
    other = "https://example.org/actors/other-manager"
    replica = _Replica(roster_manager=other)

    refused = replica.announce_from(other)

    assert refused.disposition is HandlerDisposition.REFUSED
    assert "is not the CASE_MANAGER" in (refused.reason or "")
    assert replica.case_name() == "Bootstrapped case"

    admitted = replica.announce_from(replica.manager_id)

    assert admitted.disposition is HandlerDisposition.APPLIED
    assert replica.case_name() == "Announced snapshot"


@pytest.mark.spec("PCR-03-004")
def test_announce_from_a_stranger_to_a_bootstrapped_replica_is_refused() -> (
    None
):
    replica = _Replica()

    result = replica.announce_from("https://example.org/actors/stranger")

    assert result.disposition is HandlerDisposition.REFUSED
    assert replica.case_name() == "Bootstrapped case"


@pytest.mark.spec("CLP-10-025")
def test_announce_tree_takes_no_clock_decision() -> None:
    """Only a participant replica receives the Announce, and a replica takes
    no clock decision: the tree names no case for the CASE_MANAGER gate."""
    case = as_VulnerabilityCase(name="No clock")
    event = cast(
        AnnounceVulnerabilityCaseReceivedEvent,
        extract_event(
            announce_vulnerability_case_activity(
                case,
                actor="https://example.org/actors/case-actor",
                context=case.id_,
            )
        ),
    )

    tree = create_announce_vulnerability_case_received_tree(
        case_obj=case,
        request=event,
        sender_rule=AnnounceVulnerabilityCaseReceivedUseCase.sender_entitlement,
    )

    assert not any(
        isinstance(node, (ClockDecisionStage, ClockDecision))
        for node in tree.iterate()
    )
    assert any(
        isinstance(node, SenderIsCaseManagerNode) for node in tree.iterate()
    )

    # The probe finds the stage where the factory composes one: a note tree.
    world = _World()
    note = VultronNote(content="A note", context=world.case_id)
    note_tree = create_add_note_to_case_received_tree(
        note_obj=note,
        case_id=world.case_id,
        sender_id=world.finder.id_,
        activity_id="https://example.org/activities/add-note",
        sender_rule=AddNoteToCaseReceivedUseCase.sender_entitlement,
    )
    assert any(
        isinstance(node, ClockDecisionStage) for node in note_tree.iterate()
    )
