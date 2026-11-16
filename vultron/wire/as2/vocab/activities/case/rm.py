#!/usr/bin/env python
# pyright: reportGeneralTypeIssues=false
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""RM case activities: engage, defer and close a case."""

from pydantic import Field

from vultron.wire.as2.vocab.activities.case.named_case import NamedCase
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Ignore,
    as_Join,
    as_Leave,
)

#####
# Custom Activity Streams Activities specific to the Vultron Protocol
#####


# join a case
class _RmEngageCaseActivity(as_Join):
    """The actor is has joined (i.e., is actively working on) a case.
    This represents the Vultron Message Type RA, and indicates that the actor is now in the RM.ACCEPTED state.
    object_: the case, by typed reference (ADR-0165)
    """

    object_: NamedCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RmDeferCaseActivity(as_Ignore):
    """The actor is deferring a case.
    This implies that the actor is no longer actively working on the case.
    Deferring a case does not imply that the actor is abandoning the case entirely,
    it just means that the actor is no longer actively working on it.
    This represents the Vultron Message Type RD, and indicates that the actor is now in the RM.DEFERRED state.
    Contrast with _RmCloseCaseActivity, which indicates that the actor is abandoning the case entirely.
    object_: the case, by typed reference (ADR-0165)
    """

    object_: NamedCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RmCloseCaseActivity(as_Leave):
    """The actor is ending their participation in the case and closing their local copy of the case.
    This corresponds to the Vultron RC message type.
    Case closure is considered a permanent Leave from the case.
    If the case owner (attributedTo) is the actor, then the case is closed for all participants.
    If the actor is not the case owner, then the actor should be removed from the case participants.
    object_: the case, by typed reference (ADR-0165)
    """

    object_: NamedCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
