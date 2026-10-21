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
"""Give a mock trigger-activity port the real ledger-record methods.

The CASE_MANAGER's own case-file changes are committed from the activities
the port's ``record_*`` methods build and seal (VM-08-003, #3743).  A test
that doubles the port with a ``MagicMock`` for the activities it *sends*
still needs those records built for real, or the commit has no snapshot:
:func:`with_ledger_records` routes them to a real adapter over *dl*.
"""

from unittest.mock import MagicMock

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence

#: Port methods that build a CASE_MANAGER record rather than a message.
LEDGER_RECORD_METHODS: tuple[str, ...] = (
    "record_case_created",
    "record_report_added_to_case",
    "record_participant_status_added",
    "record_case_status_added",
    "record_case_participant_created",
    "record_case_announced",
    # The CASE_MANAGER's own note, committed as ``add_note_to_case`` (#4829).
    "create_note",
    "add_note_to_case",
)


def with_ledger_records(
    port: MagicMock, dl: CaseOutboxPersistence
) -> MagicMock:
    """Route *port*'s ledger-record methods to a real adapter over *dl*."""
    real = TriggerActivityAdapter(dl)
    for name in LEDGER_RECORD_METHODS:
        getattr(port, name).side_effect = getattr(real, name)
    return port
