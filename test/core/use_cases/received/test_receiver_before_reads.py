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

"""A received use case resolves its receiver before its first store read.

Each handler here reads the DataLayer, before its tree runs or through the
tree's own doors (an unknown case is the path stage's refusal, HP-01-039).
With no receiver to resolve, it must raise as a wiring fault before it
touches the store, so a read's answer never turns our fault into a refusal
of the sender (BT-17-009, ARCH-15-001).  The store below reports no
owner and fails on any other access, so a read ahead of the resolution fails
the test with its own message instead of raising the expected error.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from test.support.act_runner import run_in_act
from test.support.objects import make
from vultron.core.models.note import VultronNote
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.accept import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.invite import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report.rm_transitions import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.errors import VultronValidationError

_CASE = "https://example.org/cases/nope"


class _UnreadableOwnerlessStore:
    """A store with no owner that fails on any access but ``actor_id``."""

    actor_id = None

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(
            f"store accessed ('{name}') before the receiver was resolved"
        )


def _request(**fields: object) -> SimpleNamespace:
    """A received request with no receiver stamp and the fields given."""
    return SimpleNamespace(
        receiving_actor_id=None,
        actor_id="https://example.org/actors/sender",
        activity_id="https://example.org/activities/a1",
        **fields,
    )


_CASES = [
    pytest.param(
        AddNoteToCaseReceivedUseCase,
        _request(
            note=make(VultronNote, id_=f"{_CASE}/notes/n1", content="x"),
            case_id=_CASE,
        ),
        id="add-note",
    ),
    pytest.param(
        RemoveNoteFromCaseReceivedUseCase,
        _request(note_id="n1", case_id=_CASE),
        id="remove-note",
    ),
    pytest.param(
        AddParticipantStatusToParticipantReceivedUseCase,
        _request(
            status_id="s1", participant_id="p1", context_id=_CASE, status=None
        ),
        id="add-participant-status",
    ),
    pytest.param(
        ValidateReportReceivedUseCase,
        _request(report_id="r1", offer_id="o1"),
        id="validate-report",
    ),
    pytest.param(
        InvalidateReportReceivedUseCase,
        _request(report_id="r1"),
        id="invalidate-report",
    ),
    pytest.param(
        CloseReportReceivedUseCase,
        _request(report_id="r1"),
        id="close-report",
    ),
    pytest.param(
        AddReportToCaseReceivedUseCase,
        _request(report_id="r1", case_id=_CASE),
        id="add-report-to-case",
    ),
    pytest.param(
        InviteToEmbargoOnCaseReceivedUseCase,
        _request(context_id=_CASE),
        id="invite-to-embargo",
    ),
    pytest.param(
        AcceptInviteToEmbargoOnCaseReceivedUseCase,
        _request(
            embargo_id=f"{_CASE}/embargo_events/e1",
            invite_id="i1",
            case_id=_CASE,
        ),
        id="accept-embargo-invite",
    ),
]


@pytest.mark.spec("BT-17-009")
@pytest.mark.spec("ARCH-15-001")
@pytest.mark.parametrize(("use_case", "request_"), _CASES)
def test_no_resolvable_receiver_raises_before_any_store_read(
    use_case: Any, request_: SimpleNamespace
) -> None:
    with pytest.raises(VultronValidationError, match="receiving actor"):
        run_in_act(use_case(_UnreadableOwnerlessStore(), request_))
