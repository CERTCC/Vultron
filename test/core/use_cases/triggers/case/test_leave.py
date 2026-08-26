#!/usr/bin/env python

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.case import (
    LeaveCaseTriggerRequest,
    SvcLeaveCaseUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    FinderParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _make_actor(name: str) -> as_Service:
    return as_Service(
        name=name, url=f"https://example.org/{name.lower().replace(' ', '-')}"
    )


def _make_actor_dl(name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = _make_actor(name)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_case_with_case_manager(
    dl: SqliteDataLayer,
    actor_id: str,
    finder_id: str,
    case_actor_id: str,
) -> tuple[as_VulnerabilityCase, as_CaseParticipant]:
    case = as_VulnerabilityCase(name="Test Case")

    actor_participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.RECEIVED)
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.VALID)
    )

    finder_participant = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )

    case.actor_participant_index[actor_id] = actor_participant.id_
    case.actor_participant_index[finder_id] = finder_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_

    case.case_participants.append(actor_participant.id_)
    case.case_participants.append(finder_participant.id_)
    case.case_participants.append(case_manager_participant.id_)

    dl.create(case)
    dl.create(actor_participant)
    dl.create(finder_participant)
    dl.create(case_manager_participant)
    return case, actor_participant


class TestLeaveCaseTriggersOutboxActivity:
    """AC-1: execute() queues a Leave(VulnerabilityCase) activity in the outbox.

    Covers: outbox effect (PCR-08-001 routing), and failure modes.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case_actor, _ = _make_actor_dl("Case Actor")
        self.case, self.vendor_participant = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    def test_leave_case_queues_activity_in_outbox(self):
        request = LeaveCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        before = set(self.dl.outbox_list())
        SvcLeaveCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()
        after = set(self.dl.outbox_list())
        assert len(after - before) >= 1

    def test_leave_case_outbox_activity_addressed_to_case_actor(self):
        """Activity is routed exclusively to the Case Actor (PCR-08-001)."""
        request = LeaveCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        before = set(self.dl.outbox_list())
        SvcLeaveCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()
        after = set(self.dl.outbox_list())
        new_ids = after - before
        assert new_ids, "No new outbox item was queued"

        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to = getattr(activity, "to", None)
        to_ids = (
            [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
            if isinstance(to, list)
            else ([to] if isinstance(to, str) else [])
        )
        assert self.case_actor.id_ in to_ids
        assert self.vendor.id_ not in to_ids
        assert self.finder.id_ not in to_ids
        assert len(to_ids) == 1, f"Expected exactly 1 recipient, got {to_ids}"

    def test_leave_case_actor_not_found_raises_error(self):
        request = LeaveCaseTriggerRequest(
            actor_id="urn:uuid:no-such-actor",
            case_id=self.case.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcLeaveCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_leave_case_not_found_raises_error(self):
        request = LeaveCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id="urn:uuid:no-such-case",
        )
        with pytest.raises(VultronNotFoundError):
            SvcLeaveCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_leave_case_no_case_manager_raises_validation_error(self):
        """VultronValidationError raised when case has no CASE_MANAGER."""
        case_solo = as_VulnerabilityCase(name="Solo Case")
        vendor_participant = as_CaseParticipant(
            attributed_to=self.vendor.id_,
            context=case_solo.id_,
            case_roles=[CVDRole.VENDOR],
        )
        vendor_participant.participant_statuses.append(
            WireParticipantStatus(context=case_solo.id_, rm_state=RM.RECEIVED)
        )
        vendor_participant.participant_statuses.append(
            WireParticipantStatus(context=case_solo.id_, rm_state=RM.VALID)
        )
        case_solo.actor_participant_index[self.vendor.id_] = (
            vendor_participant.id_
        )
        case_solo.case_participants.append(vendor_participant.id_)
        self.dl.create(case_solo)
        self.dl.create(vendor_participant)

        request = LeaveCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=case_solo.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcLeaveCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()
