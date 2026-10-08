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

"""Full-case Invite reply handlers apply the shared received-side RM rule.

``Accept(Invite(Actor, VulnerabilityCase))`` (RV, RECEIVED → VALID),
``TentativeReject(Invite(Actor, VulnerabilityCase))`` (RI, RECEIVED → INVALID),
and ``Reject(Invite(Actor, VulnerabilityCase))`` (RC, RECEIVED → CLOSED) each
declare one RM state for their sender.  The CASE_MANAGER adjudicates every
declaration exactly as it adjudicates an ``Add(ParticipantStatus)``: a forward
move is recorded, a non-adjacent one included; a backward move is refused and
the recorded state kept (RSH-06-006, CM-11-011).

Cases are drawn from the shared table in ``test/support/rm_declaration.py``
filtered to the RM states the three handlers declare, so these tests run
against the same rows the ``Add(ParticipantStatus)`` path already covers
(#4311 AC-2).

The handlers run as the CASE_MANAGER, in its store; the subject of every write
is the replier/sender (RSH-08-001).
"""

import logging
from collections.abc import Callable
from typing import Any, cast

import pytest

from test.support.embargo_register import activate
from test.support.rm_declaration import (
    ACTOR_ID,
    CASE_ID,
    CASE_MANAGER_ID,
    PARTICIPANT_ID,
    STRANGER_ID,
    RMDeclarationCase,
    assert_anomaly_flagged_and_noted,
    cases_declaring,
    current_status,
    recorded_rm,
    seed_case,
    status_count,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.rm import RM, RMDeclaration
from vultron.core.sync_helpers import ledger_tail_position
from vultron.core.use_cases.received.actor.full_case_invite import (
    AcceptInviteActorToFullCaseReceivedUseCase,
    RejectInviteActorToFullCaseReceivedUseCase,
    TentativeRejectInviteActorToFullCaseReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    rm_accept_full_case_invite_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

_INVITE_ID = f"{CASE_ID}/invitations/rm-rule-test"


def _seed_with_invite(dl: SqliteDataLayer, current: RM) -> tuple[Any, Any]:
    """Seed the CASE_MANAGER's store and return ``(invite, tail)``.

    Seeds the case via the shared table helper so the participant is at
    *current*, then stores a full-case Invite whose floor is the genesis
    position (the only ledger position that exists when the DataLayer is
    freshly seeded).  Marks the vendor participant as joined so
    ``CheckFullCaseReplyNode`` does not refuse on the join check.
    """
    seed_case(dl, current_status(current, CS_vf.Vf, CS_pxa.pxa), None)
    # The valid path requires an active embargo.
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    activate(case, f"{CASE_ID}/embargoes/shared-table")
    dl.save(case)
    # Ensure joined=True (seed_case creates participants that default to
    # joined=True, but set it explicitly to be safe).
    participant = cast(CaseParticipant, dl.read(PARTICIPANT_ID))
    participant.joined = True
    dl.save(participant)
    # Invite floor = genesis position (pre-first-entry).
    tail = ledger_tail_position(CASE_ID, dl)
    invite = rm_invite_to_full_case_activity(
        as_Organization(id_=ACTOR_ID),
        CASE_ID,
        tail,
        id_=_INVITE_ID,
        actor=CASE_MANAGER_ID,
        to=[ACTOR_ID],
    )
    dl.create(invite)
    return invite, tail


def _deliver(
    dl: SqliteDataLayer,
    declared: RM,
    invite: Any,
    tail: Any,
    sender: str = ACTOR_ID,
) -> Any:
    """Route the appropriate reply as the CASE_MANAGER's inbox would."""
    builders: dict[RM, Callable[..., Any]] = {
        RM.VALID: rm_accept_full_case_invite_activity,
        RM.INVALID: rm_tentative_reject_full_case_invite_activity,
        RM.CLOSED: rm_reject_full_case_invite_activity,
    }
    use_cases = {
        RM.VALID: AcceptInviteActorToFullCaseReceivedUseCase,
        RM.INVALID: TentativeRejectInviteActorToFullCaseReceivedUseCase,
        RM.CLOSED: RejectInviteActorToFullCaseReceivedUseCase,
    }
    activity = builders[declared](invite, tail, actor=sender)
    event = extract_event(activity)
    return use_cases[declared](
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


_DECLARED = (RM.VALID, RM.INVALID, RM.CLOSED)


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestFullCaseInviteRepliesApplyTheSharedRule:
    """Each handler runs the shared RM acceptance rule (RSH-06-006, #4311 AC-2)."""

    @pytest.mark.spec("RSH-06-001")
    @pytest.mark.spec("RSH-06-002")
    @pytest.mark.spec("RSH-06-006")
    @pytest.mark.spec("RSH-08-001")
    @pytest.mark.parametrize("case", cases_declaring(*_DECLARED))
    def test_records_what_the_rule_accepts(
        self, case: RMDeclarationCase, store_for
    ) -> None:
        dl = store_for(CASE_MANAGER_ID)
        invite, tail = _seed_with_invite(dl, case.current)
        before = status_count(dl)

        result = _deliver(dl, case.declared, invite, tail)

        assert recorded_rm(dl) == case.expected_rm
        if case.verdict is RMDeclaration.CONFIRMATION:
            assert status_count(dl) == before, (
                "a confirmation is recorded once (RSH-08-002)"
            )
            # The reply has no effect beyond the RM write, so a restatement
            # is the same no-op it is for the report verdicts (#4316).
            assert result.disposition is HandlerDisposition.SKIPPED, (
                result.reason
            )
        elif case.accepted:
            assert result.disposition is HandlerDisposition.APPLIED, (
                result.reason
            )
            assert status_count(dl) == before + 1, "one move, one record"
        else:
            assert result.disposition is HandlerDisposition.REFUSED, (
                result.reason
            )
            assert status_count(dl) == before, "a refusal writes nothing"

    @pytest.mark.spec("RSH-06-003")
    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.parametrize("case", cases_declaring(*_DECLARED))
    def test_flags_and_notes_the_same_anomalies(
        self, case: RMDeclarationCase, store_for, caplog
    ) -> None:
        dl = store_for(CASE_MANAGER_ID)
        invite, tail = _seed_with_invite(dl, case.current)

        with caplog.at_level(logging.WARNING):
            _deliver(dl, case.declared, invite, tail)

        assert_anomaly_flagged_and_noted(case, dl, caplog.records)


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestSenderMustBeTheInvitee:
    """A reply from anyone other than the invitee is refused (HP-01-006)."""

    @pytest.mark.spec("HP-01-006")
    @pytest.mark.spec("CM-11-017")
    @pytest.mark.parametrize(
        "declared", list(_DECLARED), ids=lambda rm: rm.name
    )
    def test_non_invitee_sender_is_refused(
        self, declared: RM, store_for
    ) -> None:
        dl = store_for(CASE_MANAGER_ID)
        invite, tail = _seed_with_invite(dl, RM.RECEIVED)
        before = status_count(dl)

        result = _deliver(dl, declared, invite, tail, sender=STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert status_count(dl) == before
