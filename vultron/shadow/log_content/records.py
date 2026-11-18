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

"""The log record factory that cleans every record, and the shadow's handler.

:func:`withheld_case_content` wraps the process's log record factory, so a
record is cleaned (:func:`withhold_case_content`) when it is made, before any
handler sees it.  :func:`shadow_logging` adds the shadow's one root handler.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TextIO

from vultron.logging_correlation import (
    CORRELATION_FIELDS,
    CorrelationFormatter,
    current_correlation,
    install_correlation_logging,
)
from vultron.shadow.log_content.context import (
    CaseLogContext,
    carried_context,
    current_case,
)
from vultron.shadow.log_content.render import (
    arg_values,
    exception_text,
    linked,
    safe_arg,
    safe_args,
    type_name,
)

#: The record attributes set inside a case context.
CASE_FIELDS: tuple[str, ...] = ("case_id", "case_reference")

#: The message of a record the factory could not clean.
UNCLEANED = "[log record withheld: cleaning it failed with %s]"


def _no_case(text: str) -> str:
    return text


def _record_case(
    record: logging.LogRecord, exc: BaseException | None
) -> CaseLogContext | None:
    """The case context *record* is about: the current one, else one an
    exception carried, withholding every carried context's content."""
    exceptions = linked(exc) if exc is not None else []
    for item in arg_values(record.args):
        if isinstance(item, BaseException):
            exceptions += linked(item)
    carried = [c for e in exceptions if (c := carried_context(e)) is not None]
    current = current_case()
    if current is not None:
        return current.joined(carried)
    if carried:
        return carried[0].joined(carried[1:])
    return None


def withhold_case_content(record: logging.LogRecord) -> logging.LogRecord:
    """Clean *record* of case content in place, and name its case.

    Returns:
        *record*, cleaned: its arguments made safe, its exception rendered
        into ``exc_text`` (``exc_info`` cleared, so no formatter renders the
        raw exception), the correlation ids set and, inside a case context,
        ``case_id`` and ``case_reference`` set.
    """
    exc = record.exc_info[1] if record.exc_info else None
    case = _record_case(record, exc)
    scrub = case.scrub if case is not None else _no_case
    if record.args:
        record.args = safe_args(record.msg, record.args, scrub)
    record.msg = safe_arg(record.msg, scrub)
    if record.exc_info:
        if exc is not None:
            record.exc_text = exception_text(exc, scrub)
        record.exc_info = None
    if record.stack_info:
        record.stack_info = scrub(record.stack_info)
    # The correlation ids too, so a record that reaches a handler without
    # the CorrelationFilter, such as Streamlit's, still carries them.
    record.__dict__.update(current_correlation())
    if case is not None:
        record.__dict__["case_id"] = case.case_id
        if case.references:
            record.__dict__["case_reference"] = ",".join(case.references)
    return record


def _uncleaned(record: logging.LogRecord, error: Exception) -> None:
    """Replace *record*'s text with :data:`UNCLEANED`: a record that could
    not be cleaned is still written, so the log call does not fail, but none
    of its content is."""
    record.msg = UNCLEANED
    record.args = (type_name(error),)
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None


_RecordFactory = Callable[..., logging.LogRecord]


@contextmanager
def withheld_case_content() -> Generator[None]:
    """Clean every log record made in the block (:func:`withhold_case_content`).

    Wraps the current log record factory, and puts it back on exit.  A
    record the cleaning fails on is written as :data:`UNCLEANED`, so a fault
    here never breaks the caller's log call.
    """
    previous: _RecordFactory = logging.getLogRecordFactory()

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        try:
            return withhold_case_content(record)
        except Exception as error:  # noqa: BLE001 - logging must not raise
            _uncleaned(record, error)
            return record

    logging.setLogRecordFactory(factory)
    try:
        yield
    finally:
        logging.setLogRecordFactory(previous)


class ShadowFormatter(CorrelationFormatter):
    """Prints the correlation ids, the case id and its tracker reference."""

    fields = (*CORRELATION_FIELDS, *CASE_FIELDS)


@contextmanager
def shadow_logging(
    level: int = logging.INFO, stream: TextIO | None = None
) -> Generator[logging.Handler]:
    """The case shadow's logging, for the length of the block.

    Cleans every record (:func:`withheld_case_content`), and writes the
    root logger's records at *level* and above to *stream* (standard error
    by default) with :class:`ShadowFormatter`.  On exit the handler is
    removed and the root level and record factory are put back.

    Yields:
        The handler it added.
    """
    root = logging.getLogger()
    handler = logging.StreamHandler(
        stream if stream is not None else sys.stderr
    )
    install_correlation_logging([handler], formatter=ShadowFormatter)
    saved_level = root.level
    with withheld_case_content():
        root.addHandler(handler)
        root.setLevel(level)
        try:
            yield handler
        finally:
            root.removeHandler(handler)
            root.setLevel(saved_level)


__all__ = [
    "CASE_FIELDS",
    "UNCLEANED",
    "ShadowFormatter",
    "shadow_logging",
    "withheld_case_content",
    "withhold_case_content",
]
