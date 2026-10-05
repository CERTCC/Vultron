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

"""Invite-expiry replica replay leaf (``nodes/expiry.py``, CM-28-014, ADR-0118).

The replay leaf is exercised as a replica applying a committed expiry entry.
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
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_EVENT_TYPE
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/expiry-nodes"
MANAGER = "https://example.org/actors/expiry-nodes-manager"
INVITEE = "https://example.org/actors/expiry-nodes-invitee"


def _seed(
    scenario: BTTestScenario,
    pec: PEC = PEC.INVITED,
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
        embargo_consent_state=pec,
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


def _pec(scenario: BTTestScenario, participant_id: str) -> PEC:
    record = scenario.dl.read(participant_id)
    assert isinstance(record, CaseParticipant)
    return PEC(record.embargo_consent_state)


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
        participant_id = _seed(bt_scenario, pec=PEC.INVITED)
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, participant_id) is PEC.EXPIRED

    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("ADR-0118")
    def test_already_expired_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An already-EXPIRED participant is left unchanged."""
        participant_id = _seed(bt_scenario, pec=PEC.EXPIRED)
        result = bt_scenario.run(
            ApplyInviteExpiryFromLedgerNode(name="ApplyExpiry"),
            activity=_expiry_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, participant_id) is PEC.EXPIRED

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
        assert _pec(bt_scenario, participant_id) is PEC.INVITED

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
