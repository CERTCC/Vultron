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


"""Request bodies for the case trigger verbs."""

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vultron.core.models.base import NonEmptyString, UriString
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.use_cases.triggers.request_bodies._base import (
    CaseTriggerRequest,
)


class AddObjectToCaseRequest(CaseTriggerRequest):
    """Request body for the add-object-to-case general trigger endpoint.

    Accepts any existing AS2 object identified by ``object_id``.  The object
    must already exist in the actor's datalayer.  Type-specific convenience
    endpoints (e.g., ``add-report-to-case``) delegate to this after
    performing their own type validation (TRIG-10-001, TRIG-10-002).

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    object_id: NonEmptyString


class AddNoteToCaseRequest(CaseTriggerRequest):
    """Request body for the add-note-to-case trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    note_name: NonEmptyString
    note_content: NonEmptyString
    in_reply_to: NonEmptyString | None = None


class CreateCaseRequest(BaseModel):
    """Request body for the create-case trigger endpoint.

    The actor creates a local VulnerabilityCase and queues a
    CreateCaseActivity in their outbox for delivery to the actors named in
    ``to``.  With no ``to`` the case is created locally and nothing is
    queued (OX-08-001); a blank ``to`` entry is refused (CS-08-002).

    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    name: NonEmptyString
    content: NonEmptyString
    report_id: NonEmptyString | None = None
    to: list[NonEmptyString] | None = None


class AddReportToCaseRequest(CaseTriggerRequest):
    """Request body for the add-report-to-case trigger endpoint.

    TRIG-03-001: Must include case_id and report_id.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    report_id: NonEmptyString


class AddOnBehalfStatusRequest(CaseTriggerRequest):
    """Request body for the add-on-behalf-status trigger.

    A Case Manager or Case Owner records a vendor's awareness (``v→V``,
    ``vf_state="Vf"``) or a deployer's deployment (``d→D``, ``d_state="D"``)
    on behalf of an existing participant (ADR-0121; PRM-06-003, PRM-06-004).
    A v→V target is typically an invitee that has not yet replied; a d→D
    target must be a deployer at RM ``ACCEPTED``, ``DEFERRED`` or
    ``CLOSED``.  ``target_actor_id`` names that participant; a
    non-participant target is refused and no participant is created
    (PRM-06-006).  Only the upward rungs are assertable on another actor's
    behalf: ``vf_state`` must be ``"Vf"`` and ``d_state`` must be ``"D"``.
    ``vf_state="VF"`` (``f→F``) is refused because fix readiness is not
    externally knowable and is only ever self-declared by the Vendor-role
    holder (PRM-06-005); the lower rungs (``"vf"``, ``"d"``) are refused
    because recording unawareness or non-deployment on someone's behalf is
    not an assertion PRM-06 permits.  At least one of ``vf_state`` /
    ``d_state`` is required.

    TRIG-03-002: Unknown fields are silently ignored.
    """

    target_actor_id: UriString
    vf_state: CS_vf | None = None
    d_state: CS_d | None = None

    @field_validator("vf_state")
    @classmethod
    def vf_state_not_fix_ready(cls, v: CS_vf | None) -> CS_vf | None:
        if v is not None and v == CS_vf.VF:
            raise ValueError(
                "f→F (CS_vf.VF) cannot be asserted on behalf of another actor"
                " (ADR-0121, PRM-06-005)"
            )
        if v is not None and v != CS_vf.Vf:
            raise ValueError(
                "only v→V (CS_vf.Vf) may be asserted on behalf of a vendor"
                f" (PRM-06-003); got {v!r}"
            )
        return v

    @field_validator("d_state")
    @classmethod
    def d_state_is_deployed(cls, v: CS_d | None) -> CS_d | None:
        if v is not None and v != CS_d.D:
            raise ValueError(
                "only d→D (CS_d.D) may be asserted on behalf of a deployer"
                f" (PRM-06-004); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def at_least_one_dimension(self) -> "AddOnBehalfStatusRequest":
        if self.vf_state is None and self.d_state is None:
            raise ValueError(
                "at least one of vf_state or d_state must be provided"
                " (PRM-06-003/004)"
            )
        return self


class NotifyFixReadyRequest(CaseTriggerRequest):
    """Request body for the notify-fix-ready demo trigger.

    Signals that the vendor has a fix ready (VFD → VFd).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class NotifyFixDeployedRequest(CaseTriggerRequest):
    """Request body for the notify-fix-deployed demo trigger.

    Signals that the fix has been deployed (VFd → VFD).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class NotifyPublishedRequest(CaseTriggerRequest):
    """Request body for the notify-published demo trigger.

    Signals that the vulnerability has been publicly disclosed (CS.VFDPxa).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class LeaveCaseRequest(CaseTriggerRequest):
    """Request body for the leave-case trigger.

    Names the case the actor leaves by sending Leave(VulnerabilityCase) to its
    CASE_MANAGER (TRIG-13-001).  For the Case Owner the Leave closes the case;
    for any other participant the case stays open (CM-23-002, CM-23-003).
    TRIG-03-002: Unknown fields are silently ignored.
    """


class SyncLogEntryRequest(CaseTriggerRequest):
    """Request body for the demo sync-log-entry trigger.

    Commits a canonical case ledger entry and fans it out to all participants
    via Announce(CaseLedgerEntry). Uses Announce(VulnerabilityCase) as the
    canonical payload type (case-actor-authored), and the entry's semantic
    type is the registry's label for it (ADR-0140), so the caller names none.

    TRIG-03-002: Unknown fields are silently ignored, so a client that still
    sends ``semantic_type`` has it ignored.
    """

    object_id: UriString


class SetStubSummaryRequest(CaseTriggerRequest):
    """Request body for the demo set-stub-summary trigger.

    Seeds ``stub_summary`` on the actor's local DataLayer copy of the case so
    that a subsequent ``invite-actor-to-case`` trigger can build the stub
    Invite (CM-17-010, MV-10-001, #4165).

    TRIG-03-002: Unknown fields are silently ignored.
    """

    stub_summary: NonEmptyString
