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

"""Base class for Vultron Protocol core domain object models.

Grouped by concern (CS-18-005):

- ``context`` — the Vultron JSON-LD ``@context`` and Vultron-property marker
- ``record`` — the record root :class:`CoreRecord` and the assignment mixin
- ``core_object`` — the AS2 object root :class:`CoreObject`
- ``_computed`` — the computed-field contract (ARCH-23-005)
"""

from vultron.core.models.base.context import (
    VULTRON_CONTEXT_URI,
    VULTRON_PROPERTY_EXTRA,
    VULTRON_PROPERTY_KEY,
    JsonLdContext,
)
from vultron.core.models.base.core_object import (
    CoreObject,
)
from vultron.core.models.base.record import (
    CoreRecord,
    ValidatedAssignmentMixin,
    with_record_id,
)
from vultron.primitives import NonEmptyString, UriString

__all__ = [
    "CoreObject",
    "CoreRecord",
    "JsonLdContext",
    "NonEmptyString",
    "VULTRON_CONTEXT_URI",
    "VULTRON_PROPERTY_EXTRA",
    "UriString",
    "VULTRON_PROPERTY_KEY",
    "ValidatedAssignmentMixin",
    "with_record_id",
]
