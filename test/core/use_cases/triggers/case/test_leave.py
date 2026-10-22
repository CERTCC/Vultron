#!/usr/bin/env python

from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import (
    activate,
    propose,
    terminate,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.call_out.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
    CloseReportCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.case import (
    LeaveCaseTriggerRequest,
    SvcLeaveCaseUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    ReporterParticipant,
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
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


def _stored_embargo(
    dl: SqliteDataLayer, case: as_VulnerabilityCase, suffix: str
) -> as_EmbargoEvent:
    """Persist an embargo for *case*, so a Leave carrying the case can send."""
    embargo = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/{suffix}",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    dl.create(embargo)
    return embargo


def _make_case_with_case_manager(
    dl: SqliteDataLayer,
    actor_id: str,
    finder_id: str,
    case_actor_id: str,
    roles: tuple[CVDRole, ...] = (CVDRole.VENDOR,),
    em_state: EM = EM.NONE,
) -> tuple[as_VulnerabilityCase, as_CaseParticipant]:
    case = as_VulnerabilityCase(attributed_to=CASE_OWNER_ID, name="Test Case")
    if em_state in (EM.ACTIVE, EM.REVISE):
        activate(case, _stored_embargo(dl, case, "e1"))
    if em_state == EM.REVISE:
        propose(case, _stored_embargo(dl, case, "e2"))

    actor_participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=list(roles),
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(
            context=case.id_, rm=RmDimension(state=RM.RECEIVED)
        )
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm=RmDimension(state=RM.VALID))
    )

    finder_participant = ReporterParticipant(
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
    write_consent_rows(dl, case)
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
        case_solo = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, name="Solo Case"
        )
        vendor_participant = as_CaseParticipant(
            attributed_to=self.vendor.id_,
            context=case_solo.id_,
            case_roles=[CVDRole.VENDOR],
        )
        vendor_participant.participant_statuses.append(
            WireParticipantStatus(
                context=case_solo.id_, rm=RmDimension(state=RM.RECEIVED)
            )
        )
        vendor_participant.participant_statuses.append(
            WireParticipantStatus(
                context=case_solo.id_, rm=RmDimension(state=RM.VALID)
            )
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


# ---------------------------------------------------------------------------
# leave-case: any participant, pre-close call-out, owner embargo guard
# (TRIG-13-001, TRIG-13-002, TRIG-13-003, ADR-0145)
# ---------------------------------------------------------------------------

_OWNER = (CVDRole.CASE_OWNER, CVDRole.VENDOR)
_NON_OWNER = (CVDRole.VENDOR,)


class _PreCloseRecorder:
    """A ``PreCloseAction`` backend that records each run and the outbox then.

    ``outbox_at_run`` holds the outbox contents at the moment the call-out
    ticked, so a test can assert the Leave was not queued before it ran.
    """

    def __init__(self, dl: SqliteDataLayer, status: Status = Status.SUCCESS):
        self.dl = dl
        self.status = status
        self.outbox_at_run: list[set[str]] = []

    def factory(self, name: str) -> py_trees.behaviour.Behaviour:
        recorder = self

        class _Recording(py_trees.behaviour.Behaviour):
            def update(self) -> Status:
                recorder.outbox_at_run.append(set(recorder.dl.outbox_list()))
                return recorder.status

        return _Recording(name)

    def bundle(self) -> CloseReportCallOutBundle:
        return CloseReportCallOutBundle(
            pre_close_action_factory=self.factory  # type: ignore[arg-type]
        )


def _recipients(activity) -> list[str]:
    to = getattr(activity, "to", None) or []
    items = to if isinstance(to, list) else [to]
    return [i if isinstance(i, str) else i.id_ for i in items]


class TestLeaveCaseTrigger:
    """``leave-case`` sends the Leave for any participant, after its pre-close
    step, and refuses the Case Owner under a live embargo (ADR-0145)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.actor, self.dl = _make_actor_dl("Leaving Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case_actor, _ = _make_actor_dl("Case Actor")
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    def _case(
        self, roles: tuple[CVDRole, ...], em_state: EM = EM.NONE
    ) -> as_VulnerabilityCase:
        case, _ = _make_case_with_case_manager(
            self.dl,
            self.actor.id_,
            self.finder.id_,
            self.case_actor.id_,
            roles=roles,
            em_state=em_state,
        )
        return case

    def _leave(
        self,
        case: as_VulnerabilityCase,
        call_out: CloseReportCallOutBundle = CLOSE_REPORT_DETERMINISTIC,
    ):
        return SvcLeaveCaseUseCase(
            self.dl,
            LeaveCaseTriggerRequest(actor_id=self.actor.id_, case_id=case.id_),
            trigger_activity=TriggerActivityAdapter(self.dl),
            call_out=call_out,
        ).execute()

    @pytest.mark.spec("TRIG-13-001")
    @pytest.mark.parametrize(
        "roles", [_NON_OWNER, _OWNER], ids=["non-owner", "case-owner"]
    )
    def test_any_participant_sends_leave_to_the_case_manager(self, roles):
        """A non-owner and the Case Owner each queue one Leave to the CM."""
        case = self._case(roles)
        before = set(self.dl.outbox_list())

        result = self._leave(case)

        new_ids = set(self.dl.outbox_list()) - before
        assert len(new_ids) == 1
        activity = self.dl.read(next(iter(new_ids)))
        assert activity is not None
        assert _recipients(activity) == [self.case_actor.id_]
        assert result.activity is not None
        assert result.activity["type"] == "Leave"
        assert result.activity["actor"] == self.actor.id_

    @pytest.mark.spec("TRIG-13-002")
    @pytest.mark.parametrize(
        "roles", [_NON_OWNER, _OWNER], ids=["non-owner", "case-owner"]
    )
    def test_pre_close_action_runs_before_the_leave_is_queued(self, roles):
        """The call-out ticks once, with the Leave not yet in the outbox."""
        case = self._case(roles)
        before = set(self.dl.outbox_list())
        recorder = _PreCloseRecorder(self.dl)

        self._leave(case, call_out=recorder.bundle())

        assert recorder.outbox_at_run == [before]
        assert len(set(self.dl.outbox_list()) - before) == 1

    @pytest.mark.spec("TRIG-13-002")
    def test_failing_pre_close_action_fails_the_trigger_with_nothing_queued(
        self,
    ):
        """A failing backend fails the trigger before any Leave is built."""
        case = self._case(_OWNER)
        before = set(self.dl.outbox_list())
        failing = CloseReportCallOutBundle(
            pre_close_action_factory=AlwaysFail  # type: ignore[arg-type]
        )

        with pytest.raises(VultronValidationError):
            self._leave(case, call_out=failing)

        assert set(self.dl.outbox_list()) == before

    @pytest.mark.spec("TRIG-13-003")
    @pytest.mark.parametrize("em_state", [EM.ACTIVE, EM.REVISE])
    def test_case_owner_under_live_embargo_is_refused_first(self, em_state):
        """409-class refusal before the call-out runs; nothing queued."""
        case = self._case(_OWNER, em_state=em_state)
        before = set(self.dl.outbox_list())
        recorder = _PreCloseRecorder(self.dl)

        with pytest.raises(
            VultronInvalidStateTransitionError, match="terminate the embargo"
        ):
            self._leave(case, call_out=recorder.bundle())

        assert recorder.outbox_at_run == []
        assert set(self.dl.outbox_list()) == before

    @pytest.mark.spec("TRIG-13-003")
    @pytest.mark.parametrize("em_state", [EM.ACTIVE, EM.REVISE])
    def test_non_owner_under_live_embargo_is_not_blocked(self, em_state):
        """Only the Case Owner's leave is blocked by the embargo."""
        case = self._case(_NON_OWNER, em_state=em_state)
        before = set(self.dl.outbox_list())
        recorder = _PreCloseRecorder(self.dl)

        self._leave(case, call_out=recorder.bundle())

        assert len(recorder.outbox_at_run) == 1
        assert len(set(self.dl.outbox_list()) - before) == 1

    @pytest.mark.spec("TRIG-13-003")
    def test_case_owner_after_the_embargo_ends_is_not_blocked(self):
        """An exited embargo no longer blocks the owner (CM-23-011)."""
        case = self._case(_OWNER, em_state=EM.ACTIVE)
        terminate(case)
        self.dl.save(case)
        before = set(self.dl.outbox_list())

        self._leave(case)

        assert len(set(self.dl.outbox_list()) - before) == 1

    @pytest.mark.spec("TRIG-13-003")
    def test_an_owner_check_that_cannot_answer_fails_toward_refusal(self):
        """A store error in the owner check fails the trigger, sending nothing.

        The embargo check sits in a refusal arm, where a guard that cannot
        answer must not admit (notes/bt-pitfalls.md § "A Refusal Arm in a
        Selector Fails Toward 'Admit'"): the error propagates out of the
        tree instead, so the call-out does not run and nothing is queued.
        """
        case = self._case(_OWNER, em_state=EM.ACTIVE)
        before = set(self.dl.outbox_list())
        recorder = _PreCloseRecorder(self.dl)

        with (
            patch(
                "vultron.core.behaviors.sender_entitlement"
                "._holds_case_owner_role",
                side_effect=RuntimeError("store unavailable"),
            ),
            pytest.raises(VultronError),
        ):
            self._leave(case, call_out=recorder.bundle())

        assert recorder.outbox_at_run == []
        assert set(self.dl.outbox_list()) == before
