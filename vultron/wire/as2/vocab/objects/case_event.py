#!/usr/bin/env python
"""
Re-exports CaseEvent from the core domain layer.

CaseEvent has been migrated to ``vultron.core.models.case_event`` (step 6
of issue #699).  This module re-exports it for backward compatibility so
existing ``from vultron.wire.as2.vocab.objects.case_event import CaseEvent``
imports continue to work unmodified.
"""

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

from vultron.core.models.case_event import CaseEvent  # noqa: F401

__all__ = ["CaseEvent"]
