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

"""Backward compatibility shim for datalayer_sqlite.

This module has been split into focused submodules. All public APIs are
re-exported here for backward compatibility.

See vultron/adapters/driven/datalayer_sqlite/ for the implementation.
"""

# Re-export all public APIs from the subpackage
from vultron.adapters.driven.datalayer_sqlite import (  # noqa: F401
    SqliteDataLayer,
    VultronObjectRecord,
    QueueEntry,
    get_datalayer,
    get_shared_dl,
    get_all_actor_datalayers,
    reset_datalayer,
)

__all__ = [
    "SqliteDataLayer",
    "VultronObjectRecord",
    "QueueEntry",
    "get_datalayer",
    "get_shared_dl",
    "get_all_actor_datalayers",
    "reset_datalayer",
]
