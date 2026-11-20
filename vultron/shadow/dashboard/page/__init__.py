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


"""The case shadow tool's page: one case's standing, laid out (ADR-0192).

:func:`render` asks the analyst for a case, reads it through the one
:class:`~vultron.core.ports.case_reader.CaseReader` it is given, and shows
the case's level 1 standing as a scoreboard, each state on a small map of
its state machine (#6674), with its open moves in the bands of the case's
move advice (ADR-0200), and the case narrative: one line per ledger entry,
naming who did what, when, and which states it changed.  Beside the
analysis it always
shows the facts the reader could not translate, the states it inferred, and
what its source never records (SHD-01-004, CRD-02-005).

Above the scoreboard the analyst can pick a narrative line: the scoreboard
then shows the case as it stood just after that entry, worked out from the
entries up to it alone (:func:`~vultron.shadow.analysis.point_analysis`),
so they can ask whether a better move was open earlier (#6671).  Everything
the scoreboard draws follows the pick: its states and their maps, its
participants, desiderata, move bands with their legends, and the
authored action rules that match each vendor's position there (ADR-0216).  The pick
is kept in session state by the entry's log index, so a followed case's new
entries add narrative lines without moving it.

A reader that can follow a case
(:class:`~vultron.shadow.readers.following.CaseFollower`), the live Vultron
case reader, is followed instead of read once: the page shows the case's new
standing after each ledger entry arrives (#6531), unless the analyst has
picked an earlier point, and its narrative gains a
line for it, keeping every line before it, since each reading holds every
entry the node has sent (SHD-04-003).  The last accepted reading
is kept in session state.  A reading the reader refuses shows its error
above that reading, and a follow that ends marks it as no longer live; the
reading stays on the page either way (SHD-04-005).

Each case is handled inside :func:`~vultron.shadow.log_content.case_log_context`,
so its log records name the case and its tracker reference and never carry
its content (VSD-01-003).  Each ledger entry's record carries the entry's
activity id as its correlation id.  A followed case withholds each reading
it accepts.

The page only reads: it holds the reader and nothing that can send or write
(SHD-01-001, SHD-01-002).  A case it reads lives in the process's memory
only, and nothing of it is written to disk (SHD-01-003).

Each part of the page has its own module, and every name is imported from
here:

* :mod:`~vultron.shadow.dashboard.page.frame` — the title, the case box, and
  reading or following the case entered (:func:`render`).
* :mod:`~vultron.shadow.dashboard.page.follow` — a followed case, live.
* :mod:`~vultron.shadow.dashboard.page.reading` — one reading: logged, then
  shown.
* :mod:`~vultron.shadow.dashboard.page.points` — the point picker.
* :mod:`~vultron.shadow.dashboard.page.scoreboard` — the standing, with its
  state maps, participants and desiderata.
* :mod:`~vultron.shadow.dashboard.page.advice` — the move bands and their
  legends.
* :mod:`~vultron.shadow.dashboard.page.action_rules` — the authored action
  rules beside the bands, with each rule disagreement flagged.
* :mod:`~vultron.shadow.dashboard.page.narrative` — the case narrative.
* :mod:`~vultron.shadow.dashboard.page.reader_report` — the reader's report.
* :mod:`~vultron.shadow.dashboard.page.common` — the logger and table every
  part shares.
"""

from vultron.shadow.dashboard.page.follow import (
    HEARTBEAT_KEY,
    LAST_READING_KEY,
    LIVE_NOTE,
    NO_ENTRY_NOTE,
    NOT_LIVE_NOTE,
    RECONNECTING_NOTE,
    WAITING_NOTE,
)
from vultron.shadow.dashboard.page.frame import (
    CASE_KEY,
    TITLE,
    forget_case,
    render,
)
from vultron.shadow.dashboard.page.narrative import NARRATIVE_NOTE
from vultron.shadow.dashboard.page.points import POINT_KEY, POINT_WIDGET_KEY
from vultron.shadow.dashboard.page.scoreboard import END_UNCONFIRMED_NOTE

__all__ = [
    "CASE_KEY",
    "END_UNCONFIRMED_NOTE",
    "HEARTBEAT_KEY",
    "LAST_READING_KEY",
    "LIVE_NOTE",
    "NARRATIVE_NOTE",
    "NOT_LIVE_NOTE",
    "NO_ENTRY_NOTE",
    "POINT_KEY",
    "POINT_WIDGET_KEY",
    "RECONNECTING_NOTE",
    "TITLE",
    "WAITING_NOTE",
    "forget_case",
    "render",
]
