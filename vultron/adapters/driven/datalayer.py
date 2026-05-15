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

"""DataLayer facade — single import point for all callers.

Re-exports the active DataLayer implementation so that callers only need to
import from this module::

    from vultron.adapters.driven.datalayer import get_datalayer

Switching the backend only requires updating the import below.
"""

from vultron.adapters.driven.datalayer_sqlite import (  # noqa: F401
    SqliteDataLayer as DataLayerImpl,
    get_all_actor_datalayers,
    get_datalayer,
    get_shared_dl,
    reset_datalayer,
)
