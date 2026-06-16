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

"""Shared constants and base class for TriggerActivityAdapter submodules."""

from typing import Any

from vultron.core.ports.case_persistence import CaseOutboxPersistence

_DUMP_KWARGS: dict[str, Any] = {"by_alias": True, "exclude_none": True}


class _TriggerAdapterBase:
    """Base class providing DataLayer access to trigger adapter mixins.

    Args:
        dl: The DataLayer for reading persisted objects and creating
            activities.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl
