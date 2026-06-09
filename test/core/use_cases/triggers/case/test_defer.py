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
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.triggers.case import (
    DeferCaseTriggerRequest,
    SvcDeferCaseUseCase,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def _make_actor(name: str) -> as_Service:
    return as_Service(name=name, url=f"https://example.org/{name.lower()}")


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
) -> tuple[VulnerabilityCase, CaseParticipant]:
    case = VulnerabilityCase(name="Test Case")

    actor_participant = CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    from vultron.wire.as2.vocab.objects.case_status import (
        ParticipantStatus as WireParticipantStatus,
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
    case_manager_participant = CaseParticipant(
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


class TestDeferCaseRMTransitionViaBT:
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

    def test_defer_case_updates_rm_to_deferred_via_bt(self):
        request = DeferCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        SvcDeferCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        updated = self.dl.read(self.vendor_participant.id_)
        assert updated is not None
        assert isinstance(updated, CaseParticipant)
        assert updated.participant_statuses
        assert updated.participant_statuses[-1].rm_state == RM.DEFERRED
