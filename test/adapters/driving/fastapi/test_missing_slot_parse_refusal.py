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
"""A message missing a required slot leaves nothing on its receiver (#6493 AC-4).

The inbox's extraction step (``ExtractSemanticsNode``) builds the event
before dispatch, where nothing is kept, so a message whose event refuses a
missing slot is rejected there: one WARNING naming the slot, no deferral to
retry it, and no receipt stub.  CLP-10-018's stub records the refusal of an
assertion that parsed; this one never did (ARCH-10-001, ADR-0032).

Driven through the production inbox run (:func:`pipeline._process_one`)
with the production dispatcher, for every message whose semantic pattern
still matches once the slot's field is cut, so the extraction, not the
pattern, refuses it (:mod:`test.support.required_slots`); an
answer to a case proposal with no inline report is refused one step
earlier, by the wire parser, and leaves nothing either.
"""

import logging

import pytest

from test.support.received import delivered_body
from test.support.required_slots import (
    CASES,
    RECEIVER,
    SlotCase,
    slot_reason,
    without_slot,
)
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import pipeline
from vultron.core.services.received_activity import held_received_record

#: The rows whose semantic pattern still matches the cut message.
REACHING_THE_EVENT = [
    case for case in CASES if case.cut_matches is case.semantics
]

#: Messages the wire parser refuses before extraction: an inline
#: ``CaseProposal`` with no report is malformed (``as_CaseProposal``
#: requires its object), so the ingress rejects the body first.
PARSER_REFUSES = frozenset({"Accept(CaseProposal)", "Reject(CaseProposal)"})


@pytest.fixture
def dl():
    """The receiving actor's own store (ADR-0073)."""
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)
    yield store
    store.close()


def test_some_rows_reach_the_event() -> None:
    """The parametrisation below is never empty."""
    assert REACHING_THE_EVENT


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize("case", REACHING_THE_EVENT, ids=lambda case: case.id)
def test_a_message_missing_a_required_slot_leaves_nothing_stored(
    dl: SqliteDataLayer, case: SlotCase, caplog: pytest.LogCaptureFixture
) -> None:
    activity = without_slot(case)
    body = delivered_body(activity)
    before = dl.count_all()

    run = pipeline._InboxRun(dl, RECEIVER, make_dispatcher())
    with caplog.at_level(logging.WARNING):
        pipeline._process_one(run, body, SystemClock().now())

    rejections = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "Inbox activity rejected" in record.getMessage()
    ]
    assert len(rejections) == 1
    message = rejections[0].getMessage()
    if case.message in PARSER_REFUSES:
        assert "Ingress adapter returned None from parse()" in message
    else:
        assert "extract_event raised exception" in message
        assert slot_reason(case) in message
    # Nothing kept: no receipt stub, no held body, no queued retry.
    assert held_received_record(dl, activity.id_) is None
    assert dl.count_all() == before
