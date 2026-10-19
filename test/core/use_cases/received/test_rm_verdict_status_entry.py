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

"""An RM verdict's status follows the act as its own entry (#4295, CLP-07-013).

The CASE_MANAGER commits the verdict (``invalidate_report`` here; every
activity-typed RM move shares the stage, ``record_rm_declaration``), writes
the sender's status, and commits that status as an
``add_participant_status_to_participant`` entry carrying the very object it
stored.  A replica copies the status from that entry, so the act's own entry
changes no state (CM-23-016).  A status whose entry does not commit is taken
back.
"""

from typing import cast

import pytest

from test.support.ledger import fail_commits, ledger_entries
from vultron.core.behaviors.case.nodes.participant import status_entries
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import InvalidateReportReceivedEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import (
    InvalidateReportReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import rm_invalidate_report_activity

from .test_receive_tree_ledger_commit import (
    CASE_ID,
    FINDER_ID,
    MANAGER_ID,
    _offer,
    _ports,
    _store,
)

_STATUS_ENTRY = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value


def _invalidate(dl):
    event = cast(
        InvalidateReportReceivedEvent,
        extract_event(
            rm_invalidate_report_activity(
                _offer(), actor=FINDER_ID, to=[MANAGER_ID]
            )
        ).model_copy(update={"receiving_actor_id": MANAGER_ID}),
    )
    return InvalidateReportReceivedUseCase(dl, event, **_ports(dl)).execute()


def _finder(dl) -> CaseParticipant:
    case = dl.read(CASE_ID)
    record = dl.read(case.actor_participant_index[FINDER_ID])
    assert isinstance(record, CaseParticipant)
    return record


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_the_verdict_is_followed_by_the_stored_status_in_full():
    dl = _store(MANAGER_ID)

    result = _invalidate(dl)

    assert result.disposition is HandlerDisposition.APPLIED
    entries = ledger_entries(dl, CASE_ID)
    assert [e.semantic_type for e in entries] == [
        MessageSemantics.INVALIDATE_REPORT.value,
        _STATUS_ENTRY,
    ]
    stored = _finder(dl).participant_statuses[-1]
    assert isinstance(stored, ParticipantStatus)
    assert stored.rm.state == RM.INVALID
    carried = ParticipantStatus.model_validate(
        project_wire_snapshot_to_core(
            ParticipantStatus, entries[1].payload_snapshot["object"]
        )
    )
    assert carried == stored


@pytest.mark.spec("CLP-07-013")
def test_a_status_whose_entry_fails_is_taken_back(monkeypatch):
    dl = _store(MANAGER_ID)
    before = [s.id_ for s in _finder(dl).participant_statuses]
    fail_commits(
        monkeypatch,
        status_entries,
        when=lambda kwargs: kwargs["semantic_type"] == _STATUS_ENTRY,
    )

    result = _invalidate(dl)

    assert result.disposition is not HandlerDisposition.APPLIED
    assert [s.id_ for s in _finder(dl).participant_statuses] == before
    assert _STATUS_ENTRY not in [
        e.semantic_type for e in ledger_entries(dl, CASE_ID)
    ]


@pytest.mark.spec("RSH-08-002")
def test_a_repeated_verdict_writes_and_commits_no_second_status():
    dl = _store(MANAGER_ID)
    _invalidate(dl)
    statuses = [s.id_ for s in _finder(dl).participant_statuses]

    # A new activity with the same verdict: recorded once (RSH-08-002).
    assert _invalidate(dl).disposition is not HandlerDisposition.REFUSED

    assert [s.id_ for s in _finder(dl).participant_statuses] == statuses
    assert [e.semantic_type for e in ledger_entries(dl, CASE_ID)].count(
        _STATUS_ENTRY
    ) == 1


@pytest.mark.spec("CLP-07-013")
def test_a_redelivered_verdict_records_the_withdrawn_status(monkeypatch):
    """The act's entry stays; a redelivery writes and commits the status."""
    dl = _store(MANAGER_ID)
    event = cast(
        InvalidateReportReceivedEvent,
        extract_event(
            rm_invalidate_report_activity(
                _offer(), actor=FINDER_ID, to=[MANAGER_ID]
            )
        ).model_copy(update={"receiving_actor_id": MANAGER_ID}),
    )
    with monkeypatch.context() as patched:
        fail_commits(
            patched,
            status_entries,
            when=lambda kwargs: kwargs["semantic_type"] == _STATUS_ENTRY,
        )
        InvalidateReportReceivedUseCase(dl, event, **_ports(dl)).execute()

    InvalidateReportReceivedUseCase(dl, event, **_ports(dl)).execute()

    assert [e.semantic_type for e in ledger_entries(dl, CASE_ID)] == [
        MessageSemantics.INVALIDATE_REPORT.value,
        _STATUS_ENTRY,
    ]
    assert _finder(dl).participant_statuses[-1].rm.state == RM.INVALID
