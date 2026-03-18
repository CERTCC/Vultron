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

from typing import Any

from vultron.core.models.base import VultronObject


class VultronActivity(VultronObject):
    """Domain representation of an AS2 activity for DataLayer storage.

    ``as_type`` is required and must be set to the actual activity type
    (e.g. ``"Offer"``, ``"Accept"``, ``"Invite"``, ``"Leave"``, ``"Read"``).

    Field names match the wire-layer ``as_Activity`` internal names so that
    a stored ``VultronActivity`` can be round-tripped through
    ``record_to_object`` and deserialized as the appropriate AS2 activity
    subclass.
    """

    actor: str | None = None
    as_object: str | None = None
    target: str | None = None
    origin: str | None = None
    context: str | None = None
    in_reply_to: str | None = None


class VultronOffer(VultronObject):
    """Domain representation of an Offer activity.

    Mirrors the essential fields of ``as_Offer``.
    ``as_type`` is ``"Offer"`` to match the wire value.
    """

    as_type: str = "Offer"
    actor: str | None = None
    object: Any | None = None
    to: Any | None = None
    target: Any | None = None


class VultronAccept(VultronObject):
    """Domain representation of an Accept activity.

    Mirrors the essential fields of ``as_Accept``.
    ``as_type`` is ``"Accept"`` to match the wire value.
    """

    as_type: str = "Accept"
    actor: str | None = None
    object: Any | None = None


class VultronCreateCaseActivity(VultronObject):
    """Domain representation of a Create(Case) activity.

    Mirrors the essential fields of ``as_CreateCase``.
    ``as_type`` is ``"Create"`` to match the wire value.
    """

    as_type: str = "Create"
    actor: str | None = None
    object: str | None = None
