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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""Provides a Record model for document database storage.

Grouped by concern (CS-18-005):

- ``record`` — the :class:`Record` model and its object conversions
- ``codec`` — dehydrate a model's data on write, retype inline snapshots on read
- ``ref_fields`` — which fields hold object references and which stay inline
"""

from vultron.adapters.driven.db_record.codec import (
    STORED_ROW_CONTEXT,
)
from vultron.adapters.driven.db_record.record import (
    Record,
    main,
    object_to_record,
    record_to_object,
)
from vultron.adapters.driven.db_record.ref_fields import (
    # Private, but imported by trigger_activity_adapter/_base.py, which open
    # PR #5815 is restructuring; repoint that import once it merges.
    _AS_LIST_REF_FIELDS,
    object_ref_fields,
)

__all__ = [
    "Record",
    "STORED_ROW_CONTEXT",
    "main",
    "object_ref_fields",
    "object_to_record",
    "record_to_object",
]
