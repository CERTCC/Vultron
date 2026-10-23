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

"""
Core trigger use-case classes.

Provides class-based domain use cases for actor-initiated behaviors.
No HTTP framework imports.  Raises domain exceptions
(``VultronNotFoundError``, ``VultronInvalidStateTransitionError``, ``VultronValidationError``)
that callers in the adapter layer should catch and translate.

Import trigger use-case classes directly from their submodules
(e.g. ``from vultron.core.use_cases.triggers.report import SvcValidateReportUseCase``).
The package-level re-exports were removed to avoid a circular import chain
introduced by the BT node layer importing ``triggers.sync``.
"""
