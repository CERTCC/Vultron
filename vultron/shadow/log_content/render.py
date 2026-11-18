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

"""How a shadow log record renders its arguments and its exception.

An argument that is an object, not a scalar, is rendered by its type name
and id.  An exception keeps its traceback and type; only a
:class:`~vultron.errors.VultronError` keeps its message, and a pydantic
``ValidationError`` keeps each error's location and kind.  Every string
passes through the case context's scrub (:meth:`CaseLogContext.scrub`).
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Mapping
from datetime import date, datetime
from enum import Enum
from pathlib import PurePath

from pydantic import ValidationError

from vultron.errors import VultronError

#: What a non-Vultron exception's message is replaced by.
WITHHELD_MESSAGE = "[message withheld]"

#: A log record's arguments, as :class:`logging.LogRecord` holds them.
LogArgs = tuple[object, ...] | Mapping[str, object]

#: Withholds a case's content from a string.
Scrub = Callable[[str], str]

#: The longest exception chain rendered; the rest are counted, not shown.
MAX_CHAIN = 50

#: The deepest exception group nesting rendered.
MAX_GROUP_DEPTH = 5

_CAUSE = "The above exception was the direct cause of the following exception:"
_CONTEXT = (
    "During handling of the above exception, another exception occurred:"
)


def type_name(exc: BaseException) -> str:
    """*exc*'s type, qualified by its module unless it is a builtin."""
    kind = type(exc)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def exception_message(exc: BaseException, scrub: Scrub) -> str:
    """*exc*'s message, as a shadow log record may carry it."""
    if isinstance(exc, VultronError):
        return scrub(str(exc))
    if isinstance(exc, ValidationError):
        # Each error's location and kind, never its message or input: a
        # validator's message may quote the value it refused.
        where = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['type']}"
            for error in exc.errors(include_url=False, include_input=False)
        )
        return scrub(
            f"{exc.error_count()} validation error(s) for {exc.title}"
            f" ({where})"
        )
    return WITHHELD_MESSAGE


def chain(exc: BaseException) -> list[tuple[BaseException, str | None]]:
    """*exc* and the exceptions before it, newest first, each with the line
    that links it to the one after it (``None`` for *exc*).

    Walks the links in a loop, never by recursion, so no chain length can
    exhaust the stack; a chain longer than :data:`MAX_CHAIN` is cut there.
    """
    links: list[tuple[BaseException, str | None]] = [(exc, None)]
    seen = {id(exc)}
    current = exc
    while len(links) < MAX_CHAIN:
        cause, context = current.__cause__, current.__context__
        if cause is not None:
            nxt, link = cause, _CAUSE
        elif context is not None and not current.__suppress_context__:
            nxt, link = context, _CONTEXT
        else:
            break
        if id(nxt) in seen:
            break
        seen.add(id(nxt))
        links.append((nxt, link))
        current = nxt
    return links


def linked(exc: BaseException) -> list[BaseException]:
    """*exc*, its chain and its group members, each once, in a loop."""
    found: list[BaseException] = []
    seen: set[int] = set()
    pending = [exc]
    while pending and len(found) < MAX_CHAIN * MAX_GROUP_DEPTH:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)
        pending += [
            nxt
            for nxt in (current.__cause__, current.__context__)
            if nxt is not None
        ]
        if isinstance(current, BaseExceptionGroup):
            pending += list(current.exceptions)
    return found


def exception_text(exc: BaseException, scrub: Scrub, depth: int = 0) -> str:
    """*exc* and its chain as traceback text, oldest exception first."""
    links = chain(exc)
    lines: list[str] = []
    if len(links) == MAX_CHAIN:
        lines.append(f"[exceptions before the last {MAX_CHAIN} not shown]")
    for current, link in reversed(links):
        if current.__traceback__ is not None:
            lines.append("Traceback (most recent call last):")
            lines += "".join(
                traceback.format_tb(current.__traceback__)
            ).splitlines()
        lines.append(
            f"{type_name(current)}: {exception_message(current, scrub)}"
        )
        if isinstance(current, BaseExceptionGroup):
            lines += _members(current, scrub, depth)
        # The link says how this exception led to the newer one after it.
        if link is not None:
            lines += ["", link, ""]
    return "\n".join(lines)


def _members(
    group: BaseExceptionGroup[BaseException], scrub: Scrub, depth: int
) -> list[str]:
    if depth >= MAX_GROUP_DEPTH:
        return ["  [nested exception group not shown]"]
    lines: list[str] = []
    for number, member in enumerate(group.exceptions, start=1):
        lines.append(f"  Sub-exception {number}:")
        lines += [
            f"    {line}"
            for line in exception_text(member, scrub, depth + 1).splitlines()
        ]
    return lines


def placeholder(value: object) -> str:
    """*value* by its type name and id, without its content."""
    ident = getattr(value, "id_", None)
    name = type(value).__name__
    if isinstance(ident, str):
        return f"<{name} {ident}>"
    return f"<{name}>"


def safe_arg(value: object, scrub: Scrub) -> object:
    """*value* as a shadow log record may carry it."""
    if isinstance(value, BaseException):
        return f"{type_name(value)}: {exception_message(value, scrub)}"
    if isinstance(value, str):
        return scrub(value)
    if value is None or isinstance(
        value, (bool, int, float, Enum, datetime, date)
    ):
        return value
    if isinstance(value, PurePath):
        text = str(value)
        scrubbed = scrub(text)
        return value if scrubbed == text else scrubbed
    if isinstance(value, (list, tuple)):
        return type(value)(safe_arg(item, scrub) for item in value)
    return placeholder(value)


class _MappingPlaceholder(dict[str, object]):
    """A mapping that holds only, and prints as, a placeholder.

    It stands in for a lone mapping argument the message does not index by
    name.  Being a mapping, it formats exactly as the original would: a
    ``%s`` prints the placeholder, and a message with no conversion takes
    it without error, as ``"text" % {...}`` does.  It is not empty, because
    a record formats its message only when its arguments are truthy.
    """

    def __init__(self, text: str) -> None:
        super().__init__(placeholder=text)
        self._text = text

    def __str__(self) -> str:
        return self._text

    __repr__ = __str__


def safe_args(msg: object, args: LogArgs, scrub: Scrub) -> LogArgs:
    """A record's *args*, each made safe."""
    if isinstance(args, Mapping):
        if isinstance(msg, str) and "%(" in msg:
            return {key: safe_arg(item, scrub) for key, item in args.items()}
        # A lone mapping argument that the message does not index by name
        # is rendered whole: it is an object, not named arguments.
        return _MappingPlaceholder(placeholder(args))
    return tuple(safe_arg(item, scrub) for item in args)


def arg_values(args: LogArgs | None) -> list[object]:
    """The values among a record's *args*."""
    if args is None:
        return []
    if isinstance(args, Mapping):
        return list(args.values())
    return list(args)


__all__ = [
    "MAX_CHAIN",
    "MAX_GROUP_DEPTH",
    "WITHHELD_MESSAGE",
    "LogArgs",
    "Scrub",
    "arg_values",
    "exception_message",
    "exception_text",
    "linked",
    "safe_arg",
    "safe_args",
    "type_name",
]
