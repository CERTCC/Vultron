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

"""The VINCE translation: one VINCE case's records, as a case reading.

:func:`translate_case` is a pure function.  It takes the records the VINCE
API serves for one case, keyed by their path below ``case/<vuid>/``, and
returns the :class:`~vultron.core.models.case_reading.CaseReading` the VINCE
crosswalk (``docs/reference/vince_crosswalk.md``) makes of them
(CRD-03-001).  It fetches nothing, stores nothing and reads no clock: every
time an entry carries is a time a VINCE record states (CRD-02-006), and
every id is minted from the VINCE instance and the case (:mod:`.ids`), so
the same records read at the same time always give the same reading.  The
time of reading is the caller's: whether the embargo has ended at its
``due_date`` (VINCE-EM-03) is judged against it.

An entry names as its actor the participant who acted in VINCE
(CRD-01-006) and cites the VINCE record it came from (CRD-01-004), as
``case/<vuid>/<read>`` with ``[<index>]`` for an item of a list read.  The
entries are in time order; entries that share a time keep the order of
:data:`STEPS`.  The translation logs nothing but the case's VINCE id and
counts (VSD-01-003).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime

from pydantic import JsonValue

from vultron.adapters.connectors.vince import (
    case_rows,
    content_rows,
    vendor_rows,
)
from vultron.adapters.connectors.vince.acts import render_reading
from vultron.adapters.connectors.vince.ids import CaseIds
from vultron.adapters.connectors.vince.records import parse_case
from vultron.adapters.connectors.vince.translation import CaseTranslation
from vultron.core.models.case_reading import CaseReading

logger = logging.getLogger(__name__)

#: The row groups, in the order entries that share a time keep.  CERT/CC is
#: seated first because every later row names it, and the report precedes
#: the case because the case carries the RM state the report gave CERT/CC,
#: so a report submitted at the case's ``created`` time lands just before
#: it.  The vuls precede the vendor statuses, which VINCE-RM-06 checks
#: against every vul.  The embargo's exit follows every act that may share
#: its time, so a vendor added at ``due_date`` agrees before it ends.  The
#: closure and the note come last because each reads CERT/CC's RM steps the
#: others wrote.
STEPS: tuple[Callable[[CaseTranslation], None], ...] = (
    case_rows.coordinator_seat,
    case_rows.report,
    case_rows.the_case,
    case_rows.opening,
    case_rows.case_status,
    vendor_rows.vendors,
    content_rows.vuls,
    vendor_rows.vendor_statuses,
    content_rows.posts,
    case_rows.embargo_exit,
    case_rows.closure,
    case_rows.note,
)


def translate_case(
    reads: Mapping[str, JsonValue], *, comm_url: str, as_of: datetime
) -> CaseReading:
    """Translate one VINCE case's records into a case reading (CRD-03-001).

    Args:
        reads: The JSON each per-case VINCE API read returned, keyed by the
            read's path below ``case/<vuid>/``: ``case`` (the case itself),
            ``report``, ``posts``, ``vuls``, ``vendors``, ``vendors/vuls``
            and ``note`` (:data:`~.records.READS`).  A ``None`` value is a
            read VINCE answered with 404; a missing read counts as one.
        comm_url: The VINCE Comm web root the case was read from, such as
            ``https://kb.cert.org/vince/comm`` (the API base without its
            trailing ``/api``).  It gives the case's VINCE URL and scopes
            every minted id.
        as_of: The time of reading, an aware datetime the caller supplies,
            such as the time it fetched *reads*.  The embargo's end is
            judged against it: when *as_of* is at or after the case's
            ``due_date``, the embargo ended at ``due_date`` (VINCE-EM-03);
            before it, the embargo is still in force.  It dates no entry,
            and the translation reads no clock (CRD-02-006).

    Returns:
        The reading: the ledger in time order, a citation per entry, the
        inferences by crosswalk row, the untranslated facts with their
        reasons, and :data:`~.crosswalk.VINCE_UNOBSERVABLE`.

    Raises:
        ValueError: *as_of* is a naive datetime.
        VinceCaseRecordsError: The ``case`` read is missing or lacks the
            ``vuid``, ``pk`` or ``created`` time every row needs.
    """
    if as_of.utcoffset() is None:
        raise ValueError("as_of must be an aware datetime")
    ids = CaseIds(comm_url=comm_url, case=parse_case(reads))
    translation = CaseTranslation(ids=ids, reads=reads, as_of=as_of)
    for step in STEPS:
        step(translation)
    reading = render_reading(ids, translation.acts, translation.untranslated)
    logger.debug(
        "Translated VINCE case %s: %d entries, %d inferences, %d untranslated",
        ids.case.vuid,
        len(reading.ledger),
        len(reading.inferences),
        len(reading.untranslated),
    )
    return reading


__all__ = ["STEPS", "translate_case"]
