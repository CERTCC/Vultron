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

"""Shared helper utilities for core domain model types.

Grouped by concern (CS-18-005):

- ``clock`` — the one wall-clock read (``clock.datetime`` is the clock seam)
  and the pure ordered-stamp and deadline helpers that take the act's instant
- ``timestamps`` — the serialized timestamp form and claimed-time reading
- ``ids`` — the object id minter, its id source and scoped install, and the
  mixed-reference id reader ``_as_id``
- ``inbound`` — reading inbound and stored data: absent times, key spellings
- ``dump`` — the empty-collection test a dump omits a field by
- ``class_annotations`` — a class's own annotations, read without evaluating
  forward references
"""

# ``_as_id`` is re-exported although its name is private: it is this package's
# shared id reader, imported from ``vultron.core.models._helpers`` by modules in
# every layer, including ones other open changes own (CS-18-003).
from vultron.core.models._helpers.class_annotations import own_annotations
from vultron.core.models._helpers.clock import (
    AuthoredTimes,
    EmbargoAuthoredTimes,
    SteppingClock,
    authored_times,
    days_after,
    deadline_from,
    embargo_authored_times,
    is_aware,
    now_utc,
    require_aware,
    require_future_aware,
    stamp_after,
)
from vultron.core.models._helpers.dump import is_empty
from vultron.core.models._helpers.ids import (
    URN_UUID_PREFIX,
    IdSource,
    _as_id,
    install_id_source,
    new_object_id,
)
from vultron.core.models._helpers.inbound import (
    INBOUND_CONTEXT_KEY,
    STORED_CONTEXT_KEY,
    DuplicateKeySpellingError,
    MissingReceivedIdError,
    absent_times_as_none,
    blank_times_as_none,
    collapse_duplicate_spellings,
    project_wire_snapshot_to_core,
    reads_absent_as_none,
    refuse_absent_id,
    strip_annotated,
)
from vultron.core.models._helpers.timestamps import (
    MissingClaimedTimeError,
    as_utc,
    blank_as_none,
    format_timestamp,
    parse_published,
    refuse_absent_published,
    timestamp_serializer,
)

__all__ = [
    "reads_absent_as_none",
    "blank_as_none",
    "AuthoredTimes",
    "EmbargoAuthoredTimes",
    "authored_times",
    "embargo_authored_times",
    "DuplicateKeySpellingError",
    "INBOUND_CONTEXT_KEY",
    "IdSource",
    "MissingClaimedTimeError",
    "MissingReceivedIdError",
    "STORED_CONTEXT_KEY",
    "SteppingClock",
    "URN_UUID_PREFIX",
    "absent_times_as_none",
    "as_utc",
    "blank_times_as_none",
    "collapse_duplicate_spellings",
    "days_after",
    "deadline_from",
    "format_timestamp",
    "install_id_source",
    "is_aware",
    "is_empty",
    "own_annotations",
    "new_object_id",
    "now_utc",
    "parse_published",
    "project_wire_snapshot_to_core",
    "refuse_absent_id",
    "refuse_absent_published",
    "require_aware",
    "require_future_aware",
    "stamp_after",
    "strip_annotated",
    "timestamp_serializer",
]
