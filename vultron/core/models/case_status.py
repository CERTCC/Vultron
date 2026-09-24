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

"""Domain representation of a case status snapshot."""

from typing import Literal

from pydantic import AliasChoices, Field, model_validator

from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM


class CaseStatus(CoreObject):
    """Domain representation of a case status snapshot.

    Canonical core type for the Vultron ``CaseStatus`` object.
    ``type_`` is ``"CaseStatus"`` to match the wire value and
    to auto-register this class in :data:`CORE_VOCABULARY`.

    ``context`` (case ID) is required — a status snapshot without a case
    context is not meaningful.  ``attributed_to`` (reporting actor) is
    optional but must be non-empty when present.

    ``em`` and ``pxa`` are dimension objects that own the EM and PXA state
    machines respectively (ADR-0036, SDO-03-001).
    """

    type_: Literal["CaseStatus"] = Field(
        default="CaseStatus",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
    attributed_to: NonEmptyString | None = (
        None  # pyright: ignore[reportGeneralTypeIssues]
    )
    # Each dimension serializes to its bare state value (ADR-0099 detail 5), so
    # the alias alone produces the flat wire shape the AS2 form has always used:
    # ``em`` -> ``{"emState": "NONE"}``.  ``AliasChoices`` keeps the legacy flat
    # spellings accepted on input so no caller has to change.  Declared for the
    # same reason ``ParticipantStatus`` declares its own: the AS2 spelling of a
    # core field belongs in the field's alias and nowhere else (ADR-0099 detail
    # 2), which is also where core code that must key an AS2-shaped snapshot
    # reads it from (:mod:`vultron.core.models.wire_keys`).  Adding them here
    # made this class's own ``by_alias`` dump agree with the wire form that
    # ``as_CaseStatus`` — and therefore every replica — has always produced.
    em: EmDimension = Field(
        default_factory=EmDimension,
        validation_alias=AliasChoices("emState", "em_state", "em"),
        serialization_alias="emState",
    )
    pxa: PxaDimension = Field(
        default_factory=PxaDimension,
        validation_alias=AliasChoices("pxaState", "pxa_state", "pxa"),
        serialization_alias="pxaState",
    )

    # There is deliberately no ``_migrate_flat_fields`` before-validator any
    # more.  It hand-translated the flat ``em_state`` / ``emState`` spellings
    # into the nested ``{"state": ...}`` form, and was the only AS2 spelling in
    # this module outside an alias.  Both mechanisms ADR-0099 detail 5 introduced
    # now cover its whole job with nothing hand-written: the ``AliasChoices``
    # above accept all three spellings, and ``_ScalarDimension``'s
    # ``_accept_bare_state`` accepts the bare state value the flat form carries.

    # ``em_state``/``pxa_state`` are a read/write view onto the dimension, not a
    # second place to keep the value: the dimension owns the state machine
    # (ADR-0036, SDO-03-001) and the flat spelling is only how it serializes
    # (ADR-0099 detail 5).  They exist because the deleted ``as_CaseStatus``
    # carried ``em_state``/``pxa_state`` as real fields, so callers and tests
    # written against the wire class read *and assigned* them.
    #
    # The setters are what make that compatibility real.  Read-only properties
    # satisfied every reader and then failed on the first writer with
    # "property has no setter" — which is not a compatibility shim, just a
    # narrower break.

    @property
    def em_state(self) -> EM:
        """The EM state value. A view onto ``em.state``."""
        return self.em.state

    @em_state.setter
    def em_state(self, value: EM) -> None:
        self.em = EmDimension(state=value)

    @property
    def pxa_state(self) -> CS_pxa:
        """The PXA state value. A view onto ``pxa.state``."""
        return self.pxa.state

    @pxa_state.setter
    def pxa_state(self, value: CS_pxa) -> None:
        self.pxa = PxaDimension(state=value)

    @model_validator(mode="after")
    def _set_name(self) -> "CaseStatus":
        """Derive the display ``name`` label from the dimension states.

        Mirrors ``as_CaseStatus.set_name`` exactly, and must keep mirroring it.
        ``ParticipantStatus._set_name`` appends ``case_status.name`` to its own
        label, so a core ``CaseStatus`` that left ``name`` unset silently
        shortened the enclosing participant status's label — making core and
        ``as_ParticipantStatus`` disagree on an AS2 property for the one input
        shape that sets ``case_status``, which is exactly the parity ADR-0099
        detail 5 claims.  ``name`` reaches the wire through
        ``CaseLedgerEntry.payloadSnapshot``, so the disagreement is
        protocol-visible.

        Only set when the caller supplied none, so an explicit ``name`` wins.
        ``object.__setattr__`` avoids re-entering validation, since
        ``validate_assignment`` is in effect on the core branch (ARCH-21-001).
        """
        if self.name is None:
            object.__setattr__(
                self,
                "name",
                " ".join([self.em.state.name, self.pxa.state.name]),
            )
        return self
