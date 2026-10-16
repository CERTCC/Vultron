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
"""The CASE_MANAGER's sweep of overdue embargo invitations (CM-28-015).

Before it commits the case owner's decision on a proposal, and on every
other embargo activity it handles, the CASE_MANAGER expires every ``INVITED``
row whose RSVP deadline has passed on an open proposal or the embargo in
force.  The sweep is a clock decision (CLP-10-025, ADR-0135): it runs after
the door guards, so a sender with no standing makes it write nothing, and
before the activity's own precondition guards, so an expiry is recorded even
when the activity that prompted it is then refused.  The owner learns of
each timeout from the expiry entry's fan-out (MSM-07-007).
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import py_trees
import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.embargo_register import activate, propose, reject
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    OVERDUE_INVITES_SWEEP_NAME,
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.nodes import (
    invitation_expiry as _sweep_module,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_event_types import (
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_EVENT_TYPE
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received.embargo import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcRejectEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    reject_embargo_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE_ID = "https://example.org/cases/overdue-sweep"
_PROPOSAL_ID = f"{_CASE_ID}/embargo_events/proposal"
_MANAGER = "https://example.org/users/coord"
_OWNER = "https://example.org/users/vendor"
_INVITEE = "https://example.org/users/finder"
_OTHER = "https://example.org/users/other-vendor"

_PAST = datetime.now(tz=UTC) - timedelta(days=1)
_FUTURE = datetime.now(tz=UTC) + timedelta(days=7)

_DECISIONS = [
    pytest.param(
        activate_embargo_activity,
        ActivateEmbargoOnCaseReceivedUseCase,
        "activate_embargo_on_case",
        id="activate",
    ),
    pytest.param(
        reject_embargo_proposal_activity,
        RejectEmbargoProposalOnCaseReceivedUseCase,
        "reject_embargo_proposal_on_case",
        id="reject-proposal",
    ),
]


def _invited(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    actor_id: str,
    rows: dict[str, datetime],
) -> CaseParticipant:
    """Attach *actor_id* to *case*, ``INVITED`` to each embargo in *rows*.

    Each row's deadline is the value it maps to (CM-28-013).
    """
    participant = CaseParticipant(
        id_=f"{case.id_}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.FINDER],
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo_id,
                state=EmbargoConsentState.INVITED,
                rsvp_deadline=deadline,
                attributed_to=actor_id,
            )
            for embargo_id, deadline in rows.items()
        ],
    )
    case.add_participant(participant)
    dl.create(participant)
    return participant


def _store(
    *,
    deadline: datetime = _PAST,
    owner: str = _OWNER,
    other_deadline: datetime | None = None,
) -> tuple[SqliteDataLayer, as_EmbargoEvent]:
    """The CASE_MANAGER's store of a case with one open proposal.

    *owner* owns the case; the coordinator manages it.  The invitee's
    Invite to the proposal is unanswered with *deadline*; with
    *other_deadline*, a second participant is invited too.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    case = VulnerabilityCase(
        id_=_CASE_ID, name="Overdue sweep", attributed_to=owner
    )
    embargo = as_EmbargoEvent(
        id_=_PROPOSAL_ID, context=_CASE_ID, end_time=days_from_now_utc(30)
    )
    propose(case, embargo.id_)
    seed_case_manager_participant(dl, case, _MANAGER)
    if owner != _MANAGER:
        seed_case_owner_participant(dl, case, owner)
    _invited(dl, case, _INVITEE, {embargo.id_: deadline})
    if other_deadline is not None:
        _invited(dl, case, _OTHER, {embargo.id_: other_deadline})
    dl.create(case)
    dl.create(embargo)
    return dl, embargo


def _ports(dl: SqliteDataLayer, sync_port: Any = None) -> dict[str, Any]:
    return {
        "sync_port": sync_port or SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
        "trigger_activity": TriggerActivityAdapter(dl),
    }


def _decide(
    dl: SqliteDataLayer,
    make_payload: Any,
    factory: Any,
    use_case: Any,
    embargo: as_EmbargoEvent,
    *,
    sender: str = _OWNER,
):
    activity = factory(embargo, target=_CASE_ID, actor=sender, to=[_MANAGER])
    event = make_payload(activity, receiving_actor_id=_MANAGER)
    return use_case(dl, event, **_ports(dl)).execute()


def _ledger(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == _CASE_ID
        ),
        key=lambda e: e.log_index,
    )


def _event_types(dl: SqliteDataLayer) -> list[str]:
    return [str(e.event_type) for e in _ledger(dl)]


def _expiries(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return [
        e for e in _ledger(dl) if e.event_type == INVITE_EXPIRED_EVENT_TYPE
    ]


def _consent(
    dl: SqliteDataLayer, actor_id: str, embargo_id: str = _PROPOSAL_ID
) -> EmbargoConsentState:
    case = cast(VulnerabilityCase, dl.read(_CASE_ID))
    record = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(record, CaseParticipant)
    return record.consent_for(embargo_id)


def _sweep(dl: SqliteDataLayer) -> py_trees.common.Status:
    """Run the sweep alone, as the CASE_MANAGER, with production's ports."""
    (decision,) = embargo_clock_decisions(_CASE_ID)
    result = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute_with_setup(tree=decision, actor_id=_MANAGER)
    assert not result.internal_error, result.feedback_message
    return result.status


class TestOwnerDecision:
    """AC-1: the expiry precedes the owner's decision entry."""

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.spec("CM-28-009")
    @pytest.mark.parametrize(("factory", "use_case", "decided"), _DECISIONS)
    def test_the_expiry_is_committed_before_the_decision(
        self, make_payload, factory, use_case, decided
    ):
        dl, embargo = _store()

        result = _decide(dl, make_payload, factory, use_case, embargo)

        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        types = _event_types(dl)
        expiry = types.index(INVITE_EXPIRED_EVENT_TYPE)
        # The expiry, then the CASE_MANAGER's TIMED_OUT row, then the
        # owner's decision (CM-28-014, ADR-0124).
        assert types[expiry + 1] == UPDATE_EMBARGO_CONSENT_EVENT_TYPE
        assert expiry < types.index(decided)
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT
        (entry,) = _expiries(dl)
        assert entry.payload_snapshot["actor"] == _INVITEE

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.parametrize(("factory", "use_case", "decided"), _DECISIONS)
    def test_a_row_not_yet_due_stays_invited(
        self, make_payload, factory, use_case, decided
    ):
        dl, embargo = _store(deadline=_FUTURE)

        result = _decide(dl, make_payload, factory, use_case, embargo)

        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        assert _expiries(dl) == []
        assert decided in _event_types(dl)
        assert _consent(dl, _INVITEE) == EmbargoConsentState.INVITED


class TestDoorGuardsFirst:
    """AC-3 (reworded): the sweep runs only once the door guards admit."""

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize(("factory", "use_case", "decided"), _DECISIONS)
    def test_a_non_owners_decision_is_refused_with_no_expiry(
        self, make_payload, factory, use_case, decided
    ):
        dl, embargo = _store()

        result = _decide(
            dl, make_payload, factory, use_case, embargo, sender=_INVITEE
        )

        assert result.disposition is HandlerDisposition.REFUSED
        assert _ledger(dl) == []
        assert _consent(dl, _INVITEE) == EmbargoConsentState.INVITED

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.spec("CLP-10-025")
    @pytest.mark.parametrize(("factory", "use_case", "decided"), _DECISIONS)
    def test_a_decision_on_no_open_proposal_is_refused_after_the_expiry(
        self, make_payload, factory, use_case, decided
    ):
        """The expiry is the CASE_MANAGER's own clock decision, so it is
        recorded although the decision that prompted it is refused."""
        dl, _proposal = _store()
        stray = as_EmbargoEvent(
            id_=f"{_CASE_ID}/embargo_events/never-proposed",
            context=_CASE_ID,
            end_time=days_from_now_utc(30),
        )
        dl.create(stray)

        result = _decide(dl, make_payload, factory, use_case, stray)

        assert result.disposition is HandlerDisposition.REFUSED
        assert _event_types(dl) == [
            INVITE_EXPIRED_EVENT_TYPE,
            UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
        ]
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT


class TestSweepScope:
    """AC-1/AC-4: what the sweep expires, and that it expires it once."""

    @pytest.mark.spec("CM-28-015")
    def test_a_repeat_sweep_commits_no_second_expiry(self):
        dl, _embargo = _store()

        _sweep(dl)
        _sweep(dl)

        assert len(_expiries(dl)) == 1
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT

    @pytest.mark.spec("CM-28-015")
    def test_only_the_overdue_row_is_swept(self):
        dl, _embargo = _store(other_deadline=_FUTURE)

        _sweep(dl)

        (entry,) = _expiries(dl)
        assert entry.payload_snapshot["actor"] == _INVITEE
        assert _consent(dl, _OTHER) == EmbargoConsentState.INVITED

    @pytest.mark.spec("CM-28-015")
    def test_a_row_of_a_replaced_embargo_is_frozen(self):
        """An overdue row on a rejected proposal is left as it is."""
        dl, embargo = _store()
        case = cast(VulnerabilityCase, dl.read(_CASE_ID))
        reject(case, embargo.id_)
        dl.save(case)

        _sweep(dl)

        assert _expiries(dl) == []
        assert _consent(dl, _INVITEE) == EmbargoConsentState.INVITED

    @pytest.mark.spec("CM-28-015")
    def test_a_row_of_the_embargo_in_force_is_swept(self):
        dl, embargo = _store()
        case = cast(VulnerabilityCase, dl.read(_CASE_ID))
        activate(case, embargo.id_)
        dl.save(case)

        _sweep(dl)

        assert len(_expiries(dl)) == 1
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT

    @pytest.mark.spec("CLP-10-025")
    def test_a_refused_expiry_is_logged_and_the_sweep_goes_on(
        self, monkeypatch, caplog
    ):
        """A refused commit writes no row; the sweep still succeeds, so the
        tree it runs in continues (CLP-10-025)."""
        dl, _embargo = _store(other_deadline=_PAST)
        refused = iter([True, False])
        original = _sweep_module.create_commit_and_record_expiry_tree

        def _first_refused(**kwargs: Any):
            if next(refused):
                return py_trees.behaviours.Failure(name="RefusedExpiry")
            return original(**kwargs)

        monkeypatch.setattr(
            _sweep_module,
            "create_commit_and_record_expiry_tree",
            _first_refused,
        )

        with caplog.at_level("WARNING"):
            status = _sweep(dl)

        assert status is py_trees.common.Status.SUCCESS
        (entry,) = _expiries(dl)
        assert entry.payload_snapshot["actor"] == _OTHER
        assert _consent(dl, _INVITEE) == EmbargoConsentState.INVITED
        assert _consent(dl, _OTHER) == EmbargoConsentState.TIMED_OUT
        assert any(
            "could not expire the Invite" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.spec("CLP-10-025")
    def test_an_internal_error_in_an_expiry_ends_the_sweep(self, monkeypatch):
        """An internal error is never absorbed as a refusal (ADR-0095)."""

        class _Crash(py_trees.behaviour.Behaviour):
            def update(self) -> py_trees.common.Status:
                raise RuntimeError("boom")

        dl, _embargo = _store()
        monkeypatch.setattr(
            _sweep_module,
            "create_commit_and_record_expiry_tree",
            lambda **_: _Crash(name="Crash"),
        )
        (decision,) = embargo_clock_decisions(_CASE_ID)

        result = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute_with_setup(tree=decision, actor_id=_MANAGER)

        assert result.internal_error
        assert _expiries(dl) == []

    @pytest.mark.spec("CM-28-014")
    def test_a_store_that_is_not_the_case_manager_sweeps_nothing(self):
        """The clock-decision gate runs the sweep only at the CASE_MANAGER."""
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            create_clock_decision_gate,
        )

        dl, _embargo = _store()
        gate = create_clock_decision_gate(
            _CASE_ID, embargo_clock_decisions(_CASE_ID)
        )

        BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute_with_setup(tree=gate, actor_id=_OWNER)

        assert _expiries(dl) == []
        assert _consent(dl, _INVITEE) == EmbargoConsentState.INVITED


class TestOtherEmbargoActivity:
    """AC-2 and AC-6: another participant's answer prompts the sweep."""

    def _reject_invite(self, dl: SqliteDataLayer, make_payload, sync: Any):
        """``_OTHER`` declines its Invite to the proposal, in time."""
        invite = em_propose_embargo_activity(
            embargo=cast(as_EmbargoEvent, dl.read(_PROPOSAL_ID)),
            context=_CASE_ID,
            actor=_MANAGER,
            to=[_OTHER],
            id_=f"{_CASE_ID}/invites/other",
        )
        dl.create(invite)
        answer = em_reject_embargo_activity(
            proposal=invite, context=_CASE_ID, actor=_OTHER, to=[_MANAGER]
        )
        event = make_payload(answer, receiving_actor_id=_MANAGER)
        return RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, **_ports(dl, sync)
        ).execute()

    @pytest.mark.spec("CM-28-015")
    def test_a_participants_reject_of_its_invite_sweeps_first(
        self, make_payload
    ):
        dl, _embargo = _store(other_deadline=_FUTURE)

        result = self._reject_invite(dl, make_payload, SyncActivityAdapter(dl))

        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        types = _event_types(dl)
        assert types.index(INVITE_EXPIRED_EVENT_TYPE) < types.index(
            "reject_invite_to_embargo_on_case"
        )
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT
        assert _consent(dl, _OTHER) == EmbargoConsentState.DECLINED

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.spec("MSM-07-007")
    def test_the_owner_learns_of_both_from_the_fan_out_alone(
        self, make_payload
    ):
        """An owner that is not the CASE_MANAGER is sent the expiry entry and
        the Reject(Invite) entry, and nothing else is emitted for them."""
        dl, _embargo = _store(other_deadline=_FUTURE)
        sync = MagicMock(spec=SyncActivityPort)

        result = self._reject_invite(dl, make_payload, sync)

        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        announced: dict[str, set[str]] = {}
        for c in sync.send_announce_log_entry.call_args_list:
            announced.setdefault(
                str(c.kwargs["entry"].event_type), set()
            ).update(c.kwargs["to"])
        for event_type in (
            INVITE_EXPIRED_EVENT_TYPE,
            "reject_invite_to_embargo_on_case",
        ):
            assert _OWNER in announced[event_type], announced
        # No notification activity besides the fan-out (MSM-07-007): the
        # stubbed fan-out queues nothing, so the outbox stays empty.
        assert dl.outbox_list() == []


class TestOwnerTrigger:
    """AC-5: the owner's own decision trigger, run on the CASE_MANAGER."""

    @pytest.mark.spec("CM-28-015")
    @pytest.mark.spec("EP-09-008")
    @pytest.mark.parametrize(
        ("use_case", "request_model", "decided"),
        [
            pytest.param(
                SvcAcceptEmbargoUseCase,
                AcceptEmbargoTriggerRequest,
                "activate_embargo_on_case",
                id="accept",
            ),
            pytest.param(
                SvcRejectEmbargoUseCase,
                RejectEmbargoTriggerRequest,
                "reject_embargo_proposal_on_case",
                id="reject",
            ),
        ],
    )
    def test_the_trigger_sweeps_before_the_decision(
        self, use_case, request_model, decided
    ):
        dl, embargo = _store(owner=_MANAGER)
        dl.create(as_Service(id_=_MANAGER, name="Coordinator"))
        proposal = em_propose_embargo_activity(
            embargo, context=_CASE_ID, actor=_INVITEE
        )
        dl.create(proposal)
        case = cast(VulnerabilityCase, dl.read(_CASE_ID))
        case.pending_embargo_proposal_index[embargo.id_] = proposal.id_
        dl.save(case)

        use_case(
            dl,
            request_model(
                actor_id=_MANAGER, case_id=_CASE_ID, proposal_id=proposal.id_
            ),
            **_ports(dl),
        ).execute()

        types = _event_types(dl)
        assert types.index(INVITE_EXPIRED_EVENT_TYPE) < types.index(decided)
        assert _consent(dl, _INVITEE) == EmbargoConsentState.TIMED_OUT


@pytest.mark.spec("CM-28-015")
@pytest.mark.spec("CLP-10-025")
def test_every_received_embargo_tree_with_a_case_takes_the_sweep():
    """AC-2: each received embargo tree the CASE_MANAGER handles for a case
    runs the sweep in its clock-decision stage."""
    from test.architecture._received_tree_builds import built_received_trees
    from vultron.core.behaviors.case.nodes.clock_decision_stage import (
        ClockDecisionStage,
    )

    swept = {
        tree.name
        for (path, _factory), tree in built_received_trees().items()
        if path.startswith("vultron/core/behaviors/embargo/")
        for stage in tree.iterate()
        if isinstance(stage, ClockDecisionStage)
        and OVERDUE_INVITES_SWEEP_NAME in {d.name for d in stage.decisions}
    }

    assert swept == {
        "AcceptInviteToEmbargoBT",
        "ActivateEmbargoOnCaseBT",
        "InviteToEmbargoOnCaseBT",
        "RejectEmbargoProposalOnCaseBT",
        "RejectInviteToEmbargoBT",
        "RemoveEmbargoFromCaseBT",
        "WithdrawFromEmbargoOnCaseBT",
    }
