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

"""Invite-expiry BT nodes (``nodes/expiry.py``, CM-28-014, ADR-0118).

Covers the evaluation nodes (EvaluateInviteExpiryNode,
InviteExpiryChangedConsentNode) and both replay nodes
(ApplyInviteExpiryFromLedgerNode, ApplyInviteExpiryNoopFromLedgerNode).
"""

from typing import Any

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    ApplyInviteExpiryFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/expiry-nodes"
MANAGER = "https://example.org/actors/expiry-nodes-manager"
INVITEE = "https://example.org/actors/expiry-nodes-invitee"
EMBARGO_ID = f"{CASE_ID}/embargos/e1"


def _seed(
    scenario: BTTestScenario,
    consent: EmbargoConsentState = EmbargoConsentState.INVITED,
) -> str:
    manager = CaseParticipant(
        id_=f"{CASE_ID}/participants/manager",
        attributed_to=MANAGER,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    invitee = CaseParticipant(
        id_=f"{CASE_ID}/participants/invitee",
        attributed_to=INVITEE,
        context=CASE_ID,
        embargo_consents=[
            EmbargoConsent(embargo_id=EMBARGO_ID, state=consent)
        ],
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        attributed_to=MANAGER,
        case_participants=[manager.id_, invitee.id_],
        actor_participant_index={
            MANAGER: manager.id_,
            INVITEE: invitee.id_,
        },
    )
    case.append_case_status(em_state=EM.ACTIVE)
    scenario.seed(manager, invitee, case)
    return invitee.id_


def _consent(
    scenario: BTTestScenario, participant_id: str
) -> EmbargoConsentState | None:
    record = scenario.dl.read(participant_id)
    assert isinstance(record, CaseParticipant)
    return record.consent_for(EMBARGO_ID)


def _expiry_event(actor: str | None) -> Any:
    snapshot: dict[str, Any] = {
        "type": "Expire",
        "context": CASE_ID,
    }
    if actor is not None:
        snapshot["actor"] = actor
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"{CASE_ID}/embargo_invites/i1",
            event_type=INVITE_EXPIRED_EVENT_TYPE,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )
    return _make_event(entry, actor_id=MANAGER)


class TestApplyInviteExpiryFromLedgerNode:
    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("CM-28-014")
    def test_a_replica_applies_expire_without_a_deadline(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """No deadline on the replica's record: it applies, never computes."""
        participant_id = _seed(
            bt_scenario, consent=EmbargoConsentState.INVITED
        )
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.EXPIRED
        )

    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("ADR-0118")
    def test_already_expired_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An already-EXPIRED participant is left unchanged."""
        participant_id = _seed(
            bt_scenario, consent=EmbargoConsentState.EXPIRED
        )
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.EXPIRED
        )

    @pytest.mark.executes_as(INVITEE)
    def test_an_entry_naming_no_invitee_fails(
        self, bt_scenario: BTTestScenario
    ) -> None:
        participant_id = _seed(bt_scenario)
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(None),
        )
        assert result.status == Status.FAILURE
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.INVITED
        )

    @pytest.mark.executes_as(INVITEE)
    def test_an_invitee_the_replica_does_not_hold_is_skipped(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario)
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event("https://example.org/actors/elsewhere"),
        )
        bt_scenario.assert_success(result)

    @pytest.mark.executes_as(INVITEE)
    def test_a_replica_without_the_case_skips(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(INVITEE),
        )
        bt_scenario.assert_success(result)


def _honour_late_accept_event(
    actor: str | None, embargo_id: str = EMBARGO_ID
) -> Any:
    """Build an AnnounceLogEntry event wrapping a HONOUR_LATE_ACCEPT_EVENT_TYPE entry."""
    from vultron.core.models.rsvp_deadline import (
        HONOUR_LATE_ACCEPT_EVENT_TYPE,
        HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
    )

    snapshot: dict[str, Any] = {
        "type": HONOUR_LATE_ACCEPT_SNAPSHOT_TYPE,
        "context": CASE_ID,
        "object": {
            "type": "Invite",
            "id": f"{CASE_ID}/invites/i1",
            "object": {"type": "EmbargoEvent", "id": embargo_id},
        },
    }
    if actor is not None:
        snapshot["actor"] = actor
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"{CASE_ID}/invites/i1",
            event_type=HONOUR_LATE_ACCEPT_EVENT_TYPE,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )
    return _make_event(entry, actor_id=MANAGER)


class TestApplyHonourLateAcceptFromLedgerNode:
    """Replica replay of the CASE_MANAGER's honour decision (EMB-17-001, RSH-08-004)."""

    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("EMB-17-001", "RSH-08-004", "ADR-0118")
    def test_expired_participant_row_becomes_accepted_on_replica(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A replica applies EXPIRED → ACCEPTED from the honour entry."""
        from vultron.core.behaviors.embargo.nodes.expiry import (
            ApplyHonourLateAcceptFromLedgerNode,
        )

        participant_id = _seed(
            bt_scenario, consent=EmbargoConsentState.EXPIRED
        )
        result = bt_scenario.run(
            ApplyHonourLateAcceptFromLedgerNode(name="ApplyHonour"),
            activity=_honour_late_accept_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.ACCEPTED
        )

    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("EMB-17-001", "CM-18-003", "ADR-0118")
    def test_declined_participant_row_becomes_accepted_on_replica(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A replica applies DECLINED → INVITED → ACCEPTED from the honour entry."""
        from vultron.core.behaviors.embargo.nodes.expiry import (
            ApplyHonourLateAcceptFromLedgerNode,
        )

        participant_id = _seed(
            bt_scenario, consent=EmbargoConsentState.DECLINED
        )
        result = bt_scenario.run(
            ApplyHonourLateAcceptFromLedgerNode(name="ApplyHonour"),
            activity=_honour_late_accept_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.ACCEPTED
        )

    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("ADR-0118")
    def test_already_accepted_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An ACCEPTED row is not changed by replay (idempotent)."""
        from vultron.core.behaviors.embargo.nodes.expiry import (
            ApplyHonourLateAcceptFromLedgerNode,
        )

        participant_id = _seed(
            bt_scenario, consent=EmbargoConsentState.ACCEPTED
        )
        result = bt_scenario.run(
            ApplyHonourLateAcceptFromLedgerNode(name="ApplyHonour"),
            activity=_honour_late_accept_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert (
            _consent(bt_scenario, participant_id)
            is EmbargoConsentState.ACCEPTED
        )

    @pytest.mark.executes_as(INVITEE)
    def test_entry_naming_no_actor_fails(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An entry without an actor field → FAILURE (SYNC-12-001)."""
        from vultron.core.behaviors.embargo.nodes.expiry import (
            ApplyHonourLateAcceptFromLedgerNode,
        )

        _seed(bt_scenario, consent=EmbargoConsentState.EXPIRED)
        result = bt_scenario.run(
            ApplyHonourLateAcceptFromLedgerNode(name="ApplyHonour"),
            activity=_honour_late_accept_event(None),
        )
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(INVITEE)
    def test_replica_without_case_skips(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A replica without the case skips with SUCCESS (Regime 2, ADR-0087)."""
        from vultron.core.behaviors.embargo.nodes.expiry import (
            ApplyHonourLateAcceptFromLedgerNode,
        )

        # Do NOT seed a case — partial replica (ADR-0087).
        result = bt_scenario.run(
            ApplyHonourLateAcceptFromLedgerNode(name="ApplyHonour"),
            activity=_honour_late_accept_event(INVITEE),
        )
        bt_scenario.assert_success(result)
