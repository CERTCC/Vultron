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

"""Owner decisions and expiry commit first and replay by copying (ADR-0124).

The owner's ``Accept(EmbargoEvent, target=Case)`` is one entry, and it is the
whole ``ACTIVATE`` register step, the ``SUPERSEDE`` of the embargo in force
included, and the owner's own agreement (CLP-07-013, MSM-07-008).  Each
``CARRY_OVER`` row a shorter revision gives an existing signatory follows as
its own CASE_MANAGER ``Update(EmbargoConsent)`` (EP-05-001).  The owner's
``Reject(EmbargoEvent, target=Case)`` is one entry too, the whole ``REJECT``
step, and changes no consent row (MSM-07-009).  An RSVP
time-out is the expired-invitation entry followed by the CASE_MANAGER's
``Update(EmbargoConsent)`` carrying the ``TIMED_OUT`` row (CM-28-009,
CM-28-014).  A replica copies every entry through the one apply function and
reaches the CASE_MANAGER's register and rows.  Each actor has its own store
(TB-06-007); a replica is handed the CASE_MANAGER's ledger broadcast only.
"""

import json
from typing import Any, cast

import pytest

from test.support.ledger import committed_event_types, fail_commits
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.expiry_tree import (
    create_commit_and_record_expiry_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_ACTIVATION_EVENT_TYPE,
    EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE,
)
from vultron.core.behaviors.sync import commit_tree
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_event_types import (
    CONSENT_ROW_VERBS,
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_EVENT_TYPE
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)

_S = EmbargoConsentState
_EMBARGO_ENTRY_TYPES = {
    EMBARGO_ACTIVATION_EVENT_TYPE,
    EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
    *CONSENT_ROW_VERBS,
}


# -- helpers ----------------------------------------------------------------


def _propose(net: LedgerNetwork, suffix: str, days: int) -> str:
    """PROPOSER sends a revision to the CASE_MANAGER (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{suffix}",
        content=f"Terms {suffix}",
        context=net.case_id,
        end_time=days_from_now_utc(days),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/{suffix}",
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(proposal)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return revision.id_


def _owner_decides(
    net: LedgerNetwork, embargo_id: str, *, accept: bool = True
) -> Any:
    """The owner sends ``Accept`` or ``Reject(EmbargoEvent, target=Case)``.

    It first receives the relayed Invites, so its store holds the embargo
    (ADR-0122).
    """
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    adapter = TriggerActivityAdapter(net.stores[OWNER])
    send = (
        adapter.activate_embargo if accept else adapter.reject_embargo_proposal
    )
    _, sealed = send(
        embargo_id=embargo_id, case_id=net.case_id, actor=OWNER, to=[MANAGER]
    )
    return net.receive(MANAGER, json.loads(sealed))


def _owner_activates(net: LedgerNetwork, embargo_id: str) -> Any:
    """The owner sends ``Accept(EmbargoEvent, target=Case)`` (ADR-0122)."""
    return _owner_decides(net, embargo_id)


def _owner_rejects(net: LedgerNetwork, embargo_id: str) -> Any:
    """The owner sends ``Reject(EmbargoEvent, target=Case)`` (ADR-0122)."""
    return _owner_decides(net, embargo_id, accept=False)


def _sync(net: LedgerNetwork, replica: str) -> list[str]:
    """Deliver the ledger broadcast not yet sent to *replica*; each applies."""
    applied = []
    for type_, verdict in net.deliver(MANAGER, to=replica, type_="Announce"):
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )
        applied.append(type_)
    return applied


def _register(net: LedgerNetwork, holder: str) -> list[dict[str, Any]]:
    return [
        entry.model_dump(mode="json")
        for entry in net.case(holder).embargo_register
    ]


def _rows(net: LedgerNetwork, holder: str) -> dict[str, list[dict]]:
    """Every participant's consent rows in *holder*'s store, by actor."""
    case = net.case(holder)
    rows = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        record = net.stores[holder].read(participant_id)
        if isinstance(record, CaseParticipant):
            rows[actor_id] = [
                row.model_dump(mode="json") for row in record.embargo_consents
            ]
    return rows


def _row(
    net: LedgerNetwork, holder: str, actor_id: str, embargo_id: str
) -> EmbargoConsent | None:
    case = net.case(holder)
    record = cast(
        CaseParticipant,
        net.stores[holder].read(case.actor_participant_index[actor_id]),
    )
    return record.held_row(embargo_id)


def _state(
    net: LedgerNetwork, holder: str, actor_id: str, embargo_id: str
) -> EmbargoConsentState:
    row = _row(net, holder, actor_id, embargo_id)
    assert row is not None, (holder, actor_id, embargo_id)
    return row.state


def _embargo_entries(net: LedgerNetwork, since: int) -> list[str]:
    """The embargo and consent entries committed after the first *since*."""
    return [
        event_type
        for event_type in committed_event_types(
            net.stores[MANAGER], net.case_id
        )[since:]
        if event_type in _EMBARGO_ENTRY_TYPES
    ]


def _count(net: LedgerNetwork) -> int:
    return len(committed_event_types(net.stores[MANAGER], net.case_id))


def _assert_replicas_match(net: LedgerNetwork, replicas: tuple[str, ...]):
    for replica in replicas:
        _sync(net, replica)
        assert _register(net, replica) == _register(net, MANAGER), replica
        assert _rows(net, replica) == _rows(net, MANAGER), replica


def _carried_over(
    net: LedgerNetwork,
    revision_id: str,
    *,
    excluding: frozenset[str] = frozenset({OWNER, PROPOSER}),
) -> set[str]:
    """Actors whose row for *revision_id* reads ``AGREED``, other than the
    owner (its own Accept agrees) and the revision's proposer (proposing
    agrees): the activation carried them over."""
    case = net.case(MANAGER)
    return {
        actor_id
        for actor_id in case.actor_participant_index
        if actor_id not in excluding
        and (row := _row(net, MANAGER, actor_id, revision_id)) is not None
        and row.state is _S.AGREED
    }


# -- the received owner's activation ----------------------------------------


class TestReceivedActivation:
    """The owner is not the CASE_MANAGER and sends its Accept to it."""

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("EP-05-001")
    @pytest.mark.spec("MSM-07-005")
    def test_the_accept_then_one_update_per_carried_over_row(self):
        """A shorter revision: the Accept is the step and the owner's
        agreement; every other signatory's row is its own entry."""
        net = LedgerNetwork("https://example.org/cases/ac-received")
        revision_id = _propose(net, "short", 30)
        since = _count(net)

        assert _owner_activates(net, revision_id).disposition is (
            HandlerDisposition.APPLIED
        )

        case = net.case(MANAGER)
        assert case.active_embargo_id == revision_id
        assert case.embargo_register_status(net.initial_embargo_id) is (
            EmbargoRegisterStatus.SUPERSEDED
        )
        # One Accept, then one Update per carried-over row; no supersede
        # entry and no entry for the owner's own row.
        carried = _carried_over(net, revision_id)
        assert carried == {MANAGER, BYSTANDER}
        assert _embargo_entries(net, since) == [
            EMBARGO_ACTIVATION_EVENT_TYPE,
            *[UPDATE_EMBARGO_CONSENT_EVENT_TYPE] * len(carried),
        ]
        assert _state(net, MANAGER, OWNER, revision_id) is _S.AGREED

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EP-09-007")
    def test_replicas_hold_the_managers_register_and_rows(self):
        net = LedgerNetwork("https://example.org/cases/ac-received-copy")
        revision_id = _propose(net, "short", 30)
        _owner_activates(net, revision_id)

        _assert_replicas_match(net, (OWNER, BYSTANDER))
        for replica in (OWNER, BYSTANDER):
            assert net.case(replica).em_state is EM.ACTIVE

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EMB-18-005")
    def test_with_another_proposal_open(self):
        """The other proposal stays open (EM REVISE) everywhere."""
        net = LedgerNetwork("https://example.org/cases/ac-received-open")
        revision_id = _propose(net, "short", 30)
        other_id = _propose(net, "other", 60)
        _owner_activates(net, revision_id)

        case = net.case(MANAGER)
        assert case.active_embargo_id == revision_id
        assert case.proposed_embargo_ids == [other_id]
        assert case.em_state is EM.REVISE
        _assert_replicas_match(net, (OWNER, BYSTANDER))

    @pytest.mark.spec("EP-05-001")
    def test_a_longer_revision_carries_nobody_over(self):
        """Only the Accept is committed: no consent row follows it."""
        net = LedgerNetwork("https://example.org/cases/ac-received-long")
        revision_id = _propose(net, "long", 120)
        since = _count(net)

        _owner_activates(net, revision_id)

        assert _embargo_entries(net, since) == [EMBARGO_ACTIVATION_EVENT_TYPE]
        assert _state(net, MANAGER, OWNER, revision_id) is _S.AGREED
        assert _carried_over(net, revision_id) == set()

    @pytest.mark.spec("CLP-07-013")
    def test_a_failed_carry_over_commit_writes_only_what_committed(
        self, monkeypatch
    ):
        """The Accept is committed by intake; the second carry-over commit
        fails, so its row is not written, and the first row is."""
        net = LedgerNetwork("https://example.org/cases/ac-received-fail")
        revision_id = _propose(net, "short", 30)
        failed = fail_commits(
            monkeypatch,
            commit_tree,
            allowed=1,
            when=lambda kw: (
                kw["event_type"] == UPDATE_EMBARGO_CONSENT_EVENT_TYPE
            ),
        )

        # A failed commit is not a refusal: the handler raises (BT-14-001).
        with pytest.raises(VultronBTInternalError, match="ledger commit"):
            _owner_activates(net, revision_id)

        assert len(failed) == 2
        case = net.case(MANAGER)
        assert case.active_embargo_id == revision_id
        assert _state(net, MANAGER, OWNER, revision_id) is _S.AGREED
        assert len(_carried_over(net, revision_id)) == 1


# -- the received owner's rejection -----------------------------------------


class TestReceivedRejection:
    """The owner is not the CASE_MANAGER and sends its Reject to it.

    The ``Reject`` entry is the whole ``REJECT`` step: no consent row
    changes, so no ``Update(EmbargoConsent)`` follows it (MSM-07-009), and
    every replica copies the step (CM-23-016).
    """

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("MSM-07-009")
    def test_the_reject_is_the_only_entry(self):
        net = LedgerNetwork("https://example.org/cases/rj-received")
        revision_id = _propose(net, "short", 30)
        rows = _rows(net, MANAGER)
        since = _count(net)

        assert _owner_rejects(net, revision_id).disposition is (
            HandlerDisposition.APPLIED
        )

        case = net.case(MANAGER)
        assert case.embargo_register_status(revision_id) is (
            EmbargoRegisterStatus.REJECTED
        )
        assert case.active_embargo_id == net.initial_embargo_id
        assert _embargo_entries(net, since) == [
            EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE
        ]
        assert _rows(net, MANAGER) == rows

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EP-08-001")
    def test_with_one_proposal_open(self):
        """The last open revision: EM returns to the prior terms (EJ)."""
        net = LedgerNetwork("https://example.org/cases/rj-received-one")
        revision_id = _propose(net, "short", 30)
        _owner_rejects(net, revision_id)

        _assert_replicas_match(net, (OWNER, BYSTANDER))
        for holder in (MANAGER, OWNER, BYSTANDER):
            case = net.case(holder)
            assert case.em_state is EM.ACTIVE, holder
            assert case.proposed_embargo_ids == [], holder

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("EP-08-001")
    def test_with_several_proposals_open(self):
        """Another revision stays open (EM REVISE) everywhere, and the next
        rejection then returns every node to the prior terms."""
        net = LedgerNetwork("https://example.org/cases/rj-received-several")
        first_id = _propose(net, "short", 30)
        second_id = _propose(net, "mid", 60)
        third_id = _propose(net, "long", 90)
        _owner_rejects(net, second_id)

        _assert_replicas_match(net, (OWNER, BYSTANDER))
        for holder in (MANAGER, OWNER, BYSTANDER):
            case = net.case(holder)
            assert case.em_state is EM.REVISE, holder
            assert case.proposed_embargo_ids == [first_id, third_id], holder

        _owner_rejects(net, first_id)
        _owner_rejects(net, third_id)

        _assert_replicas_match(net, (OWNER, BYSTANDER))
        for holder in (MANAGER, OWNER, BYSTANDER):
            case = net.case(holder)
            assert case.em_state is EM.ACTIVE, holder
            assert case.active_embargo_id == net.initial_embargo_id, holder


# -- the managing owner's activation by trigger -----------------------------


def _managing_owner(case_id: str) -> LedgerNetwork:
    net = LedgerNetwork(case_id, owner=MANAGER)
    net.stores[MANAGER].create(as_Service(id_=MANAGER, name="Coordinator"))
    return net


def _ports(net: LedgerNetwork) -> dict[str, Any]:
    dl = net.stores[MANAGER]
    return {
        "trigger_activity": TriggerActivityAdapter(dl),
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


def _manager_revises(net: LedgerNetwork, days: int) -> str:
    SvcProposeEmbargoRevisionUseCase(
        net.stores[MANAGER],
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(days),
        ),
        **_ports(net),
    ).execute()
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
    return revision_id


def _manager_activates(net: LedgerNetwork) -> None:
    SvcAcceptEmbargoUseCase(
        net.stores[MANAGER],
        AcceptEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_ports(net),
    ).execute()


class TestTriggerActivation:
    """The case owner is the CASE_MANAGER and activates by trigger."""

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("EP-09-008")
    def test_the_accept_is_committed_before_the_case_changes(
        self, monkeypatch
    ):
        net = _managing_owner("https://example.org/cases/ac-trigger-order")
        revision_id = _manager_revises(net, 30)
        since = _count(net)
        active_at_commit: list[str | None] = []

        def _observe(kwargs: dict[str, Any]) -> bool:
            if kwargs["event_type"] == EMBARGO_ACTIVATION_EVENT_TYPE:
                active_at_commit.append(net.case(MANAGER).active_embargo_id)
            return False  # every commit runs

        fail_commits(monkeypatch, commit_tree, when=_observe)
        _manager_activates(net)

        assert active_at_commit == [net.initial_embargo_id]
        assert net.case(MANAGER).active_embargo_id == revision_id
        # The proposer and the bystander were signatories to the initial
        # embargo: one CARRY_OVER entry each.
        assert _carried_over(
            net, revision_id, excluding=frozenset({MANAGER})
        ) == {PROPOSER, BYSTANDER}
        assert _embargo_entries(net, since) == [
            EMBARGO_ACTIVATION_EVENT_TYPE,
            *[UPDATE_EMBARGO_CONSENT_EVENT_TYPE] * 2,
        ]
        _assert_replicas_match(net, (BYSTANDER,))

    @pytest.mark.spec("CLP-07-013")
    def test_a_failed_accept_commit_leaves_no_write_behind(self, monkeypatch):
        net = _managing_owner("https://example.org/cases/ac-trigger-fail")
        revision_id = _manager_revises(net, 30)
        register, rows = _register(net, MANAGER), _rows(net, MANAGER)
        failed = fail_commits(
            monkeypatch,
            commit_tree,
            when=lambda kw: kw["event_type"] == EMBARGO_ACTIVATION_EVENT_TYPE,
        )

        # A failed commit is not a refusal: the handler raises (BT-14-001).
        with pytest.raises(VultronBTInternalError, match="ledger commit"):
            _manager_activates(net)

        assert len(failed) == 1
        assert _register(net, MANAGER) == register
        assert _rows(net, MANAGER) == rows
        assert net.case(MANAGER).proposed_embargo_ids == [revision_id]
        assert EMBARGO_ACTIVATION_EVENT_TYPE not in committed_event_types(
            net.stores[MANAGER], net.case_id
        )

        monkeypatch.undo()
        _manager_activates(net)
        assert net.case(MANAGER).active_embargo_id == revision_id


# -- an RSVP time-out -------------------------------------------------------


def _invited_bystander(name: str) -> tuple[LedgerNetwork, str]:
    """A revision relayed to the bystander, whose row is now INVITED."""
    net = LedgerNetwork(f"https://example.org/cases/{name}")
    revision_id = _propose(net, "pending", 90)
    assert _state(net, MANAGER, BYSTANDER, revision_id) is _S.INVITED
    return net, revision_id


def _expire(net: LedgerNetwork, embargo_id: str):
    dl = net.stores[MANAGER]
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute_with_setup(
        tree=create_commit_and_record_expiry_tree(
            case_id=net.case_id,
            invitee_id=BYSTANDER,
            invite_id=None,
            embargo_id=embargo_id,
            published=now_utc().isoformat(),
        ),
        actor_id=MANAGER,
    )


class TestInviteTimeOut:
    @pytest.mark.spec("CM-28-009")
    @pytest.mark.spec("CM-28-014")
    @pytest.mark.spec("CLP-07-013")
    def test_the_expiry_then_the_timed_out_row(self):
        net, revision_id = _invited_bystander("ac-timeout")
        since = _count(net)

        assert _expire(net, revision_id).status.name == "SUCCESS"

        assert _embargo_entries(net, since) == [
            INVITE_EXPIRED_EVENT_TYPE,
            UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
        ]
        assert _state(net, MANAGER, BYSTANDER, revision_id) is (_S.TIMED_OUT)

    @pytest.mark.spec("CM-23-016")
    @pytest.mark.spec("CM-28-014")
    def test_replicas_copy_the_timed_out_row(self):
        net, revision_id = _invited_bystander("ac-timeout-copy")
        _expire(net, revision_id)

        _assert_replicas_match(net, (OWNER, BYSTANDER))
        assert _state(net, BYSTANDER, BYSTANDER, revision_id) is (_S.TIMED_OUT)

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.parametrize(
        "failing",
        [INVITE_EXPIRED_EVENT_TYPE, UPDATE_EMBARGO_CONSENT_EVENT_TYPE],
    )
    def test_a_failed_commit_leaves_the_row_invited(
        self, monkeypatch, failing
    ):
        net, revision_id = _invited_bystander(f"ac-timeout-fail-{failing}")
        failed = fail_commits(
            monkeypatch,
            commit_tree,
            when=lambda kw: kw["event_type"] == failing,
        )

        assert _expire(net, revision_id).status.name != "SUCCESS"

        assert len(failed) == 1
        assert _state(net, MANAGER, BYSTANDER, revision_id) is _S.INVITED

    @pytest.mark.spec("CM-28-009")
    def test_a_row_no_longer_invited_commits_nothing(self):
        net, revision_id = _invited_bystander("ac-timeout-twice")
        _expire(net, revision_id)
        since = _count(net)

        assert _expire(net, revision_id).status.name == "SUCCESS"

        assert _embargo_entries(net, since) == []
