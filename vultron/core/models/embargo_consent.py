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

"""One participant's consent to one embargo.

Consent is per (participant, embargo) (ADR-0122, CM-10-001, CM-18-001): a
:class:`CaseParticipant` carries one :class:`EmbargoConsent` row for each
entry in the case's embargo register, and nothing else records consent.  The
rows live on the participant record; the case's consent table is the union of
its participants' rows.  Being bound by the embargo in force, and having lapsed
from a replaced one, are lookups over the rows — see
:meth:`CaseParticipant.is_signatory` and :meth:`CaseParticipant.has_lapsed`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import as_utc
from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)


class EmbargoConsent(ValidatedAssignmentMixin, BaseModel):
    """A participant's answer to one embargo: the row of the consent table.

    ``rsvp_deadline`` belongs to the invitation the row is waiting on
    (CM-28-001, CM-28-012): it is set only on an ``INVITED`` row, from that
    Invite's ``end_time``, and the row drops it when it leaves ``INVITED``.
    Keeping it on the row lets one participant hold concurrent invitations
    with different deadlines.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    embargo_id: NonEmptyString
    state: EmbargoConsentState
    rsvp_deadline: datetime | None = None

    @field_validator("rsvp_deadline", mode="after")
    @classmethod
    def _deadline_is_utc(cls, value: datetime | None) -> datetime | None:
        """Read a naive deadline as UTC (CM-28-006, CS-13-001)."""
        return as_utc(value)

    @model_validator(mode="after")
    def _deadline_only_while_invited(self) -> "EmbargoConsent":
        """Refuse a deadline on a row that is not waiting on an invitation."""
        if (
            self.rsvp_deadline is not None
            and self.state != EmbargoConsentState.INVITED
        ):
            raise ValueError(
                f"Consent row for embargo '{self.embargo_id}' is"
                f" {self.state}; only an INVITED row carries an RSVP deadline"
                " (CM-28-013)."
            )
        return self
