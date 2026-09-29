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

"""Domain representation of an EmbargoEvent."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import now_utc
from vultron.core.models.base import CoreObject, NonEmptyString


class EmbargoEvent(CoreObject):
    """Domain representation of an EmbargoEvent.

    Canonical core type for the Vultron ``EmbargoEvent`` object.
    ``type_`` is ``"EmbargoEvent"`` to match the wire vocabulary key, enabling
    proper DataLayer round-trips via ``dl.read()`` and ``dl.list_objects()``,
    and to auto-register this class in :data:`CORE_VOCABULARY`.
    """

    type_: Literal["EmbargoEvent"] = Field(
        default="EmbargoEvent",
        validation_alias="type",
        serialization_alias="type",
    )
    # Optional: a received embargo carries the sender's start, which may be
    # absent (ISSUE-3257).  Nothing decides on it — ``end_time`` is the time
    # embargo decisions read, and it is required with no default: the only
    # fallback duration in the system is the protocol default resolved at case
    # creation (EP-04-005, EP-04-010, #3404), so every construction site states
    # the end it means.  Both fields are read as UTC by ``CoreObject`` (#3784).
    start_time: datetime | None = Field(default_factory=now_utc)
    end_time: datetime  # pyright: ignore[reportGeneralTypeIssues]
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]

    def with_subject(self, subject_id: str) -> "EmbargoEvent":
        """Return this embargo re-scoped to *subject_id*, identity kept.

        The rewrite EP-04-004 prescribes at case creation: the Reporter's
        proposed terms name the report until a case exists, then the case.
        Everything else — id, times, the sender's name — is carried as it was,
        and the copy goes through validation rather than around it.
        """
        # Field-name spelling on purpose: core never produces the wire shape
        # itself (ARCH-20-001), and ``populate_by_name`` accepts this dump.
        data = {**self.model_dump(), "context": subject_id}
        if self.name == self._derived_name():
            # The label ``_set_name`` derived for the old subject is not a name
            # the sender chose; drop it so the copy is labelled by the new one.
            data.pop("name")
        return type(self).model_validate(data)

    def _derived_name(self) -> str:
        """The label ``_set_name`` gives an unnamed embargo: subject and window."""
        parts = ["Embargo for", self.context]
        if self.start_time:
            parts.append(f"start: {self.start_time.isoformat()}")
        parts.append(f"end: {self.end_time.isoformat()}")
        return " ".join(parts)

    @model_validator(mode="after")
    def _set_name(self) -> "EmbargoEvent":
        """Label the embargo by its case and window when it carries no name.

        The derivation the deleted ``as_EmbargoEvent.set_name`` performed,
        relocated here because this class is now its own wire class (ADR-0099
        detail 3).  Activity labels compose the object's name, and the name
        reaches peers in the ledger payload snapshot, so dropping it changed the
        wire.  A name the object already carries is kept: it is the sender's.
        """
        if self.name is not None:
            return self
        object.__setattr__(self, "name", self._derived_name())
        return self
