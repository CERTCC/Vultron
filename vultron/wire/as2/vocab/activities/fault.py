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

"""Fault and refusal activity shapes (MSM-05-001)."""

from pydantic import Field

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Reject


class _RefusalNoticeActivity(as_Reject):
    """The CASE_MANAGER's refusal notice for an assertion a guard refused.

    Sent to the asserting participant alone when a precondition guard at the
    CASE_MANAGER refuses its assertion, so the participant learns the
    assertion had no effect (CLP-02-005, CLP-05-001, ADR-0141).  Nothing is
    ledgered for it (CLP-05-002).

    object_: The refused activity, inline.
    in_reply_to: The refused activity's id.
    summary: The refusing guard's reason.
    context: The case the refused activity concerns, when it names one.
    """

    object_: as_Activity = Field(
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )
    in_reply_to: NonEmptyString = Field(default=...)
    summary: NonEmptyString = Field(default=...)
