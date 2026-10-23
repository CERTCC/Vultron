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
    attributed_to: NonEmptyString | None = None  # pyright: ignore[reportGeneralTypeIssues]
    # Each dimension serializes to its bare state value (ARCH-25-005, ADR-0099), so
    # the alias alone produces the flat wire shape the AS2 form has always used:
    # ``em`` -> ``{"emState": "NONE"}``.  Declared for the same reason
    # ``ParticipantStatus`` declares its own: the AS2 spelling of a core field
    # belongs in the field's alias and nowhere else (ARCH-25-002, ADR-0099),
    # which is also where core code that must key an AS2-shaped snapshot reads
    # it from (:mod:`vultron.core.models.wire_keys`).  Adding them here made
    # this class's own ``by_alias`` dump agree with the wire form that
    # ``as_CaseStatus`` — and therefore every replica — has always produced.
    #
    # Input accepts the wire spelling and the field name only.  The old flat
    # snake_case spellings (``em_state``, ``pxa_state``) are retired with their
    # shim properties (SDO-03-003): ``extra="forbid"`` refuses them on
    # in-process and stored data (SDO-03-005), and the parse edge refuses them
    # inbound as near misses of ``emState`` / ``pxaState`` (MV-11-002).
    em: EmDimension = Field(
        default_factory=EmDimension,
        validation_alias=AliasChoices("emState", "em"),
        serialization_alias="emState",
        frozen=True,
    )
    pxa: PxaDimension = Field(
        default_factory=PxaDimension,
        validation_alias=AliasChoices("pxaState", "pxa"),
        serialization_alias="pxaState",
    )

    # There is deliberately no ``_migrate_flat_fields`` before-validator and no
    # flat ``em_state`` / ``pxa_state`` view (SDO-03-003): the dimension owns
    # the state machine (ADR-0036, SDO-03-001), so readers use ``em.state`` and
    # ``pxa.state``.  ``_ScalarDimension``'s ``_accept_bare_state`` accepts the
    # bare state value the flat wire form carries.  ``em`` is a frozen field
    # and ``EmDimension`` a frozen model, so ``status.em = ...`` and
    # ``status.em.state = ...`` raise ``ValidationError`` (SDO-03-006,
    # EMB-18-001).  The owning ``VulnerabilityCase`` stamps the derived EM onto
    # a copy via :meth:`with_em` rather than mutating the status (ADR-0122).

    @model_validator(mode="after")
    def _set_name(self) -> "CaseStatus":
        """Derive the display ``name`` label from the dimension states.

        Mirrors ``as_CaseStatus.set_name`` exactly, and must keep mirroring it.
        ``ParticipantStatus._set_name`` appends ``case_status.name`` to its own
        label, so a core ``CaseStatus`` that left ``name`` unset silently
        shortened the enclosing participant status's label — making core and
        ``as_ParticipantStatus`` disagree on an AS2 property for the one input
        shape that sets ``case_status``, which is exactly the parity ARCH-25-005
        (ADR-0099) claims.  ``name`` reaches the wire through
        ``CaseLedgerEntry.payloadSnapshot``, so the disagreement is
        protocol-visible.

        Only set when the caller supplied none, so an explicit ``name`` wins.
        ``object.__setattr__`` avoids re-entering validation, since
        ``validate_assignment`` is in effect on the core branch (ARCH-21-001).
        """
        if self.name is None:
            object.__setattr__(self, "name", self._derived_name())
        return self

    def _derived_name(self) -> str:
        """The label :meth:`_set_name` derives from the current states."""
        return " ".join([self.em.state.name, self.pxa.state.name])

    def with_em(self, em: EM) -> "CaseStatus":
        """A copy of this status carrying *em*: the owning case's EM stamp.

        ``model_copy`` runs no validator, so a label derived from the old
        states would survive the copy and contradict its EM (#5124).  A
        derived label is derived again for the copy; an explicit one is
        kept, as :meth:`_set_name` keeps it.  The status itself is left as
        it was (ADR-0122).
        """
        relabel = self.name == self._derived_name()
        copy = self.model_copy(update={"em": EmDimension(state=em)})
        if relabel:
            object.__setattr__(copy, "name", copy._derived_name())
        return copy
