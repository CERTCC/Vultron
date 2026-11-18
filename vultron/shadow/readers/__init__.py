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

"""The case shadow tool's case readers, and which one a run reads through.

* :class:`~vultron.shadow.readers.vultron_ledger.VultronCaseReader` — reads
  a Vultron case-ledger JSONL file, untranslated.
* :class:`~vultron.shadow.readers.vultron_node.VultronNodeCaseReader` — the
  live Vultron case reader: a running node's case ledger, untranslated,
  read once or followed as it grows.
* :class:`~vultron.shadow.readers.following.CaseFollower` — a reader that
  can follow a case, which the dashboard follows instead of reading once;
  the shadow tool's own, not a core port.
* :func:`~vultron.shadow.readers.event_stream.server_sent_events` — the
  events of a node's ledger event stream, read from its lines.
* :func:`~vultron.shadow.readers.ledger_reading.ledger_reading` — the case
  reading both Vultron readers build from a ledger's parsed rows.
* :class:`~vultron.shadow.readers.selection.CaseSource` — the sources the
  analyst picks from on the page: the recorded demo cases, an outside
  system, or a running Vultron node.
* :func:`~vultron.shadow.readers.selection.select_case_reader` — the reader
  a source reads through.
* :func:`~vultron.shadow.readers.configured.configured_case_reader` — that
  reader set up from the run's ``shadow:`` settings, with
  :func:`~vultron.shadow.readers.configured.typed_node` checking a node the
  analyst typed and
  :func:`~vultron.shadow.readers.configured.outside_source_ready` saying
  whether the outside system can be chosen.
"""

from vultron.shadow.readers.configured import (
    configured_case_reader,
    configured_node,
    outside_connector,
    outside_source_ready,
    typed_node,
)
from vultron.shadow.readers.selection import (
    CaseSource,
    VultronNode,
    select_case_reader,
)
from vultron.shadow.readers.vultron_ledger import VultronCaseReader
from vultron.shadow.readers.vultron_node import VultronNodeCaseReader

__all__ = [
    "CaseSource",
    "VultronCaseReader",
    "VultronNode",
    "VultronNodeCaseReader",
    "configured_case_reader",
    "configured_node",
    "outside_connector",
    "outside_source_ready",
    "select_case_reader",
    "typed_node",
]
