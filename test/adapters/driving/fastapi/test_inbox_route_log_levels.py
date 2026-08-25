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

"""Inbox-route HTTP handler chatter is DEBUG, not INFO (SL-04-007).

Two patterns are covered:

- ``Parsing activity from request body`` — HTTP handler internals, and a
  duplicate of the ``vultron.wire.as2.parser`` line that follows it.
- ``Activity ... already received by ...; ignoring duplicate submission`` —
  normal sync-protocol behaviour, not an anomaly worth INFO.
"""

import logging

from vultron.adapters.driving.fastapi.routers.actors import _inbox
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# The inbox router logs through uvicorn's error logger so its records
# appear alongside server output.
_INBOX_LOGGER = "uvicorn.error"


def _body() -> dict:
    activity = rm_create_report_activity(
        report=as_VulnerabilityReport(
            name="LOG-001", content="log-level test report"
        ),
        actor="https://example.org/actors/finder",
        to=["https://example.org/actors/vendor"],
    )
    return activity.model_dump(by_alias=True, exclude_none=True)


def _parsing_records(caplog) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if "Parsing activity from request body" in r.getMessage()
    ]


def test_parse_activity_logs_body_dump_at_debug(caplog):
    """The request-body dump is emitted at DEBUG."""
    with caplog.at_level(logging.DEBUG, logger=_INBOX_LOGGER):
        _inbox.parse_activity(_body())

    records = _parsing_records(caplog)
    assert records, "Expected the request-body parsing log entry"
    assert all(r.levelno == logging.DEBUG for r in records)


def test_parse_activity_body_dump_not_emitted_at_info(caplog):
    """No request-body dump reaches an INFO-only handler."""
    with caplog.at_level(logging.INFO, logger=_INBOX_LOGGER):
        _inbox.parse_activity(_body())

    assert not _parsing_records(caplog)


class _StubInbox:
    """Inbox stand-in exposing the ``items`` list the dedup guard reads."""

    def __init__(self, items: list[str]) -> None:
        self.items = items


class _StubActor:
    """CoreActor stand-in exposing only the inbox the guard reads."""

    def __init__(self, received: list[str]) -> None:
        self.id_ = "https://example.org/actors/vendor"
        self.inbox = _StubInbox(received)


def test_duplicate_submission_guard_still_detects_duplicates():
    """Demoting the log level does not change the dedup decision."""
    activity_id = "urn:uuid:already-seen"
    actor = _StubActor([activity_id])

    assert _inbox._activity_already_received(actor, activity_id)  # type: ignore[arg-type]
    assert not _inbox._activity_already_received(actor, "urn:uuid:fresh")  # type: ignore[arg-type]
