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
"""Wire-layer AS2 activity classes for SYNC-2 log replication.

Provides :class:`AnnounceLogEntryActivity` used by the CaseActor to fan
out canonical log entries to participant actors.
"""

from typing import Optional, Union

from pydantic import Field

from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)
from vultron.wire.as2.vocab.objects.case_log_entry import (
    VultronCaseLogEntry,
)


class AnnounceLogEntryActivity(as_Announce):
    """The CaseActor is announcing a canonical CaseLogEntry for replication.

    Sent to each participant actor after a new log entry has been committed
    to the case event log (SYNC-09-002).

    object_: :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`
        being replicated.
    """

    object_: Optional[Union[VultronCaseLogEntry, as_Link, str]] = Field(  # type: ignore[assignment]
        default=None,
        validation_alias="object",
        serialization_alias="object",
    )
