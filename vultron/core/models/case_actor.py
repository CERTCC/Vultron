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

"""Domain representations for CaseActor and its outbox."""

from typing import Any

from pydantic import BaseModel, Field

from vultron.core.models.base import VultronObject


class VultronOutbox(BaseModel):
    """Minimal outbox representation for domain actor types."""

    items: list[str] = Field(default_factory=list)


class VultronCaseActor(VultronObject):
    """Domain representation of a CaseActor service.

    Mirrors the Vultron-specific fields of ``CaseActor`` (which inherits
    ``as_Service``).  The ``outbox`` field carries the actor's outgoing
    activity IDs and is required so that ``UpdateActorOutbox`` can append
    to it via ``save_to_datalayer``.
    ``as_type`` is ``"Service"`` to match ``CaseActor``'s wire value.
    """

    as_type: str = "Service"
    attributed_to: Any | None = None
    context: Any | None = None
    outbox: VultronOutbox = Field(default_factory=VultronOutbox)
