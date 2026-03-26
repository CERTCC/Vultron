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

from vultron.core.models.base import NonEmptyString, VultronObject


class VultronEmbargoEvent(VultronObject):
    """Domain representation of an EmbargoEvent.

    ``as_type`` is ``"Event"`` to match the wire value (EmbargoEvent inherits
    as_Event and does not override as_type).
    """

    as_type: str = "Event"
    end_time: datetime  # pyright: ignore[reportGeneralTypeIssues]
    context: NonEmptyString  # pyright: ignore[reportGeneralTypeIssues]
