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

"""Core trigger requests for the embargo verbs."""

from vultron.core.models.use_case_result import (
    ActivityResult,
)
from vultron.core.use_cases.triggers.request_bodies import (
    AcceptEmbargoRequest,
    ProposeEmbargoRequest,
    ProposeEmbargoRevisionRequest,
    RejectEmbargoRequest,
    TerminateEmbargoRequest,
    WithdrawEmbargoRequest,
)
from vultron.core.use_cases.triggers.requests._base import TriggerRequest


class ProposeEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], ProposeEmbargoRequest
):
    pass


class AcceptEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], AcceptEmbargoRequest
):
    pass


class RejectEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], RejectEmbargoRequest
):
    pass


class ProposeEmbargoRevisionTriggerRequest(
    TriggerRequest[ActivityResult], ProposeEmbargoRevisionRequest
):
    pass


class TerminateEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], TerminateEmbargoRequest
):
    pass


class WithdrawEmbargoTriggerRequest(
    TriggerRequest[ActivityResult], WithdrawEmbargoRequest
):
    """Trigger request for a signatory to send Leave(EmbargoEvent) (EP-09-013)."""
