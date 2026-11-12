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
"""The case event history: a case ledger as labeled, timestamped CVD events (CEH-03, CEH-04).

Read through :mod:`vultron.measure.ledger`, never beside it:

* :mod:`~vultron.measure.history.model` — the event record, its closed kind
  and gap enumerations, and the history that carries the ledger's holes.
* :mod:`~vultron.measure.history.snapshot` — the state-bearing records of one
  payload snapshot, recommendations and offers left out (CEH-04-014).
* :mod:`~vultron.measure.history.derive` — the derivation:
  :func:`case_event_history` for one selected case ledger, and
  :func:`read_case_event_histories` for the files a caller names.
* :mod:`~vultron.measure.history.render` — the history as JSON or as a
  friendly-named Markdown table (:func:`case_history_report`, CEH-01-005).
* :mod:`~vultron.measure.history.cli` — the ``vultron-case-history``
  command over it (CEH-01-004).
"""

from vultron.measure.history.derive import (
    case_event_history,
    read_case_event_histories,
)
from vultron.measure.history.model import (
    CASE_KINDS,
    RM_EVENT_KINDS,
    CaseEvent,
    CaseEventHistories,
    CaseEventHistory,
    CaseEventKind,
    EventKind,
    EventScope,
    ExcludedState,
    GapLabel,
    UnreadableEntry,
    scope_of,
)
from vultron.measure.history.render import (
    HistoryFormat,
    case_history_report,
)

__all__ = [
    "CASE_KINDS",
    "RM_EVENT_KINDS",
    "CaseEvent",
    "CaseEventHistories",
    "CaseEventHistory",
    "CaseEventKind",
    "EventKind",
    "EventScope",
    "ExcludedState",
    "GapLabel",
    "HistoryFormat",
    "UnreadableEntry",
    "case_event_history",
    "case_history_report",
    "read_case_event_histories",
    "scope_of",
]
