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

"""Row ↔ domain-object conversion for the SQLite DataLayer.

One responsibility: turning a :class:`~.schema.VultronObjectRecord` into the
most precise domain object the registries can name, and back.  Nothing here
opens a session or issues SQL — the callers in :mod:`.crud` and :mod:`.queries`
own that, and hand rows in.

Split out of ``datalayer.py`` (CS-18-002): that module had grown to two
unrelated jobs, this pipeline and a thin delegating façade over the other
submodules.  The functions take the DataLayer as their first argument, the same
shape :mod:`.crud`, :mod:`.queries` and :mod:`.queues` already use, so
``SqliteDataLayer``'s methods stay one-line delegations and every existing
``dl._from_row(row)`` call site keeps working.

The pipeline is a package grouped by concern (CS-18-005):

- ``rows`` — the entry points, :func:`to_row` and :func:`from_row`
- ``row_types`` — which class a stored row's type names
- ``coercion`` — reference hydration and semantic coercion
- ``fields`` — which classes a declared field admits
"""

from vultron.adapters.driven.datalayer_sqlite.hydration.coercion import (
    coerce_to_semantic_class,
    hydrate,
    object_from_storage,
    rehydrate_fields,
)
from vultron.adapters.driven.datalayer_sqlite.hydration.fields import (
    class_field_admits_object,
    field_admits_object,
)
from vultron.adapters.driven.datalayer_sqlite.hydration.row_types import (
    WIRE_ROW_FAILURES,
    core_class_for_row_type,
    project_wire_row_to_core,
    wire_object_from_row,
)
from vultron.adapters.driven.datalayer_sqlite.hydration.rows import (
    from_row,
    to_row,
)

__all__ = [
    "WIRE_ROW_FAILURES",
    "class_field_admits_object",
    "coerce_to_semantic_class",
    "core_class_for_row_type",
    "field_admits_object",
    "from_row",
    "hydrate",
    "object_from_storage",
    "project_wire_row_to_core",
    "rehydrate_fields",
    "to_row",
    "wire_object_from_row",
]
