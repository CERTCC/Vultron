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

"""Domain representation of a case event log entry."""

from datetime import datetime

from pydantic import BaseModel, Field

from vultron.core.models._helpers import _now_utc


class VultronCaseEvent(BaseModel):
    """Domain representation of a case event log entry.

    Mirrors ``CaseEvent`` from ``vultron.wire.as2.vocab.objects.case_event``
    using identical field names for DataLayer round-trip compatibility.
    """

    object_id: str
    event_type: str
    received_at: datetime = Field(default_factory=_now_utc)
