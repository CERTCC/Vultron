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

"""Abstract base classes for BT-backed trigger use cases.

Three-level hierarchy:

- :class:`SvcBTTriggerBase` — top-level template method that owns the
  ``__init__``, the TriggerActivityPort guard, BTBridge construction, BT
  execution, and the failure guard.  Generic in the :class:`TriggerResult`
  subtype its verb returns (UCORG-05-007).  Subclasses implement
  ``_prepare()``, ``_build_tree()``, ``_handle_result()`` and
  ``_build_result()``.

- :class:`SvcActivityTriggerBase` — binds the result to
  :class:`ActivityResult` and builds it from the captured activity and the
  emitting actor; the base of every verb whose body is
  ``{"activity", "emitting_actor_id"}``.

- :class:`SvcEmbargoTriggerBase` — extends ``SvcActivityTriggerBase`` with a
  concrete ``_handle_result()`` for the two role arms of an embargo trigger
  tree (EP-09-008): a non-manager's pending assertion is recorded, and a
  CASE_MANAGER's ``lifecycle_result`` is validated and handed to the
  per-operation ``_log_lifecycle_result()`` hook.

One class per submodule: :mod:`.bt`, :mod:`.activity`, :mod:`.embargo`.
"""

from .activity import SvcActivityTriggerBase
from .bt import SvcBTTriggerBase
from .embargo import SvcEmbargoTriggerBase

__all__ = [
    "SvcActivityTriggerBase",
    "SvcBTTriggerBase",
    "SvcEmbargoTriggerBase",
]
