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

"""The sender rules of the last received use cases to declare one (#4522).

``Add(CaseStatus)``, ``Invite(Actor)`` and ``Leave(VulnerabilityCase)`` each
declare a sender rule that the receive-tree factory composes (HP-01-007,
HP-01-008).  ``Add(CaseStatus)`` is admitted only from the CASE_MANAGER, at a
participant replica (RSH-04-005, #4851).  For each:

- a sender with no standing is ``REFUSED`` with nothing committed, written or
  sent (HP-01-006);
- because the tree now has a sender guard, the CASE_MANAGER runs its embargo
  end-time check first, so an overdue embargo is ended by an entitled
  sender's activity (CLP-10-025, EMB-13-003), and never by an unentitled
  one's.

A repeated ``Leave`` from a sender the case already records as closed is
``SKIPPED`` with nothing committed or sent, whatever its activity id
(CM-23-018, ID-05-003).
"""

from datetime import datetime, timedelta
from typing import Any, cast

import pytest

from test.support.embargo_register import activate, write_consent_rows
from test.support.ledger import ledger_entries
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderExemption,
    SenderIsCaseOwnerNode,
    SenderRule,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    CaseParticipant,
    ReporterParticipant,
    VendorParticipant,
)
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.received.actor.invite import (
    InviteActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.core.use_cases.received.unknown import (
    UnknownUseCase,
    UnresolvableObjectUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
    rm_close_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _World:
    """One actor's store holding a case with an embargo in force.

    The store belongs to the CASE_MANAGER unless *store_owner* names the
    finder, whose store is a participant replica of the same case.  The
    embargo ends at *end_time*.  The deployer is a third participant,
    seated beside the finder, which no test but the Add(CaseStatus) ones
    needs.
    """

    def __init__(
        self, end_time: datetime | None = None, store_owner: str = "manager"
    ) -> None:
        self.manager = as_Service(name="Vendor Co")
        self.finder = as_Service(name="Finder Co")
        self.deployer = as_Service(name="Deployer Co")
        self.stranger = as_Service(name="Stranger Co")
        self.invitee = as_Service(name="Invitee Co")
        owner_id = (
            self.manager.id_ if store_owner == "manager" else self.finder.id_
        )
        self.receiver_id = owner_id
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        for actor in (
            self.manager,
            self.finder,
            self.deployer,
            self.stranger,
            self.invitee,
        ):
            self.dl.create(actor)
        case = VulnerabilityCase(
            name="Sender rule case", attributed_to=self.manager.id_
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
        deployer_p = CaseParticipant(
            attributed_to=self.deployer.id_,
            context=case.id_,
            case_roles=[CVDRole.DEPLOYER],
        )
        case.case_participants = [manager_p.id_, finder_p.id_, deployer_p.id_]
        case.actor_participant_index = {
            self.manager.id_: manager_p.id_,
            self.finder.id_: finder_p.id_,
            self.deployer.id_: deployer_p.id_,
        }
        activate(case, self.embargo.id_)
        self.case_id = case.id_
        self.finder_participant_id = finder_p.id_
        for obj in (case, self.embargo, manager_p, finder_p, deployer_p):
            self.dl.create(obj)
        write_consent_rows(self.dl, case)

    # -- reads ---------------------------------------------------------------

    def case(self) -> VulnerabilityCase:
        return cast(VulnerabilityCase, self.dl.read(self.case_id))

    def ledger_size(self) -> int:
        return len(ledger_entries(self.dl, self.case_id))

    def outbox(self) -> list[str]:
        return list(self.dl.outbox_list())

    def finder_closed(self) -> bool:
        record = self.dl.read(self.finder_participant_id)
        return isinstance(record, CaseParticipant) and record.rm_closed

    # -- received activities ---------------------------------------------------

    def _ports(self) -> dict[str, Any]:
        return {
            "trigger_activity": TriggerActivityAdapter(self.dl),
            "sync_port": SyncActivityAdapter(self.dl),
            "wire_render_port": As2WireRenderAdapter(),
        }

    def _event(self, activity: Any) -> Any:
        return received_event(activity).model_copy(
            update={"receiving_actor_id": self.receiver_id}
        )

    def case_status_from(
        self, sender_id: str, pxa: CS_pxa = CS_pxa.pxa
    ) -> HandlerResult:
        # The status carries the case's EM: a status never moves EM, so one
        # that differs is refused whole (RSH-09-005).
        status = as_CaseStatus(
            context=self.case_id,
            em=EmDimension(state=self.case().em_state),
            pxa=PxaDimension(state=pxa),
        )
        activity = add_status_to_case_activity(
            status,
            target=self.case_id,
            actor=sender_id,
            to=[self.receiver_id],
            context=self.case_id,
        )
        return AddCaseStatusToCaseReceivedUseCase(
            self.dl, self._event(activity), **self._ports()
        ).execute()

    def finder_status(self) -> HandlerResult:
        """The finder's own status, at the RM state it was seated with."""
        status = as_ParticipantStatus(
            context=self.case_id, attributed_to=self.finder.id_
        )
        activity = add_status_to_participant_activity(
            status,
            target=as_CaseParticipant(
                id_=self.finder_participant_id,
                context=self.case_id,
                attributed_to=self.finder.id_,
            ),
            actor=self.finder.id_,
            to=[self.receiver_id],
        )
        return AddParticipantStatusToParticipantReceivedUseCase(
            self.dl, self._event(activity), **self._ports()
        ).execute()

    def leave_from(self, sender_id: str, suffix: str = "1") -> HandlerResult:
        activity = rm_close_case_activity(
            as_VulnerabilityCase(id_=self.case_id),
            actor=sender_id,
            # Addressed to the manager and, at a replica, to the replica too.
            to=list(dict.fromkeys([self.manager.id_, self.receiver_id])),
            id_=f"{self.case_id}/leaves/{suffix}",
        )
        return CloseCaseReceivedUseCase(
            self.dl, self._event(activity), **self._ports()
        ).execute()

    def invite_from(self, sender_id: str) -> HandlerResult:
        """An Invite naming the receiver, or, at the CASE_MANAGER, which is
        never invited, a third actor (CM-17-006)."""
        invitee = (
            self.invitee.id_
            if self.receiver_id == self.manager.id_
            else self.receiver_id
        )
        activity = rm_invite_to_case_activity(
            as_Actor(id_=invitee),
            target=self.case_id,
            actor=sender_id,
            to=[invitee],
            id_=f"{self.case_id}/invitations/1",
        )
        return InviteActorToCaseReceivedUseCase(
            self.dl, self._event(activity), **self._ports()
        ).execute()


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
            AddCaseStatusToCaseReceivedUseCase,
            SenderRule(
                at_participant=frozenset({SenderEntitlementKind.CASE_MANAGER})
            ),
            id="add-case-status",
        ),
        pytest.param(
            CloseCaseReceivedUseCase,
            SenderRule.to_case_manager(
                SenderEntitlementKind.CASE_OWNER,
                SenderEntitlementKind.PARTICIPANT,
            ),
            id="leave",
        ),
        pytest.param(
            InviteActorToCaseReceivedUseCase,
            SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER),
            id="invite",
        ),
        pytest.param(
            CreateCaseReceivedUseCase,
            SenderRule(
                at_participant=frozenset({SenderEntitlementKind.NAMED_ACTOR}),
                outside_case=frozenset({SenderEntitlementKind.NAMED_ACTOR}),
            ),
            id="create-case",
        ),
    ],
)
def test_use_case_declares_its_sender_rule(
    use_case: type, rule: SenderRule
) -> None:
    assert use_case.sender_entitlement == rule  # type: ignore[attr-defined]


@pytest.mark.spec("HP-01-007")
@pytest.mark.parametrize(
    "use_case",
    [UnknownUseCase, UnresolvableObjectUseCase],
    ids=lambda c: c.__name__,
)
def test_use_case_with_nothing_to_gate_declares_no_sender_check(
    use_case: type,
) -> None:
    """No issue owns a check for them: the reason says why none applies."""
    declared = use_case.sender_entitlement  # type: ignore[attr-defined]
    assert isinstance(declared, SenderExemption)
    assert declared.permanent
    assert declared.reason.strip()


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("SYNC-16-003")
def test_the_fault_exemption_names_the_issue_that_gives_it_an_effect() -> None:
    """A fault changes nothing yet; the re-seed it will trigger brings the
    rule (#4799)."""
    declared = CreateProcessingFaultReceivedUseCase.sender_entitlement
    assert isinstance(declared, SenderExemption)
    assert declared.tracking_issue == "#4799"


# ---------------------------------------------------------------------------
# Add(CaseStatus)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CLP-10-025")
def test_case_status_from_a_stranger_is_refused_and_changes_nothing() -> None:
    """Refused before the end-time check: an overdue embargo stays, and no
    processing fault answers a sender with no standing."""
    world = _World(end_time=_overdue())
    statuses = list(world.case().case_statuses)
    before = world.ledger_size()

    result = world.case_status_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "No sender is entitled" in (result.reason or "")
    assert list(world.case().case_statuses) == statuses
    assert world.case().em_state is EM.ACTIVE
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("RSH-04-005")
@pytest.mark.spec("CLP-10-025")
def test_case_status_from_a_participant_to_the_manager_is_refused() -> None:
    """An active participant's public-awareness Add(CaseStatus) is refused at
    the CASE_MANAGER with nothing appended, committed, torn down or sent;
    even an overdue embargo stays, because no sender is entitled there."""
    world = _World(end_time=_overdue())
    statuses = list(world.case().case_statuses)
    before = world.ledger_size()

    result = world.case_status_from(world.finder.id_, pxa=CS_pxa.Pxa)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert list(world.case().case_statuses) == statuses
    assert world.case().em_state is EM.ACTIVE
    assert world.case().active_embargo_id == world.embargo.id_
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("RSH-04-005")
@pytest.mark.spec("RSH-04-001")
@pytest.mark.spec("PCR-03-001")
def test_case_status_from_a_participant_to_a_peer_is_refused() -> None:
    """At the finder's replica, the deployer's public-awareness
    Add(CaseStatus) is refused: a replica admits it from the CASE_MANAGER
    alone, so nothing is appended, committed, torn down or sent."""
    world = _World(store_owner="finder")
    statuses = list(world.case().case_statuses)
    before = world.ledger_size()

    result = world.case_status_from(world.deployer.id_, pxa=CS_pxa.Pxa)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert list(world.case().case_statuses) == statuses
    assert world.case().em_state is EM.ACTIVE
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("RSH-04-005")
def test_case_status_from_the_manager_is_admitted_at_a_replica() -> None:
    """The CASE_MANAGER's Add(CaseStatus) is admitted at a replica, which
    writes nothing on receipt (RSH-08-003) and asks nothing (RSH-03-004)."""
    world = _World(store_owner="finder")
    statuses = list(world.case().case_statuses)

    result = world.case_status_from(world.manager.id_, pxa=CS_pxa.Pxa)

    assert result.disposition is not HandlerDisposition.REFUSED, result.reason
    assert list(world.case().case_statuses) == statuses
    assert world.case().em_state is EM.ACTIVE
    assert world.outbox() == []


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("EMB-13-003")
def test_participant_status_from_a_participant_ends_an_overdue_embargo() -> (
    None
):
    """A participant reports through its own status, so that is the
    entitled activity whose receipt ends an overdue embargo."""
    world = _World(end_time=_overdue())

    world.finder_status()

    case = world.case()
    assert case.active_embargo_id is None
    assert case.em_state is EM.EXITED


# ---------------------------------------------------------------------------
# Leave(VulnerabilityCase)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CLP-10-025")
def test_leave_from_a_stranger_is_refused_and_changes_nothing() -> None:
    world = _World(end_time=_overdue())
    before = world.ledger_size()

    result = world.leave_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_OWNER, PARTICIPANT" in (result.reason or "")
    assert world.case().em_state is EM.ACTIVE
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("PCR-03-001")
def test_leave_at_a_replica_from_a_non_manager_is_refused() -> None:
    """A replica takes a closure from the CASE_MANAGER alone."""
    world = _World(store_owner="finder")
    before = world.ledger_size()

    result = world.leave_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert not world.finder_closed()
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("EMB-13-003")
def test_leave_from_a_participant_ends_an_overdue_embargo() -> None:
    world = _World(end_time=_overdue())

    result = world.leave_from(world.finder.id_)

    assert result.disposition is HandlerDisposition.APPLIED
    case = world.case()
    assert case.active_embargo_id is None
    assert case.em_state is EM.EXITED
    assert world.finder_closed()


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("ID-05-003")
def test_a_second_leave_with_a_new_id_is_skipped_and_records_nothing() -> None:
    """The closure is already in place, whatever the repeat's activity id."""
    world = _World()
    first = world.leave_from(world.finder.id_, suffix="first")
    assert first.disposition is HandlerDisposition.APPLIED
    assert world.finder_closed()
    ledger = world.ledger_size()
    outbox = world.outbox()

    again = world.leave_from(world.finder.id_, suffix="second")

    assert again.disposition is HandlerDisposition.SKIPPED
    assert "ID-05-003" in (again.reason or "")
    assert world.ledger_size() == ledger
    assert world.outbox() == outbox


# ---------------------------------------------------------------------------
# Invite(Actor)
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("CLP-10-025")
def test_invite_at_the_case_manager_from_a_stranger_is_refused() -> None:
    world = _World(end_time=_overdue())
    before = world.ledger_size()

    result = world.invite_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert world.case().em_state is EM.ACTIVE
    assert world.ledger_size() == before
    assert world.outbox() == []


@pytest.mark.spec("HP-01-006")
@pytest.mark.spec("PCR-03-001")
def test_invite_at_a_replica_from_a_peer_records_no_trust_anchor() -> None:
    """A receiver that knows the case's CASE_MANAGER refuses anyone else."""
    world = _World(store_owner="finder")

    result = world.invite_from(world.stranger.id_)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert (
        world.dl.read(VultronPendingCaseInbox.build_id(world.case_id)) is None
    )
    assert world.outbox() == []


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("EMB-13-003")
def test_invite_echoed_to_the_case_manager_ends_an_overdue_embargo() -> None:
    """The CASE_MANAGER is entitled to its own Invite, so the tree runs its
    end-time check."""
    world = _World(end_time=_overdue())

    world.invite_from(world.manager.id_)

    assert world.case().em_state is EM.EXITED


@pytest.mark.spec("ARCH-15-001")
def test_an_internal_error_asking_for_the_case_owner_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The closed-sender door's Case Owner check for a repeated Leave never
    reads a crash as "not the owner", which would report the Leave SKIPPED."""
    world = _World()
    assert world.leave_from(world.finder.id_, suffix="first").disposition is (
        HandlerDisposition.APPLIED
    )

    def _crash(self: SenderIsCaseOwnerNode) -> Any:
        raise RuntimeError("owner lookup crashed")

    monkeypatch.setattr(SenderIsCaseOwnerNode, "update", _crash)

    with pytest.raises(VultronBTInternalError):
        world.leave_from(world.finder.id_, suffix="second")
