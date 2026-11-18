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

"""The case a shadow log record is about, set around the code that handles it.

:func:`case_log_context` names a case on every record its block makes;
:meth:`CaseLog.withhold` adds the case reading's content to withhold and
its tracker references to name.  An exception that leaves the block carries
the context with it (:func:`carried_context`), so a record made about it
after the block has ended is cleaned the same way.
"""

from __future__ import annotations

import re
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace

from vultron.core.models.case_reading import CaseReading
from vultron.errors import VultronError
from vultron.shadow.log_content.content import (
    longest_first,
    reading_content,
    tracker_references,
)

#: What a withheld piece of case content is replaced by.
WITHHELD = "[case content withheld]"

#: The exception attribute that carries a case context out of its block.
_CARRIED = "_vultron_case_log_context"


@dataclass(frozen=True)
class CaseLogContext:
    """The case being handled, as its log records name and withhold it.

    Attributes:
        case_id: The case id the shadow was asked for.
        references: The case's outside tracker references, in ledger order.
        content: The case content to withhold, longest first.
    """

    case_id: str
    references: tuple[str, ...] = ()
    content: tuple[str, ...] = ()
    _pattern: re.Pattern[str] | None = field(
        init=False, repr=False, compare=False, default=None
    )

    def __post_init__(self) -> None:
        # One alternation, longest piece first, compiled once per context
        # rather than once per record: at a position the regex takes the
        # first piece that matches, so a longer piece wins.
        if self.content:
            pattern = re.compile("|".join(map(re.escape, self.content)))
            object.__setattr__(self, "_pattern", pattern)

    def scrub(self, text: str) -> str:
        """*text* with every piece of this case's content withheld."""
        if self._pattern is None:
            return text
        return self._pattern.sub(WITHHELD, text)

    def joined(self, others: Iterable[CaseLogContext]) -> CaseLogContext:
        """This context's ids, withholding the content of *others* too."""
        extra = [other for other in others if other.content]
        if not extra:
            return self
        pieces = [*self.content]
        for other in extra:
            pieces += other.content
        return replace(self, content=longest_first(pieces))


_CASE: ContextVar[CaseLogContext | None] = ContextVar(
    "vultron_shadow_case_log", default=None
)


def current_case() -> CaseLogContext | None:
    """The case context the current code runs in, if any."""
    return _CASE.get()


def carried_context(exc: BaseException) -> CaseLogContext | None:
    """The case context *exc* carried out of its block, if any."""
    carried = getattr(exc, _CARRIED, None)
    return carried if isinstance(carried, CaseLogContext) else None


class CaseLog:
    """The handle :func:`case_log_context` yields for its case.

    Args:
        case_id: The case id the context names.
    """

    def __init__(self, case_id: str) -> None:
        self._case_id = case_id
        self._active = True

    def close(self) -> None:
        """End the handle: its block has ended."""
        self._active = False

    def withhold(self, reading: CaseReading) -> None:
        """Withhold *reading*'s content from the rest of the block's records.

        Also names the reading's tracker references on those records.

        Raises:
            VultronError: The handle's block has ended, so a context
                set now would never be reset.
        """
        if not self._active:
            raise VultronError(
                f"case log context for {self._case_id} has ended;"
                " withhold() must run inside its block"
            )
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
    handle = CaseLog(case_id)
    try:
        yield handle
    except BaseException as exc:
        context = _CASE.get()
        # The innermost context is the most specific; an outer one leaves
        # it in place.
        if context is not None and carried_context(exc) is None:
            setattr(exc, _CARRIED, context)
        raise
    finally:
        handle.close()
        _CASE.reset(token)


__all__ = [
    "WITHHELD",
    "CaseLog",
    "CaseLogContext",
    "carried_context",
    "case_log_context",
    "current_case",
]
