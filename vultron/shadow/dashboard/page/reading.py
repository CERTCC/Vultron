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


"""One reading on the page: logged once accepted, its content withheld
from the case's records (VSD-01-003), then shown as the scoreboard at the
picked point, the case narrative and the reader's report.
"""

from __future__ import annotations

import streamlit as st

from vultron.core.models.case_reading import CaseReading
from vultron.logging_correlation import correlation_context
from vultron.shadow.analysis import analyse, point_analysis
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import logger
from vultron.shadow.dashboard.page.narrative import _show_narrative
from vultron.shadow.dashboard.page.points import _pick_point
from vultron.shadow.dashboard.page.reader_report import _show_reader_report
from vultron.shadow.dashboard.page.scoreboard import _show_standing
from vultron.shadow.log_content import CaseLog


def _log_reading(case_id: str, reading: CaseReading) -> None:
    """Log what was read: the case, then each entry and its source record."""
    logger.info(
        "Read case %s: %d ledger entries, %d inferences, %d untranslated"
        " facts",
        case_id,
        len(reading.ledger),
        len(reading.inferences),
        len(reading.untranslated),
    )
    sources = {c.entry_id: c.source_record for c in reading.citations}
    for entry in reading.ledger:
        with correlation_context(activity_id=entry.log_object_id):
            logger.debug(
                "Case %s entry %s (%s) translates source record %s",
                case_id,
                entry.id_,
                entry.semantic_type,
                sources[entry.id_],
            )
    for fact in reading.untranslated:
        logger.debug(
            "Case %s source record %s not translated: %s",
            case_id,
            fact.source_record,
            fact.reason,
        )


def _accept(case_log: CaseLog, case_id: str, reading: CaseReading) -> None:
    """Withhold *reading*'s content from the case's records, then log it."""
    case_log.withhold(reading)
    _log_reading(case_id, reading)


def _show_reading(reading: CaseReading, case_id: str, draw: int = 0) -> None:
    """Show *reading*: the scoreboard at the picked point, the narrative and
    the reader's report.  *draw* numbers the reading's draw in this run."""
    analysis = analyse(reading)
    shown, past_point = analysis, False
    if analysis.narrative:
        point = _pick_point(case_id, analysis, draw)
        if point != view.LATEST_POINT:
            st.info(view.point_note(point, analysis.narrative))
            shown = point_analysis(analysis, point)
            past_point = point != analysis.narrative[-1].log_index
    _show_standing(shown, past_point=past_point)
    _show_narrative(analysis)
    _show_reader_report(reading)
