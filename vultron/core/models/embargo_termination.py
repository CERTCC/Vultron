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

"""Why an embargo ended: a termination's structured cause (ADR-0122, ADR-0203).

A termination is its cause, a union discriminated on ``kind`` (EMB-13-010):

- :class:`EndTimeReachedCause` — the embargo reached its end time;
- :class:`ThreatSignalCause` — the CS signals (``P``, ``X``, ``A``) that
  ended the embargo; only the CASE_MANAGER names it;
- :class:`FixReadyCause` — the vendors whose fix readiness made the quorum
  (VP-09-007);
- :class:`FixDeployedCause` — the fix is deployed;
- :class:`OtherCause` — anything else; the ``Remove``'s ``summary`` gives
  the account.

End time reached is a cause like the others, so no separate
``END_TIME_REACHED``/``EARLY`` value travels beside it (ADR-0203): every
cause but :class:`EndTimeReachedCause` ends an embargo before its end time.
The stored termination always names its cause: a ``Remove`` whose sender
named none records ``OTHER`` (:meth:`EmbargoTermination.from_cause`).  The
termination ``Remove`` carries the cause as ``terminationCause``, checked at
the parse edge (EMB-13-005).  A replica copies the cause from the ledger
entry and never works it out itself.  The termination is stored on the
terminated embargo itself (ADR-0202).

:func:`end_time_violations` is the end-time rule every node applies before
an end-time termination: it is refused when it is claimed before the
embargo's end time.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import (
    PropertyValueKind,
    ValidatedAssignmentMixin,
    vultron_property,
)
from vultron.core.states.cs import CS_pxa
from vultron.primitives import NonEmptyString, NormalisedActorId


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
    """The kinds of structured cause a termination records."""

    #: The embargo reached its end time (EMB-13-003).
    END_TIME_REACHED = "END_TIME_REACHED"
    #: The case carries P, X or A; only the CASE_MANAGER names it.
    THREAT_SIGNAL = "THREAT_SIGNAL"
    #: A quorum of vendors is fix-ready (VP-09-007).
    FIX_READY = "FIX_READY"
    #: The fix is deployed.
    FIX_DEPLOYED = "FIX_DEPLOYED"
    #: Anything else; the ``Remove``'s ``summary`` gives the account.
    OTHER = "OTHER"


#: The cause kinds only the CASE_MANAGER may name on a ``Remove``.  A
#: threat signal ends an embargo through a case status update setting
#: ``P``, ``X`` or ``A``, after which the CASE_MANAGER terminates it with the
#: signals the case carries (EMB-13-005).
CASE_MANAGER_ONLY_CAUSE_KINDS: frozenset[TerminationCauseKind] = frozenset(
    {TerminationCauseKind.THREAT_SIGNAL}
)


_FROZEN = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
    frozen=True,
)


#: The Vultron property ``kind`` every termination cause carries, declared
#: once so the four causes give it one meaning (VM-10-012).
CAUSE_KIND_PROPERTY = vultron_property(
    "The kind of an embargo's termination cause: END_TIME_REACHED, "
    "THREAT_SIGNAL, FIX_READY, FIX_DEPLOYED or OTHER",
    PropertyValueKind.PLAIN,
)


class EndTimeReachedCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo reached its end time (EMB-13-003).

    The one cause that does not end an embargo early, so it is refused when
    claimed before the end time (EMB-13-008, :func:`end_time_violations`).
    """

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.END_TIME_REACHED] = Field(
        default=TerminationCauseKind.END_TIME_REACHED,
        json_schema_extra=CAUSE_KIND_PROPERTY,
    )


class ThreatSignalCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo ended early because the case carries P, X or A."""

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.THREAT_SIGNAL] = Field(
        default=TerminationCauseKind.THREAT_SIGNAL,
        json_schema_extra=CAUSE_KIND_PROPERTY,
    )
    #: The signals set when the embargo ended, in ``P``, ``X``, ``A`` order.
    signals: list[ThreatSignal] = Field(
        min_length=1,
        json_schema_extra=vultron_property(
            (
                "The threat signals (P, X, A) set on a case when its embargo "
                "ended"
            ),
            PropertyValueKind.SET,
        ),
    )

    @model_validator(mode="after")
    def _signals_are_distinct_and_ordered(self) -> ThreatSignalCause:
        """Refuse a repeated or out-of-order signal, so one cause has one form."""
        order = list(ThreatSignal)
        expected = sorted(set(self.signals), key=order.index)
        if self.signals != expected:
            raise ValueError(
                f"threat signals {[str(s) for s in self.signals]} must be"
                f" distinct and in P, X, A order ({[str(s) for s in expected]})"
            )
        return self


class FixReadyCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo ended early because a quorum of vendors is fix-ready.

    On a case owner's ``Remove`` it is the owner's claim, recorded as given:
    the CASE_MANAGER does not check that the vendors are fix-ready, because
    ending early on a quorum is the owner's judgment (EMB-13-005).
    """

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.FIX_READY] = Field(
        default=TerminationCauseKind.FIX_READY,
        json_schema_extra=CAUSE_KIND_PROPERTY,
    )
    #: The actor IDs of the vendors whose readiness made the quorum
    #: (VP-09-007); at least one, each named once, in its normalised
    #: spelling (OID-01-006), so one vendor has one form.
    vendors: list[NormalisedActorId] = Field(
        min_length=1,
        json_schema_extra=vultron_property(
            (
                "The ids of the vendors whose readiness to fix made the "
                "quorum that ended an embargo"
            ),
            PropertyValueKind.SET,
            items=PropertyValueKind.IRI,
        ),
    )

    @model_validator(mode="after")
    def _vendors_are_distinct(self) -> FixReadyCause:
        """Refuse a vendor named twice, so one quorum has one form."""
        repeated = sorted(
            {
                vendor
                for vendor in self.vendors
                if self.vendors.count(vendor) > 1
            }
        )
        if repeated:
            raise ValueError(
                f"a FIX_READY cause names each vendor once; {repeated}"
                " appear more than once"
            )
        return self


class FixDeployedCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo ended early because the fix is deployed."""

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.FIX_DEPLOYED] = Field(
        default=TerminationCauseKind.FIX_DEPLOYED,
        json_schema_extra=CAUSE_KIND_PROPERTY,
    )


class OtherCause(ValidatedAssignmentMixin, BaseModel):
    """The embargo ended early for a reason no other kind names.

    It carries no detail: the ``Remove``'s ``summary`` gives the account.
    """

    model_config = _FROZEN

    kind: Literal[TerminationCauseKind.OTHER] = Field(
        default=TerminationCauseKind.OTHER,
        json_schema_extra=CAUSE_KIND_PROPERTY,
    )


#: The structured why of a termination: one model per kind, discriminated on
#: ``kind`` (EMB-13-010).  A new cause is a new model with its own ``kind``
#: literal, added here.
TerminationCause = Annotated[
    EndTimeReachedCause
    | ThreatSignalCause
    | FixReadyCause
    | FixDeployedCause
    | OtherCause,
    Field(discriminator="kind"),
]


class EmbargoTermination(ValidatedAssignmentMixin, BaseModel):
    """How one embargo ended, stored on the embargo (ADR-0202, ADR-0203).

    ``cause`` is required: end time reached is a cause like the others, and
    an early end whose sender named no structured cause is ``OTHER``
    (:meth:`from_cause`).  ``caused_by`` is the id of the act that caused
    the end, when known, and ``summary`` the human reason, when given.
    """

    model_config = _FROZEN

    cause: TerminationCause = Field(
        json_schema_extra=vultron_property(
            (
                "Why an embargo ended: an object whose kind names the "
                "cause, END_TIME_REACHED included"
            ),
            PropertyValueKind.PLAIN,
        ),
    )
    caused_by: NonEmptyString | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            "The id of the act that caused an embargo to end, when known",
            PropertyValueKind.IRI,
        ),
    )
    #: The human reason the embargo ended, when one is given (ADR-0203).
    summary: NonEmptyString | None = None

    @property
    def is_end_time_reached(self) -> bool:
        """Whether the embargo ended at its end time, not early."""
        return self.cause.kind == TerminationCauseKind.END_TIME_REACHED

    @classmethod
    def from_cause(cls, cause: TerminationCause | None) -> EmbargoTermination:
        """The termination a ``Remove`` naming *cause* records.

        A ``Remove`` that names no structured cause ends the embargo early
        for a reason no other kind names, so it records ``OTHER``: the
        stored termination always names its cause kind (ADR-0202).
        """
        return cls(cause=cause if cause is not None else OtherCause())

    @classmethod
    def end_time_reached(cls) -> EmbargoTermination:
        """The embargo reached its end time."""
        return cls(cause=EndTimeReachedCause())

    @classmethod
    def threat(cls, signals: list[ThreatSignal]) -> EmbargoTermination:
        """An early termination caused by the threat *signals*."""
        return cls(cause=ThreatSignalCause(signals=signals))

    @classmethod
    def other(cls) -> EmbargoTermination:
        """An early termination for a reason no other kind names."""
        return cls(cause=OtherCause())

    @property
    def participant_cause(self) -> TerminationCause | None:
        """The cause a participant's ask for this termination may carry.

        The cause itself, unless only the CASE_MANAGER may name its kind
        (``THREAT_SIGNAL``): the CASE_MANAGER would refuse that ask, and it
        learns the signals from the case status update instead (EMB-13-005).
        """
        if self.cause.kind in CASE_MANAGER_ONLY_CAUSE_KINDS:
            return None
        return self.cause


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
    def _signals_form_a_cause(self) -> ThreatSignalTermination:
        """Refuse given signals no :class:`ThreatSignalCause` would accept."""
        if self.signals is not None:
            ThreatSignalCause(signals=self.signals)
        return self

    @property
    def participant_cause(self) -> None:
        """A participant's ask names no threat-signal cause (EMB-13-005).

        Only the CASE_MANAGER may name ``THREAT_SIGNAL``; it learns the
        signals from the case status update instead.
        """
        return None

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
    time is refused (EMB-13-008); it needs the time it is claimed at.  Every
    other cause ends an embargo early and has no time rule.  An empty list
    means it may be applied.
    """
    if not termination.is_end_time_reached:
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
    "CASE_MANAGER_ONLY_CAUSE_KINDS",
    "EmbargoTermination",
    "EndTimeReachedCause",
    "FixDeployedCause",
    "FixReadyCause",
    "OtherCause",
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
