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

"""The case shadow's log records carry ids, never case content (VSD-01-003).

Logs are copied into issues, CI artifacts and agent sessions, so a log record
is a publication path (ADR-0189).  While :func:`withheld_case_content` is
active, every log record the process makes, by any logger and whatever
handler later writes it, is cleaned when it is made:

* A message argument that is an object, not a scalar, is replaced by its type
  name and id.  A whole case reading, entry or payload never reaches the
  text.
* An exception, logged with ``exc_info`` or passed as an argument, keeps its
  traceback (file, line, function and source line) and its type.  The message
  of a :class:`~vultron.errors.VultronError` is kept, because Vultron authors
  those messages to name ids and problems, not values.  Any other exception's
  message is withheld: a validation error, for one, quotes the input it
  refused.
* Inside :func:`case_log_context`, every string of the case reading's content
  (:func:`reading_content`) is replaced in each argument and traceback by
  :data:`WITHHELD`.  An exception raised inside the context carries the
  context out with it, so a record made after the context has exited, such as
  Streamlit's log of an uncaught page exception, is cleaned too.

The ids stay: inside :func:`case_log_context` each record carries
``case_id``, and ``case_reference`` when the case's ledger holds an outside
tracker reference (an ``issue-tracking`` ``CaseReference``, such as a VINCE
case URL).  The shadow keeps no copy of a case (SHD-01-003), so that reference
is how a log read after the run finds the case again.  The correlation ids
(``activity_id``, ``actor_id``) come from
:func:`~vultron.logging_correlation.correlation_context`, and
:class:`ShadowFormatter` prints all of them after the message.

The records are cleaned by a log record factory, not a handler filter,
because Streamlit writes its own records through handlers of its own, which
it replaces when it reads its configuration.  A factory sees each record when
it is made, before any handler.  :func:`shadow_logging` installs the factory
and the shadow's one root handler; ``vultron-shadow`` enters it around the
whole run.
"""

from __future__ import annotations

import logging
import re
import sys
import traceback
from collections.abc import Callable, Generator, Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
from pathlib import PurePath
from typing import Any, TextIO

from pydantic import ValidationError

from vultron.core.models.case_reading import CaseReading
from vultron.core.models.case_reference import CVE_REFERENCE_TAG_RELS
from vultron.errors import VultronError
from vultron.logging_correlation import (
    CORRELATION_FIELDS,
    CorrelationFormatter,
    current_correlation,
    install_correlation_logging,
)

#: What a withheld piece of case content is replaced by.
WITHHELD = "[case content withheld]"

#: What a non-Vultron exception's message is replaced by.
WITHHELD_MESSAGE = "[message withheld]"

#: The record attributes set inside :func:`case_log_context`.
CASE_FIELDS: tuple[str, ...] = ("case_id", "case_reference")

#: The ``rel`` of an outside tracker reference.
ISSUE_TRACKING_REL = CVE_REFERENCE_TAG_RELS["issue-tracking"]

#: Payload keys whose string values are vocabulary, types or times: never
#: case content.  An ``id`` key, or one that ends in ``Id``, holds an id.
#: Every other string in a payload is content, unless it is an IRI, so a key
#: an outside reader adds is withheld until it is listed here.
_VOCABULARY_KEYS = frozenset(
    {
        "@context",
        "id",
        "state",
        "status",
        "type",
        "published",
        "updated",
        "startTime",
        "endTime",
        "deleted",
        "mediaType",
        "rel",
        "semanticType",
        "emState",
        "pxaState",
        "rmState",
        "vfState",
        "cvdRole",
        "caseRoles",
    }
)

#: An IRI names an object, actor or link: an identifier, not content.
_IRI = re.compile(r"(?:urn|https?):\S+\Z")

#: A string shorter than this carries no case content worth withholding,
#: and replacing it would cut through every word that holds it.
_SHORTEST_CONTENT = 4

_CAUSE = "The above exception was the direct cause of the following exception:"
_CONTEXT = (
    "During handling of the above exception, another exception occurred:"
)

#: The exception attribute that carries a case context out of its block.
_CARRIED = "_vultron_case_log_context"


@dataclass(frozen=True)
class CaseLogContext:
    """The case being handled, as its log records name and withhold it.

    Attributes:
        case_id: The case id the shadow was asked for.
        references: The case's outside tracker references, in ledger order.
        content: The case content to withhold, longest first, so a longer
            string is replaced before a shorter one it holds.
    """

    case_id: str
    references: tuple[str, ...] = ()
    content: tuple[str, ...] = ()


_CASE: ContextVar[CaseLogContext | None] = ContextVar(
    "vultron_shadow_case_log", default=None
)


def _names_no_content(key: str | None) -> bool:
    """Whether a string under payload key *key* is never case content."""
    return key is not None and (key in _VOCABULARY_KEYS or key.endswith("Id"))


def _payload_strings(value: object, key: str | None, found: set[str]) -> None:
    """Add each content string in *value*, found under *key*, to *found*."""
    if isinstance(value, Mapping):
        for name, item in value.items():
            _payload_strings(item, str(name), found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _payload_strings(item, key, found)
    elif isinstance(value, str) and not _names_no_content(key):
        found.add(value)


def _rels(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _references_in(value: object, found: list[str]) -> None:
    """Append the href of each tracker reference in *value* to *found*."""
    if isinstance(value, Mapping):
        url = value.get("url")
        if value.get("type") == "CaseReference" and isinstance(url, Mapping):
            href = url.get("href")
            if (
                isinstance(href, str)
                and href
                and ISSUE_TRACKING_REL in _rels(url.get("rel"))
                and href not in found
            ):
                found.append(href)
        for item in value.values():
            _references_in(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _references_in(item, found)


def tracker_references(reading: CaseReading) -> tuple[str, ...]:
    """The outside tracker references *reading*'s ledger holds, in order.

    Each is the ``href`` of an ``issue-tracking`` ``CaseReference``, such as
    a VINCE case URL.
    """
    found: list[str] = []
    for entry in reading.ledger:
        _references_in(entry.payload_snapshot, found)
    return tuple(found)


def _identifiers(reading: CaseReading) -> set[str]:
    ids: set[str] = set(tracker_references(reading))
    for entry in reading.ledger:
        ids.update((entry.case_id, entry.id_, entry.log_object_id))
    for citation in reading.citations:
        ids.update((citation.entry_id, citation.source_record))
    for inference in reading.inferences:
        ids.update((inference.entry_id, inference.rule_id))
    ids.update(fact.source_record for fact in reading.untranslated)
    return ids


def reading_content(reading: CaseReading) -> tuple[str, ...]:
    """The strings of *reading* that are case content, longest first.

    Content is every string in an entry's payload except vocabulary, times
    and IRIs, every untranslated fact (which names its field and value) and
    every inference caveat.  The reading's ids are not content.  Each line
    of a multi-line string is content too, so a traceback line that quotes
    one line of a description still loses it.
    """
    found: set[str] = set()
    for entry in reading.ledger:
        _payload_strings(entry.payload_snapshot, None, found)
    found.update(fact.fact for fact in reading.untranslated)
    found.update(inference.caveat for inference in reading.inferences)
    pieces: set[str] = set()
    for text in found:
        pieces.add(text.strip())
        pieces.update(line.strip() for line in text.splitlines())
    ids = _identifiers(reading)
    kept = {
        piece
        for piece in pieces
        if len(piece) >= _SHORTEST_CONTENT
        and piece not in ids
        and not _IRI.match(piece)
    }
    return tuple(sorted(kept, key=lambda piece: (-len(piece), piece)))


class CaseLog:
    """The handle :func:`case_log_context` yields for its case.

    Args:
        case_id: The case id the context names.
    """

    def __init__(self, case_id: str) -> None:
        self._case_id = case_id

    def withhold(self, reading: CaseReading) -> None:
        """Withhold *reading*'s content from the rest of the block's records.

        Also names the reading's tracker references on those records.
        """
        _CASE.set(
            CaseLogContext(
                case_id=self._case_id,
                references=tracker_references(reading),
                content=reading_content(reading),
            )
        )


@contextmanager
def case_log_context(case_id: str) -> Generator[CaseLog]:
    """Name *case_id* on every record the block makes.

    Call :meth:`CaseLog.withhold` once the case is read, so the rest of the
    block's records withhold its content and name its tracker references.
    An exception that leaves the block carries the case context with it.
    """
    token = _CASE.set(CaseLogContext(case_id=case_id))
    try:
        yield CaseLog(case_id)
    except BaseException as exc:
        context = _CASE.get()
        # The innermost context is the most specific; an outer one leaves
        # it in place.
        if context is not None and not hasattr(exc, _CARRIED):
            setattr(exc, _CARRIED, context)
        raise
    finally:
        _CASE.reset(token)


def _scrub(text: str, content: Iterable[str]) -> str:
    for piece in content:
        text = text.replace(piece, WITHHELD)
    return text


def _type_name(exc: BaseException) -> str:
    kind = type(exc)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def _exception_message(exc: BaseException, content: Iterable[str]) -> str:
    """*exc*'s message, as a shadow log record may carry it."""
    if isinstance(exc, VultronError):
        return _scrub(str(exc), content)
    if isinstance(exc, ValidationError):
        # Each error's location and kind, never its message or input: a
        # validator's message may quote the value it refused.
        where = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['type']}"
            for error in exc.errors(include_url=False, include_input=False)
        )
        return _scrub(
            f"{exc.error_count()} validation error(s) for {exc.title}"
            f" ({where})",
            content,
        )
    return WITHHELD_MESSAGE


def _exception_lines(
    exc: BaseException, content: tuple[str, ...], seen: set[int]
) -> list[str]:
    """*exc* and its chain as traceback lines, oldest exception first."""
    seen.add(id(exc))
    lines: list[str] = []
    cause, context = exc.__cause__, exc.__context__
    if cause is not None and id(cause) not in seen:
        lines += [*_exception_lines(cause, content, seen), "", _CAUSE, ""]
    elif (
        context is not None
        and not exc.__suppress_context__
        and id(context) not in seen
    ):
        lines += [*_exception_lines(context, content, seen), "", _CONTEXT, ""]
    if exc.__traceback__ is not None:
        lines.append("Traceback (most recent call last):")
        lines += "".join(traceback.format_tb(exc.__traceback__)).splitlines()
    lines.append(f"{_type_name(exc)}: {_exception_message(exc, content)}")
    if isinstance(exc, BaseExceptionGroup):
        for number, member in enumerate(exc.exceptions, start=1):
            lines.append(f"  Sub-exception {number}:")
            lines += [
                f"    {line}"
                for line in _exception_lines(member, content, seen)
            ]
    return lines


def _chain(exc: BaseException | None) -> list[BaseException]:
    """*exc*, its causes, contexts and group members, each once."""
    found: list[BaseException] = []
    pending = [exc] if exc is not None else []
    while pending:
        current = pending.pop()
        if any(current is known for known in found):
            continue
        found.append(current)
        pending += [
            linked
            for linked in (current.__cause__, current.__context__)
            if linked is not None
        ]
        if isinstance(current, BaseExceptionGroup):
            pending += list(current.exceptions)
    return found


def _carried(exceptions: Iterable[BaseException]) -> list[CaseLogContext]:
    return [
        carried
        for exc in exceptions
        if isinstance(carried := getattr(exc, _CARRIED, None), CaseLogContext)
    ]


def _placeholder(value: object) -> str:
    """*value* by its type name and id, without its content."""
    ident = getattr(value, "id_", None)
    name = type(value).__name__
    if isinstance(ident, str):
        return f"<{name} {ident}>"
    return f"<{name}>"


def _safe_arg(value: object, content: tuple[str, ...]) -> object:
    """*value* as a shadow log record may carry it."""
    if isinstance(value, BaseException):
        return f"{_type_name(value)}: {_exception_message(value, content)}"
    if isinstance(value, str):
        return _scrub(value, content)
    if isinstance(value, (bool, int, float, Enum, datetime, date)):
        return value
    if value is None:
        return None
    if isinstance(value, PurePath):
        text = str(value)
        scrubbed = _scrub(text, content)
        return value if scrubbed == text else scrubbed
    if isinstance(value, (list, tuple)):
        return type(value)(_safe_arg(item, content) for item in value)
    return _placeholder(value)


def _safe_args(msg: object, args: Any, content: tuple[str, ...]) -> Any:
    if isinstance(args, Mapping):
        if isinstance(msg, str) and "%(" in msg:
            return {key: _safe_arg(i, content) for key, i in args.items()}
        # A lone mapping argument that the message does not index by name
        # is rendered whole: it is an object, not named arguments.
        return (_placeholder(args),)
    if isinstance(args, tuple):
        return tuple(_safe_arg(item, content) for item in args)
    return _safe_arg(args, content)


def _merged(contexts: list[CaseLogContext]) -> CaseLogContext | None:
    """The first context's ids, with every context's content withheld."""
    if not contexts:
        return None
    pieces = {piece for context in contexts for piece in context.content}
    return replace(
        contexts[0],
        content=tuple(sorted(pieces, key=lambda piece: (-len(piece), piece))),
    )


def _arg_values(args: Any) -> list[object]:
    if isinstance(args, Mapping):
        return list(args.values())
    if isinstance(args, tuple):
        return list(args)
    return [args] if args is not None else []


def withhold_case_content(record: logging.LogRecord) -> logging.LogRecord:
    """Clean *record* of case content in place, and name its case.

    Returns:
        *record*, cleaned: its arguments made safe, its exception rendered
        into ``exc_text`` (``exc_info`` cleared, so no formatter renders the
        raw exception), the correlation ids set and, inside a case context,
        ``case_id`` and ``case_reference`` set.
    """
    exc = record.exc_info[1] if record.exc_info else None
    arg_errors = [
        item
        for item in _arg_values(record.args)
        if isinstance(item, BaseException)
    ]
    exceptions = _chain(exc) + [
        linked for item in arg_errors for linked in _chain(item)
    ]
    current = _CASE.get()
    context = _merged(
        ([current] if current is not None else []) + _carried(exceptions)
    )
    content = context.content if context is not None else ()

    if record.args:
        record.args = _safe_args(record.msg, record.args, content)
    record.msg = _safe_arg(record.msg, content)
    if record.exc_info:
        if exc is not None:
            record.exc_text = "\n".join(_exception_lines(exc, content, set()))
        record.exc_info = None
    if record.stack_info:
        record.stack_info = _scrub(record.stack_info, content)
    # The correlation ids too, so a record that reaches a handler without
    # the CorrelationFilter, such as Streamlit's, still carries them.
    record.__dict__.update(current_correlation())
    if context is not None:
        record.__dict__["case_id"] = context.case_id
        if context.references:
            record.__dict__["case_reference"] = ",".join(context.references)
    return record


_RecordFactory = Callable[..., logging.LogRecord]


@contextmanager
def withheld_case_content() -> Generator[None]:
    """Clean every log record made in the block (:func:`withhold_case_content`).

    Wraps the current log record factory, and puts it back on exit.
    """
    previous: _RecordFactory = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        return withhold_case_content(previous(*args, **kwargs))

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
    "ISSUE_TRACKING_REL",
    "WITHHELD",
    "WITHHELD_MESSAGE",
    "CaseLog",
    "CaseLogContext",
    "ShadowFormatter",
    "case_log_context",
    "reading_content",
    "shadow_logging",
    "tracker_references",
    "withheld_case_content",
    "withhold_case_content",
]
