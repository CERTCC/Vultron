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
Backward-compatible re-export of ``TinyDbDataLayer``, ``get_datalayer``, and
``reset_datalayer``.

The authoritative implementation lives in
``vultron.adapters.driven.activity_store``.  New code should import from
there directly.  This shim will be removed once all callers are updated
(see plan task P70-5).
"""

from vultron.adapters.driven.datalayer_tinydb import (
    TinyDbDataLayer,
    get_datalayer,
    reset_datalayer,
)

__all__ = ["TinyDbDataLayer", "get_datalayer", "reset_datalayer"]
