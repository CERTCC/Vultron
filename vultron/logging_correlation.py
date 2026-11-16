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

"""Correlation ids on log records, from ambient context (SL-02-003).

A processing boundary (inbox receipt of an activity, BT execution on behalf of
an actor, one poll of an external system) enters :func:`correlation_context`
once.  Every record written inside it, by any module, then carries
``activity_id`` and ``actor_id`` as record **attributes**, copied by
:class:`CorrelationFilter`.  No log call passes them through ``extra=``
(``test/architecture/test_no_correlation_ids_in_log_extra.py``), and naming an
id in the message text does not count (SL-02-004).

Like :mod:`vultron.logging_setup`, this module is defined once and installed at
each entry point: :func:`install_correlation_logging` puts the filter and the
plain-text :class:`CorrelationFormatter` on the handlers that entry point owns.
How the attributes are rendered is the formatter's decision; no call site
changes when it does.

The ids live in :mod:`contextvars`, so they follow the code that set them into
``asyncio`` tasks and ``anyio`` worker threads, and never leak between two
concurrent requests.  A filter reads the context when its handler runs, so it
belongs on a handler that runs where the record is emitted (a
``QueueHandler``, not the handlers behind a ``QueueListener``).

See ``notes/structured-logging.md`` § "``extra=`` is not the other option".
"""

import logging
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar, Token

from vultron.primitives import require_non_empty

#: The plain-text line format entry points use: timestamp, level, component
#: (the logger name, SL-01-003) and message.  :class:`CorrelationFormatter`
#: appends whichever correlation ids are set after the message.
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

#: One context variable per correlation field, keyed by the record attribute
#: it fills.  The one place the fields and their print order are defined;
#: :func:`correlation_context` maps its keyword parameters onto these keys.
_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    name: ContextVar(f"vultron_log_{name}", default=None)
    for name in ("activity_id", "actor_id")
}

#: The record attributes this module sets, in the order the formatter prints
#: them.
CORRELATION_FIELDS: tuple[str, ...] = tuple(_CONTEXT_VARS)


def current_correlation() -> dict[str, str]:
    """Return the correlation ids set in the current context, by field name.

    A field that is not set is absent from the result, never ``None`` or
    ``""``.
    """
    fields: dict[str, str] = {}
    for name in CORRELATION_FIELDS:
        value = _CONTEXT_VARS[name].get()
        if value is not None:
            fields[name] = value
    return fields


@contextmanager
def correlation_context(
    *,
    activity_id: str | None = None,
    actor_id: str | None = None,
) -> Generator[None]:
    """Set correlation ids for every record written inside the block.

    A field passed as ``None`` keeps the value the enclosing context set, so a
    BT run that names only its actor still carries the activity id of the inbox
    receipt around it.  On exit each field returns to the value it had on
    entry, also when the block raises, so nested use restores the outer ids.

    Args:
        activity_id: The id of the activity being processed.
        actor_id: The id of the actor the processing runs on behalf of.

    Raises:
        ValueError: A field is passed as a blank string.  A record never
            carries an empty correlation id (CS-08-001).
    """
    requested = {"activity_id": activity_id, "actor_id": actor_id}
    for name, value in requested.items():
        if value is not None:
            require_non_empty(value, name)
    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = [
        (_CONTEXT_VARS[name], _CONTEXT_VARS[name].set(value))
        for name, value in requested.items()
        if value is not None
    ]
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class CorrelationFilter(logging.Filter):
    """Copy the current correlation ids onto each record (SL-02-003).

    Sets an attribute for each id that :func:`correlation_context` has set and
    leaves the others absent, so a formatter or test can tell "not known" from
    a value.  Never drops a record.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for name, value in current_correlation().items():
            setattr(record, name, value)
        return True


class CorrelationFormatter(logging.Formatter):
    """Plain-text formatter that prints the correlation ids beside the message.

    The line is the configured format, then `` [activity_id=… actor_id=…]``
    naming only the ids the record carries.  A record without either id
    renders exactly as the base format would.  The ids go on the message line,
    before any traceback the base class appends.
    """

    def formatMessage(self, record: logging.LogRecord) -> str:
        line = super().formatMessage(record)
        present = [
            f"{name}={getattr(record, name)}"
            for name in CORRELATION_FIELDS
            if hasattr(record, name)
        ]
        if not present:
            return line
        return f"{line} [{' '.join(present)}]"


def install_correlation_logging(
    handlers: Iterable[logging.Handler],
    fmt: str = DEFAULT_LOG_FORMAT,
    datefmt: str | None = None,
) -> None:
    """Put the correlation filter and formatter on each handler.

    Adds one :class:`CorrelationFilter` per handler (a second call adds no
    second filter) and sets a :class:`CorrelationFormatter` built from *fmt*
    and *datefmt*.  The filter goes on handlers, not loggers, because a
    logger's filters do not run for records propagated from its children.

    Args:
        handlers: The handlers the entry point owns, e.g.
            ``logging.getLogger().handlers``.
        fmt: The base line format; defaults to :data:`DEFAULT_LOG_FORMAT`.
        datefmt: The ``asctime`` format, or ``None`` for the logging default.
    """
    for handler in handlers:
        if not any(isinstance(f, CorrelationFilter) for f in handler.filters):
            handler.addFilter(CorrelationFilter())
        handler.setFormatter(CorrelationFormatter(fmt, datefmt))
