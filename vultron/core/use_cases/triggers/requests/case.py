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

"""Core trigger requests for the case verbs."""

from vultron.core.models.base import NonEmptyString
from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    StatusResult,
    SyncLogEntryResult,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.request_bodies import (
    AddNoteToCaseRequest,
    AddObjectToCaseRequest,
    AddOnBehalfStatusRequest,
    AddReportToCaseRequest,
    CaseTriggerRequest,
    CreateCaseRequest,
    LeaveCaseRequest,
    SetStubSummaryRequest,
    SyncLogEntryRequest,
)
from vultron.core.use_cases.triggers.requests._base import TriggerRequest


class EngageCaseTriggerRequest(
    TriggerRequest[ActivityResult], CaseTriggerRequest
):
    pass


class DeferCaseTriggerRequest(
    TriggerRequest[ActivityResult], CaseTriggerRequest
):
    pass


class LeaveCaseTriggerRequest(
    TriggerRequest[ActivityResult], LeaveCaseRequest
):
    """Trigger request for an actor to send Leave(VulnerabilityCase).

    Routes ``Leave(VulnerabilityCase)`` to the Case Actor inbox so the
    Case Actor can commit a ``close_case`` ledger entry and broadcast it
    to all participants (ADR-0050).  The ``leave-case`` route's body is
    ``LeaveCaseRequest`` (TRIG-13-001).
    """


class AddNoteToCaseTriggerRequest(
    TriggerRequest[NoteResult], AddNoteToCaseRequest
):
    """Trigger request for adding a note to a case."""


class CreateCaseTriggerRequest(TriggerRequest[CaseResult], CreateCaseRequest):
    """Trigger request to create a new VulnerabilityCase.

    The actor creates a local case and emits a CreateCaseActivity queued in
    the outbox for delivery to the CaseActor (or other recipients).
    """


class AddObjectToCaseTriggerRequest(
    TriggerRequest[ActivityResult], AddObjectToCaseRequest
):
    """Trigger request to attach an existing AS2 object to a case.

    The object must already exist in the actor's datalayer.  The use case
    will read it by ``object_id`` and queue an ``Add(object)[target=VulnerabilityCase]``
    activity in the actor's outbox.  Type-specific wrappers (e.g.,
    ``AddReportToCaseTriggerRequest``) extend this with additional
    type-validation before delegating here.
    """


class AddReportToCaseTriggerRequest(
    TriggerRequest[ActivityResult], AddReportToCaseRequest
):
    """Trigger request to link a report to an existing case."""


class AddParticipantStatusTriggerRequest(
    TriggerRequest[StatusResult], CaseTriggerRequest
):
    """Trigger request to send a ParticipantStatus update to the case.

    The actor self-reports their current RM/VF/D/PXA state to the Case Manager.
    Emits an Add(ParticipantStatus)[target=CaseParticipant] activity.  The
    demo ``notify-*`` routes build this from their ``CaseTriggerRequest``-shaped
    bodies; no client supplies the state fields directly.
    """

    rm_state: RM | None = None
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None
    pxa_state: CS_pxa | None = None
    #: The status an earlier step of the same demo verb stored and sent.  It
    #: is not on the actor's record until the CASE_MANAGER records it
    #: (RSH-08-003), so this step is validated as the one after it.
    follows_status_id: NonEmptyString | None = None


class AddOnBehalfStatusTriggerRequest(
    TriggerRequest[StatusResult], AddOnBehalfStatusRequest
):
    """On-behalf v→V / d→D assertion by Case Manager or Case Owner.

    ``actor_id`` is the asserting actor (must hold CASE_MANAGER or CASE_OWNER);
    the body model carries ``target_actor_id`` (the vendor/deployer whose
    awareness is being recorded) and refuses ``CS_vf.VF`` (f→F), which is
    always self-declared by the Vendor role holder.

    Per ADR-0121, PRM-06-003/004/005.
    """


class SyncLogEntryTriggerRequest(
    TriggerRequest[SyncLogEntryResult], SyncLogEntryRequest
):
    """Trigger request for the demo-only ``sync-log-entry`` verb.

    Commits a canonical ``CaseLedgerEntry`` for ``case_id`` through the BT
    commit path as the case's CASE_MANAGER and fans it out to every
    participant (SYNC-02-002, SYNC-02-003; TRIG-10-004).
    """


class SetStubSummaryTriggerRequest(
    TriggerRequest[StatusResult], SetStubSummaryRequest
):
    """Trigger request for the demo-only ``set-stub-summary`` verb.

    Seeds ``stub_summary`` on the requesting actor's local DataLayer copy of
    the case so that a subsequent ``invite-actor-to-case`` trigger can build
    the stub Invite (CM-17-010, MV-10-001, #4165).
    """
