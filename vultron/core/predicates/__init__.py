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

"""Pure predicate functions over core domain objects.

Sub-modules
-----------
- :mod:`~vultron.core.predicates.participants` — predicates over
  :class:`~vultron.core.models.case_participant.CaseParticipant` lists
  (e.g. convergence checks).
- :mod:`~vultron.core.predicates.roles` — role-membership and role-gated
  state-invariant predicates (AC-1, AC-3 of ISSUE-3058).
- :mod:`~vultron.core.predicates.embargo` — embargo-eligibility predicates
  (AC-2 of ISSUE-3058).

Import constraints
------------------
All modules in this package MUST remain free of I/O, DataLayer, and
framework imports.  They MAY import from ``vultron.core.states`` and
``vultron.enums`` but MUST NOT import from ``vultron.core.behaviors``,
``vultron.core.use_cases``, or ``vultron.core.services``.
"""
