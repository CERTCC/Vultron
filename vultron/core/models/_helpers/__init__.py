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
- ``timestamps`` — the serialized timestamp form and claimed-time reading
- ``ids`` — the object id minter, its id source and scoped install, and the
  mixed-reference id reader ``_as_id``
- ``inbound`` — reading inbound and stored data: absent times, key spellings
"""

# ``_as_id`` is re-exported although its name is private: it is this package's
# shared id reader, imported from ``vultron.core.models._helpers`` by modules in
# every layer, including ones other open changes own (CS-18-003).
from vultron.core.models._helpers.clock import (
    SteppingClock,
    days_from_now_utc,
    from_now_utc,
    now_utc,
    now_utc_after,
    require_future_aware,
)
from vultron.core.models._helpers.ids import (
    URN_UUID_PREFIX,
    IdSource,
    _as_id,
    install_id_source,
    new_object_id,
    system_id_source,
)
from vultron.core.models._helpers.inbound import (
    INBOUND_CONTEXT_KEY,
    STORED_CONTEXT_KEY,
    DuplicateKeySpellingError,
    absent_times_as_none,
    blank_times_as_none,
    collapse_duplicate_spellings,
    project_wire_snapshot_to_core,
    strip_annotated,
)
from vultron.core.models._helpers.timestamps import (
    MissingClaimedTimeError,
    as_utc,
    claimed_published_iso,
    format_timestamp,
    parse_published,
    refuse_absent_published,
    timestamp_serializer,
)

__all__ = [
    "DuplicateKeySpellingError",
    "INBOUND_CONTEXT_KEY",
    "IdSource",
    "MissingClaimedTimeError",
    "STORED_CONTEXT_KEY",
    "SteppingClock",
    "URN_UUID_PREFIX",
    "absent_times_as_none",
    "as_utc",
    "blank_times_as_none",
    "claimed_published_iso",
    "collapse_duplicate_spellings",
    "days_from_now_utc",
    "format_timestamp",
    "from_now_utc",
    "install_id_source",
    "new_object_id",
    "now_utc",
    "now_utc_after",
    "parse_published",
    "project_wire_snapshot_to_core",
    "refuse_absent_published",
    "require_future_aware",
    "strip_annotated",
    "system_id_source",
    "timestamp_serializer",
]
