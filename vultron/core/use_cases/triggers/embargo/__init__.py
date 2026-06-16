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

"""Embargo trigger use-case package.

This package replaces the former ``triggers/embargo.py`` flat module with
one-module-per-use-case while preserving existing imports such as:

``from vultron.core.use_cases.triggers.embargo import SvcProposeEmbargoUseCase``.
"""

from vultron.core.use_cases.triggers._helpers import _is_case_owner
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)

from .accept import SvcAcceptEmbargoUseCase, SvcEvaluateEmbargoUseCase
from .propose import SvcProposeEmbargoUseCase
from .reject import SvcRejectEmbargoUseCase
from .revise import SvcProposeEmbargoRevisionUseCase
from .terminate import SvcTerminateEmbargoUseCase

__all__ = [
    "_is_case_owner",
    "AcceptEmbargoTriggerRequest",
    "ProposeEmbargoRevisionTriggerRequest",
    "ProposeEmbargoTriggerRequest",
    "RejectEmbargoTriggerRequest",
    "TerminateEmbargoTriggerRequest",
    "SvcAcceptEmbargoUseCase",
    "SvcEvaluateEmbargoUseCase",
    "SvcProposeEmbargoRevisionUseCase",
    "SvcProposeEmbargoUseCase",
    "SvcRejectEmbargoUseCase",
    "SvcTerminateEmbargoUseCase",
]
