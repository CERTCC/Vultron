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

"""Why an embargo ended: the *what* and the *why* of a termination (ADR-0122).

A termination has two parts:

- **What** — :class:`~vultron.core.states.embargo_register.TerminationReason`,
  ``END_TIME_REACHED`` or ``EARLY``.  It travels on the wire as the
  termination ``Remove``'s ``content`` and is checked at the parse edge.
- **Why** — a structured :data:`TerminationCause`, recorded on the
  ``TERMINATED`` register entry beside the what.  The one cause defined so
  far is :class:`ThreatSignalCause`, naming the CS signals (``P``, ``X``,
  ``A``) that ended the embargo early.  Other early causes stay open-ended:
  :data:`TerminationCause` grows into a union discriminated on ``kind``.
  ``cause`` is ``None`` when no structured cause is recorded — an end-time
  termination, a participant's own early decision, or a replica that has
  learned only the what from the ``Remove`` (until #4294 copies whole
  register entries).

:func:`end_time_violations` is the end-time rule every node applies before
an ``END_TIME_REACHED`` termination: it is refused when it is claimed before
the embargo's end time.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.core.states.cs import CS_pxa
from vultron.core.states.embargo_register import TerminationReason


class ThreatSignal(StrEnum):
    """A CS signal that ends an embargo early (EMB-07, RSH-03-001)."""

    #: The public is aware of the vulnerability.
    P = "P"
    #: An exploit is public.
    X = "X"
    #: Attacks have been observed.
    A = "A"


def threat_signals_of(pxa: CS_pxa) -> list[ThreatSignal]:
    """The threat signals *pxa* carries, in ``P``, ``X``, ``A`` order.

    Empty for ``pxa``: no signal is set.
    """
    return [ThreatSignal(letter) for letter in pxa.name if letter.isupper()]


class TerminationCauseKind(StrEnum):
    """The kinds of structured cause a termination may record."""

    THREAT_SIGNAL = "THREAT_SIGNAL"


_FROZEN = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
    frozen=True,
)


class ThreatSignalCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo ended early because the case carries P, X or A."""

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.THREAT_SIGNAL] = (
        TerminationCauseKind.THREAT_SIGNAL
    )
    #: The signals set when the embargo ended, in ``P``, ``X``, ``A`` order.
    signals: list[ThreatSignal] = Field(min_length=1)

    @model_validator(mode="after")
    def _signals_are_distinct_and_ordered(self) -> "ThreatSignalCause":
        """Refuse a repeated or out-of-order signal, so one cause has one form."""
        order = list(ThreatSignal)
        expected = sorted(set(self.signals), key=order.index)
        if self.signals != expected:
            raise ValueError(
                f"threat signals {[str(s) for s in self.signals]} must be"
                f" distinct and in P, X, A order ({[str(s) for s in expected]})"
            )
        return self


#: The structured why of a termination.  A single cause today; a new cause is
#: a new model with its own ``kind`` literal, and this becomes a union
#: discriminated on ``kind``.
TerminationCause = ThreatSignalCause

#: The causes each what admits.  A threat signal ends an embargo before its
#: end time, so it is always ``EARLY``.
_CAUSE_KINDS_BY_REASON: dict[TerminationReason, frozenset[str]] = {
    TerminationReason.END_TIME_REACHED: frozenset(),
    TerminationReason.EARLY: frozenset({TerminationCauseKind.THREAT_SIGNAL}),
}


class EmbargoTermination(ValidatedAssignmentMixin, BaseModel):
    """How one embargo ended: the what, and the why when it is recorded."""

    model_config = _FROZEN

    reason: TerminationReason
    cause: TerminationCause | None = None

    @model_validator(mode="after")
    def _cause_fits_reason(self) -> "EmbargoTermination":
        """Refuse a cause the what cannot have (EH-07-001)."""
        if (
            self.cause is not None
            and self.cause.kind not in _CAUSE_KINDS_BY_REASON[self.reason]
        ):
            raise ValueError(
                f"a {self.reason} termination cannot have a"
                f" {self.cause.kind} cause"
            )
        return self

    @classmethod
    def early(cls) -> "EmbargoTermination":
        """An early termination with no structured cause recorded."""
        return cls(reason=TerminationReason.EARLY)

    @classmethod
    def end_time_reached(cls) -> "EmbargoTermination":
        """The embargo reached its end time."""
        return cls(reason=TerminationReason.END_TIME_REACHED)

    @classmethod
    def threat(cls, signals: list[ThreatSignal]) -> "EmbargoTermination":
        """An early termination caused by the threat *signals*."""
        return cls(
            reason=TerminationReason.EARLY,
            cause=ThreatSignalCause(signals=signals),
        )

    @classmethod
    def from_reason(cls, reason: TerminationReason) -> "EmbargoTermination":
        """The termination a ``Remove`` carrying *reason* tells its receiver.

        The ``Remove`` carries only the what, so no cause is recorded.
        """
        return cls(reason=reason)


class ThreatSignalTermination(ValidatedAssignmentMixin, BaseModel):
    """A threat-signal termination, its signals given or read at the write.

    A CS cascade reacting to a status names the signals that status carries.
    One that builds its terminate tree before it knows them leaves
    ``signals`` unset, and :meth:`resolve` reads them from the case's PXA
    state at the write.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: The signals that ended the embargo; ``None`` (distinct from any list,
    #: which must name at least one) reads them from the case at the write.
    signals: list[ThreatSignal] | None = None

    @model_validator(mode="after")
    def _signals_form_a_cause(self) -> "ThreatSignalTermination":
        """Refuse given signals no :class:`ThreatSignalCause` would accept."""
        if self.signals is not None:
            ThreatSignalCause(signals=self.signals)
        return self

    @property
    def reason(self) -> TerminationReason:
        """The what: a threat signal ends an embargo early (ADR-0122)."""
        return TerminationReason.EARLY

    def resolve(self, pxa: CS_pxa) -> EmbargoTermination:
        """The termination this names, reading *pxa* when no signals are given.

        Raises:
            ValueError: no signal is given and *pxa* carries none, so nothing
                caused the termination this names.
        """
        signals = (
            self.signals
            if self.signals is not None
            else threat_signals_of(pxa)
        )
        if not signals:
            raise ValueError(
                "a threat-signal termination needs P, X or A set, but the"
                f" case is at {pxa.name}"
            )
        return EmbargoTermination.threat(signals)


#: What a terminate operation is given: the termination itself, or a threat
#: signal whose signals the case supplies at the write.
TerminationRequest = EmbargoTermination | ThreatSignalTermination


def has_reached_end_time(end_time: datetime, at: datetime) -> bool:
    """Whether an embargo ending at *end_time* has reached it at *at*.

    The one end-time rule: an embargo reaches its end time at that instant,
    not after it, so *at* equal to *end_time* counts (ADR-0122).
    """
    return at >= end_time


def end_time_violations(
    termination: EmbargoTermination,
    *,
    end_time: datetime,
    at: datetime | None,
) -> list[str]:
    """Why *termination* may not be applied at *at*, given *end_time*.

    An ``END_TIME_REACHED`` termination claimed before the embargo's end
    time is refused (ADR-0122); it needs the time it is claimed at.  An
    ``EARLY`` one has no time rule.  An empty list means it may be applied.
    """
    if termination.reason != TerminationReason.END_TIME_REACHED:
        return []
    if at is None:
        return [
            "an END_TIME_REACHED termination needs the time it was claimed at"
        ]
    if not has_reached_end_time(end_time, at):
        return [
            f"END_TIME_REACHED claimed at {at.isoformat()}, before the"
            f" embargo's end time {end_time.isoformat()}"
        ]
    return []


__all__ = [
    "EmbargoTermination",
    "TerminationCause",
    "TerminationCauseKind",
    "ThreatSignal",
    "ThreatSignalCause",
    "ThreatSignalTermination",
    "TerminationRequest",
    "end_time_violations",
    "has_reached_end_time",
    "threat_signals_of",
]
