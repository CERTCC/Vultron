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

"""Domain representations of AS2 activity types used in the core layer."""

from typing import Any, Literal

from pydantic import Field

from vultron.core.models.base import NonEmptyString, VultronObject


class VultronActivity(VultronObject):
    """Domain representation of an AS2 activity for DataLayer storage.

    ``VultronActivity`` is the domain model for an inbound or outbound AS2
    activity object. It is distinct from ``VultronEvent`` (defined in
    ``vultron.core.models.events``), which is the semantic dispatch event
    that carries decomposed ID/type fields extracted from the wire format.
    A ``VultronEvent`` may carry a ``VultronActivity`` as its ``activity``
    field, but the two types serve different purposes: ``VultronActivity``
    persists activity records in the DataLayer, while ``VultronEvent`` drives
    handler dispatch in the core.

    ``as_type`` is required and must be set to the actual activity type
    (e.g. ``"Offer"``, ``"Accept"``, ``"Invite"``, ``"Leave"``, ``"Read"``).

    Field names match the wire-layer ``as_Activity`` internal names so that
    a stored ``VultronActivity`` can be round-tripped through
    ``record_to_object`` and deserialized as the appropriate AS2 activity
    subclass.  ``as_object`` uses alias ``"object"`` to match the AS2 wire
    field name; callers may pass either ``as_object=`` or ``object=`` thanks
    to ``populate_by_name=True`` on ``VultronBase``.
    """

    as_type: NonEmptyString = Field(alias="type")
    actor: NonEmptyString  # non-optional because every activity must have an actor
    as_object: Any | None = Field(default=None, alias="object")
    target: NonEmptyString | None = None
    origin: NonEmptyString | None = None
    to: list[str] | None = None
    cc: list[str] | None = None


class VultronOffer(VultronActivity):
    """Domain representation of an Offer activity.

    Mirrors the essential fields of ``as_Offer``.
    ``as_type`` is ``"Offer"`` to match the wire value.
    """

    as_type: Literal["Offer"] = "Offer"


class VultronAccept(VultronActivity):
    """Domain representation of an Accept activity.

    Mirrors the essential fields of ``as_Accept``.
    ``as_type`` is ``"Accept"`` to match the wire value.
    """

    as_type: Literal["Accept"] = "Accept"


class VultronCreateCaseActivity(VultronActivity):
    """Domain representation of a Create(Case) activity.

    Mirrors the essential fields of ``as_CreateCase``.
    ``as_type`` is ``"Create"`` to match the wire value.
    """

    as_type: Literal["Create"] = "Create"
