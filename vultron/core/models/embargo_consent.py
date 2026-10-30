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

A row is an AS2 object (``type`` ``EmbargoConsent``) so that the CASE_MANAGER
can commit each changed row as its own ledger entry, a ``Create`` or
``Update`` carrying the row in full, and every replica copies it (ADR-0122,
ADR-0124, CLP-07-009, CLP-07-013).  ``attributedTo`` names the participant
actor whose consent it is, and the id is derived from that actor and the
embargo, so the same row has the same id on every node and nothing mints one.
A row carries no ``published`` or ``updated`` time: building one reads no
clock (CM-23-016).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from vultron.core.models._helpers import as_utc
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.wire_keys import first_input, wire_key
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)


class EmbargoConsent(CoreObject):
    """A participant's answer to one embargo: the row of the consent table.

    ``attributed_to`` is the participant actor whose consent the row records.
    A row built before it is seated on a participant record may leave it
    unset; :class:`CaseParticipant` stamps its own actor on every row it
    holds, and a row committed to the ledger on its own must name it.

    ``rsvp_deadline`` belongs to the invitation the row is waiting on
    (CM-28-001, CM-28-012): it is set only on an ``INVITED`` row, from that
    Invite's ``end_time``, and the row drops it when it leaves ``INVITED``.
    Keeping it on the row lets one participant hold concurrent invitations
    with different deadlines.
    """

    type_: Literal["EmbargoConsent"] = Field(
        default="EmbargoConsent",
        validation_alias="type",
        serialization_alias="type",
    )
    embargo_id: NonEmptyString
    state: EmbargoConsentState
    rsvp_deadline: datetime | None = None
    # A row is copied, never stamped: no clock is read to build one.
    published: datetime | None = None
    updated: datetime | None = None

    @classmethod
    def build_id(cls, embargo_id: str, actor_id: str | None) -> str:
        """The row's id: derived from its embargo and its participant actor."""
        return derived_activity_id(
            "embargo-consent", actor_id or "", embargo_id
        )

    @model_validator(mode="before")
    @classmethod
    def _derive_id(cls, data: Any) -> Any:
        """Give a row with no id the one its embargo and actor derive.

        A row that carries an id keeps it: a copy writes the id its entry
        carries (CM-23-016).
        """
        if not isinstance(data, dict) or (
            first_input(data, cls, "id_") is not None
        ):
            return data
        embargo_id = first_input(data, cls, "embargo_id")
        if embargo_id is None:
            return data  # the missing embargo_id is reported by its field
        return {
            **data,
            wire_key("id_", cls): cls.build_id(
                embargo_id, first_input(data, cls, "attributed_to")
            ),
        }

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

    def for_actor(self, actor_id: str) -> "EmbargoConsent":
        """This row attributed to *actor_id*, under the id that derives.

        For the participant record that seats the row: a row with no
        ``attributed_to`` takes its participant's actor.

        Raises:
            ValueError: the row is attributed to another actor.
        """
        if self.attributed_to == actor_id:
            return self
        if self.attributed_to is not None:
            raise ValueError(
                f"Consent row for embargo '{self.embargo_id}' is attributed"
                f" to '{self.attributed_to}', not '{actor_id}'."
            )
        data = self.model_dump(exclude={"id_"})
        return EmbargoConsent.model_validate(
            {**data, "attributed_to": actor_id}
        )
