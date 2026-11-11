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


"""Request bodies for the embargo trigger verbs."""

from datetime import datetime

from pydantic import field_validator, model_validator

from vultron.core.models._helpers import (
    require_aware,
    timestamp_serializer,
)
from vultron.core.models.base import NonEmptyString
from vultron.core.models.embargo_termination import (
    CASE_MANAGER_ONLY_CAUSE_KINDS,
    TerminationCause,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.triggers.request_bodies._base import (
    CaseTriggerRequest,
)


class ProposeEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the propose-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    TRIG-03-003: Optional note field may be included.
    end_time is required and must be timezone-aware and in the future: the
    body checks it is aware, the trigger that it is after its act's instant.
    """

    note: NonEmptyString | None = None
    end_time: datetime
    _serialize_end_time = timestamp_serializer("end_time")

    @field_validator("end_time")
    @classmethod
    def end_time_must_be_tz_aware(cls, v: datetime) -> datetime:
        # Whether it is in the future is the trigger's to judge, against its
        # act's instant (ADR-0176).
        return require_aware(v)


class AcceptEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the accept-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    Optional proposal_id identifies the specific EmProposeEmbargoActivity to accept:
    an open proposal, or the actor's received Invite for the embargo in force
    while its consent row for that embargo is INVITED or TIMED_OUT
    (EP-09-012).  If omitted, the earliest-expiring open proposal for the
    case is used (EP-08-002) — never the first recorded, and never the
    embargo in force.
    """

    proposal_id: NonEmptyString | None = None


class RejectEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the reject-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    Optional proposal_id identifies the specific EmProposeEmbargoActivity to reject:
    an open proposal, or the actor's received Invite for the embargo in force
    while its consent row for that embargo is INVITED or TIMED_OUT
    (EP-09-012).  If omitted, the earliest-expiring open proposal for the
    case is used (EP-08-002) — never the first recorded, and never the
    embargo in force.
    """

    proposal_id: NonEmptyString | None = None


class ProposeEmbargoRevisionRequest(ProposeEmbargoRequest):
    """
    Request body for the propose-embargo-revision trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    end_time is required and must be timezone-aware and in the future.
    Only valid when EM state is ACTIVE or REVISE; use propose-embargo for
    initial proposals.
    """


class TerminateEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the terminate-embargo trigger endpoint.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").

    ``reason`` is what ends the embargo (ADR-0122).  ``EARLY``, the default,
    is the actor's own decision to end it before its end time.
    ``END_TIME_REACHED`` is a request to end it at its end time, such as a
    Sentinel monitoring embargo timers sends: refused before the end time,
    and answered as already done, with no activity, once the embargo has
    ended.

    ``cause`` is why an ``EARLY`` termination ends the embargo (EMB-13-004):
    ``FIX_READY`` with its vendors, ``FIX_DEPLOYED`` or ``OTHER``.  An
    ``EARLY`` request with no cause is recorded as ``OTHER``.  A
    ``THREAT_SIGNAL`` cause is refused: a case status update setting ``P``,
    ``X`` or ``A`` is how a threat signal ends an embargo (EMB-13-005).  A
    cause on an ``END_TIME_REACHED`` request is refused too.
    """

    reason: TerminationReason = TerminationReason.EARLY
    cause: TerminationCause | None = None

    @model_validator(mode="after")
    def _cause_fits_request(self) -> "TerminateEmbargoRequest":
        """Refuse a cause this request may not name (EMB-13-004/005)."""
        if self.cause is None:
            return self
        if self.reason == TerminationReason.END_TIME_REACHED:
            raise ValueError(
                "an END_TIME_REACHED termination cannot have a cause"
                " (EMB-13-004)"
            )
        if self.cause.kind in CASE_MANAGER_ONLY_CAUSE_KINDS:
            raise ValueError(
                f"a terminate-embargo request cannot name a {self.cause.kind}"
                " cause: a case status update setting P, X or A is how a"
                " threat signal ends an embargo (EMB-13-005)"
            )
        return self


class WithdrawEmbargoRequest(CaseTriggerRequest):
    """
    Request body for the withdraw-embargo trigger endpoint (EP-09-013).

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    Names no Invite: the embargo withdrawn from is the case's embargo in
    force, which the actor must have agreed to (MSM-07-010).
    """
