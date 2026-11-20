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
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    PropertyValueKind,
    vultron_property,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import EmbargoRegisterStatus

_S = EmbargoRegisterStatus

#: Statuses an embargo reaches only by having been ``ACTIVE``.
_WAS_ACTIVE = frozenset({_S.ACTIVE, _S.SUPERSEDED, _S.TERMINATED})


class EmbargoEvent(CoreObject):
    """Domain representation of an EmbargoEvent.

    Canonical core type for the Vultron ``EmbargoEvent`` object.
    ``type_`` is ``"EmbargoEvent"`` to match the wire vocabulary key, enabling
    proper DataLayer round-trips via ``dl.read()`` and ``dl.list_objects()``,
    and to auto-register this class in :data:`CORE_VOCABULARY`.

    Beyond its terms, an embargo stores its own state (ADR-0202): its
    ``status`` in its case's register (ADR-0122's statuses; every embargo
    starts ``PROPOSED``), the embargo an activated revision ``replaces``, and
    how it ended once ``TERMINATED`` (``termination``).  A case's
    ``embargo_register`` is its ordered list of embargoes, and only a
    register step (:func:`~vultron.core.models.embargo_register.apply_register_step`)
    changes these three fields.

    A Vultron extension type and a subtype of AS2 ``Event`` (ADR-0201): its
    AS2 dump writes ``"type": ["EmbargoEvent", "Event"]`` (VM-03-005), so a
    generic AS2 reader sees an event, and a receiver reads the list back as
    this class (VM-03-006).
    """

    _as2_core_supertype_term: ClassVar[str | None] = "Event"

    # Every author states it (ADR-0176), and a receiver refuses a received
    # one without it (CLP-15-011).
    published: datetime

    type_: Literal["EmbargoEvent"] = Field(
        default="EmbargoEvent",
        validation_alias="type",
        serialization_alias="type",
    )
    # Optional: a received embargo carries the sender's start, which may be
    # absent (ISSUE-3257).  Nothing decides on it — ``end_time`` is the time
    # embargo decisions read, and it is required with no default: the only
    # fallback duration in the system is the protocol default resolved at case
    # creation (EP-04-019, EP-04-023, #3404), so every construction site states
    # the end it means.  Both fields are read as UTC by ``CoreObject`` (#3784).
    start_time: datetime | None  # pyright: ignore[reportGeneralTypeIssues]
    end_time: datetime  # pyright: ignore[reportGeneralTypeIssues]
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    status: EmbargoRegisterStatus = Field(
        default=_S.PROPOSED,
        json_schema_extra=vultron_property(
            (
                "The status of an embargo in its case's embargo register, "
                "such as PROPOSED, ACTIVE or TERMINATED"
            ),
            PropertyValueKind.PLAIN,
        ),
    )
    replaces: NonEmptyString | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            "The id of the embargo that an activated revision replaced",
            PropertyValueKind.IRI,
        ),
    )
    termination: EmbargoTermination | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            (
                "How a terminated embargo ended: its cause, END_TIME_REACHED "
                "included, the act that caused it when known, and a reason"
            ),
            PropertyValueKind.PLAIN,
        ),
    )

    def with_register_state(
        self,
        status: EmbargoRegisterStatus = _S.PROPOSED,
        *,
        replaces: str | None = None,
        termination: EmbargoTermination | None = None,
    ) -> EmbargoEvent:
        """Return this embargo holding the register state given, terms kept.

        With no arguments, the embargo's terms alone, as proposed.  The copy
        goes through validation, so a state no embargo may hold is refused
        (ADR-0202).
        """
        return type(self).model_validate(
            {
                **self.model_dump(),
                "status": status,
                "replaces": replaces,
                "termination": termination,
            }
        )

    def with_subject(self, subject_id: str) -> EmbargoEvent:
        """Return this embargo re-scoped to *subject_id*, identity kept.

        The rewrite EP-04-017 prescribes at case creation: the Reporter's
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
    def _status_fields_agree(self) -> EmbargoEvent:
        """Refuse a ``replaces`` or ``termination`` the status cannot carry."""
        problems: list[str] = []
        if (self.termination is None) == (self.status == _S.TERMINATED):
            problems.append(
                "a termination is required on a TERMINATED embargo and"
                " refused otherwise"
            )
        if self.replaces is not None and self.status not in _WAS_ACTIVE:
            problems.append(
                f"replaces is set on a {self.status} embargo, which was never"
                " activated"
            )
        if self.replaces is not None and self.replaces == self.id_:
            problems.append("an embargo cannot replace itself")
        if problems:
            raise ValueError(f"Embargo '{self.id_}': " + "; ".join(problems))
        return self

    @model_validator(mode="after")
    def _set_name(self) -> EmbargoEvent:
        """Label the embargo by its case and window when it carries no name.

        The derivation the deleted ``as_EmbargoEvent.set_name`` performed,
        relocated here because this class is now its own wire class (ARCH-25-003,
        ADR-0099).  Activity labels compose the object's name, and the name
        reaches peers in the ledger payload snapshot, so dropping it changed the
        wire.  A name the object already carries is kept: it is the sender's.
        """
        if self.name is not None:
            return self
        object.__setattr__(self, "name", self._derived_name())
        return self
