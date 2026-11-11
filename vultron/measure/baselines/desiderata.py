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

"""The desiderata, each with the smallest model that holds it, and their baselines.

Every ordering desideratum of ``docs/topics/measuring_cvd/process_model_desiderata.md``
is one :class:`Desideratum`: the ordering, the events that scope it, and the
model it takes chance from (ADR-0182 decision 2):

* the twelve original desiderata use the six-event case-state model;
* a desideratum about one vendor, the case's shared events or the embargo
  uses the one-vendor joint model, so a desideratum that must hold for every
  vendor is scored per vendor against it;
* the one desideratum that relates two vendors uses the two-vendor model.

:func:`baseline` computes a desideratum's chance frequency exactly, and
:func:`implications` finds every pair in which one desideratum implies another,
by search over the model rather than by argument.
"""

from collections.abc import Iterable
from enum import StrEnum
from fractions import Fraction
from functools import cache
from typing import NamedTuple

from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.baselines.case_state import CASE_STATE_MODEL
from vultron.measure.baselines.joint import (
    ONE_VENDOR_MODEL,
    TWO_VENDOR_MODEL,
    Event,
    EventKind,
)
from vultron.measure.baselines.walk import (
    Ordering,
    OrderingQuery,
    frequency,
    implies,
)

NEAR_EQUAL_RATIO = Fraction(9, 10)
"""A pair is flagged when the stronger desideratum keeps this share of the weaker's chance.

When one desideratum implies another, the ratio of their baselines is the
chance that a history meeting the weaker also meets the stronger.  At or above
this share, the skill score's ``-log(f_d)`` terms count nearly the same
histories, and so nearly the same skill, twice.
"""


class ModelName(StrEnum):
    """The models a baseline is taken from."""

    CASE_STATE = "six-event case state"
    ONE_VENDOR = "one vendor"
    TWO_VENDOR = "two vendors"


type Query = OrderingQuery[Event]
"""A query over the joint models' events.

An original desideratum is stated in the same events, for vendor 1; its
six-event query maps each back to its :class:`CSEvent`.
"""


class Group(StrEnum):
    """The groups of ``process_model_desiderata.md`` § "Summary"."""

    ORIGINAL = "Original"
    EMBARGO = "Embargo"
    REPORT_HANDLING = "Report handling"
    MULTI_PARTY = "Multi-party"


class Desideratum(NamedTuple):
    """One ordering desideratum and the model its baseline comes from.

    ``notation`` is the page's LaTeX, using its event macros; ``scope`` says
    which cases or vendors the desideratum is measured over, empty when it is
    every case.
    """

    notation: str
    group: Group
    model: ModelName
    query: Query
    scope: str = ""


def _vendor(kind: EventKind, number: int = 1) -> Event:
    return Event(kind, number)


def _case(kind: EventKind) -> Event:
    return Event(kind)


def _one(before: Event, after: Event, given: Iterable[Event] = ()) -> Query:
    return OrderingQuery((Ordering(before, after),), frozenset(given))


_K = EventKind
_V, _F, _D = _vendor(_K.V), _vendor(_K.F), _vendor(_K.D)
_VA, _AC = _vendor(_K.VALIDATED), _vendor(_K.ACCEPTED)
_P, _X, _A = _case(_K.P), _case(_K.X), _case(_K.A)
_E, _EX_OWN = _case(_K.EMBARGO_START), _case(_K.EXIT_OWN_TERMS)

_CS_TO_JOINT: dict[CSEvent, Event] = {
    CSEvent.V: _V,
    CSEvent.F: _F,
    CSEvent.D: _D,
    CSEvent.P: _P,
    CSEvent.X: _X,
    CSEvent.A: _A,
}

_ORIGINAL_ORDER: tuple[tuple[CSEvent, CSEvent], ...] = tuple(
    (CSEvent(a), CSEvent(b))
    for a, b in (
        "DP",
        "FP",
        "DX",
        "DA",
        "FX",
        "VP",
        "FA",
        "PX",
        "XA",
        "PA",
        "VX",
        "VA",
    )
)
"""The twelve original desiderata, most desirable first (``twelve_desiderata.md``)."""


_JOINT_TO_CS: dict[Event, CSEvent] = {v: k for k, v in _CS_TO_JOINT.items()}


def _symbol(event: CSEvent) -> str:
    return rf"\ev{event.value}"


ORIGINAL: tuple[Desideratum, ...] = tuple(
    Desideratum(
        rf"${_symbol(a)} \prec {_symbol(b)}$",
        Group.ORIGINAL,
        ModelName.CASE_STATE,
        _one(_CS_TO_JOINT[a], _CS_TO_JOINT[b]),
    )
    for a, b in _ORIGINAL_ORDER
)
"""The twelve original desiderata over the six-event model."""

_VALID = "vendors whose report reaches Valid"
_EVERY_VENDOR = "every vendor, each scored alone"

EXTENDED: tuple[Desideratum, ...] = (
    Desideratum(
        r"$\evE \prec \evP$", Group.EMBARGO, ModelName.ONE_VENDOR, _one(_E, _P)
    ),
    Desideratum(
        r"$\evE \prec \evX$", Group.EMBARGO, ModelName.ONE_VENDOR, _one(_E, _X)
    ),
    Desideratum(
        r"$\evE \prec \evA$", Group.EMBARGO, ModelName.ONE_VENDOR, _one(_E, _A)
    ),
    Desideratum(
        r"$\evExOwn \prec \evP$",
        Group.EMBARGO,
        ModelName.ONE_VENDOR,
        _one(_EX_OWN, _P),
    ),
    Desideratum(
        r"$\evExOwn \prec \evX$",
        Group.EMBARGO,
        ModelName.ONE_VENDOR,
        _one(_EX_OWN, _X),
    ),
    Desideratum(
        r"$\evExOwn \prec \evA$",
        Group.EMBARGO,
        ModelName.ONE_VENDOR,
        _one(_EX_OWN, _A),
    ),
    Desideratum(
        r"$\evF_i \prec \evExOwn$",
        Group.EMBARGO,
        ModelName.ONE_VENDOR,
        _one(_F, _EX_OWN, [_EX_OWN]),
        "every vendor, each scored alone, in cases whose embargo ends on its"
        " own terms",
    ),
    Desideratum(
        r"$\evAc_i \prec \evP$",
        Group.REPORT_HANDLING,
        ModelName.ONE_VENDOR,
        _one(_AC, _P, [_VA]),
        _VALID,
    ),
    Desideratum(
        r"$\evAc_i \prec \evX$",
        Group.REPORT_HANDLING,
        ModelName.ONE_VENDOR,
        _one(_AC, _X, [_VA]),
        _VALID,
    ),
    Desideratum(
        r"$\evAc_i \prec \evA$",
        Group.REPORT_HANDLING,
        ModelName.ONE_VENDOR,
        _one(_AC, _A, [_VA]),
        _VALID,
    ),
    Desideratum(
        r"$\evVa_i \prec \evP$",
        Group.REPORT_HANDLING,
        ModelName.ONE_VENDOR,
        _one(_VA, _P, [_VA]),
        _VALID,
    ),
    Desideratum(
        r"$\evAc_i \prec \evF_i$",
        Group.REPORT_HANDLING,
        ModelName.ONE_VENDOR,
        _one(_AC, _F),
        _EVERY_VENDOR,
    ),
    Desideratum(
        r"$\evV_i \prec \evF_j$",
        Group.MULTI_PARTY,
        ModelName.TWO_VENDOR,
        _one(_vendor(_K.V, 1), _vendor(_K.F, 2), [_vendor(_K.VALIDATED, 1)]),
        "vendor $i$ whose report reaches Valid, and every other vendor $j$",
    ),
    Desideratum(
        r"$\evF_i \prec \evP$",
        Group.MULTI_PARTY,
        ModelName.ONE_VENDOR,
        _one(_F, _P),
        _EVERY_VENDOR,
    ),
)
"""The extended desiderata of ``process_model_desiderata.md``, in page order."""


def _in_case_state_model(query: Query) -> OrderingQuery[CSEvent]:
    """*query* restated over the six-event model's events."""
    return OrderingQuery(
        tuple(
            Ordering(_JOINT_TO_CS[o.before], _JOINT_TO_CS[o.after])
            for o in query.orderings
        ),
        frozenset(_JOINT_TO_CS[e] for e in query.given),
    )


@cache
def _frequency(model: ModelName, query: Query) -> Fraction:
    if model is ModelName.CASE_STATE:
        return frequency(CASE_STATE_MODEL, _in_case_state_model(query))
    if model is ModelName.ONE_VENDOR:
        return frequency(ONE_VENDOR_MODEL, query)
    return frequency(TWO_VENDOR_MODEL, query)


def baseline(desideratum: Desideratum) -> Fraction:
    """The exact chance frequency ``f_d`` of *desideratum* in its own model."""
    return _frequency(desideratum.model, desideratum.query)


def _in_one_vendor_model(desideratum: Desideratum) -> Query | None:
    """*desideratum* over the one-vendor model, or ``None`` if it relates two vendors."""
    if desideratum.model is ModelName.TWO_VENDOR:
        return None
    return desideratum.query


class Implication(NamedTuple):
    """*stronger* implies *weaker*: every history meeting the one meets the other.

    Both frequencies are taken in the one-vendor model among walks in which
    every scoping event of either desideratum occurs, so they compare: their
    ratio, :attr:`share`, is the chance that a history meeting the weaker also
    meets the stronger.  They differ from the desiderata's own baselines when
    the scopes or the models differ.
    """

    stronger: Desideratum
    weaker: Desideratum
    stronger_frequency: Fraction
    weaker_frequency: Fraction
    equivalent: bool

    @property
    def share(self) -> Fraction:
        return self.stronger_frequency / self.weaker_frequency

    @property
    def counts_twice(self) -> bool:
        """Whether the weaker adds almost nothing to the stronger (:data:`NEAR_EQUAL_RATIO`)."""
        return self.share >= NEAR_EQUAL_RATIO


def _scoped(query: Query, given: frozenset[Event]) -> Query:
    return OrderingQuery(query.orderings, query.given | given)


def _candidates() -> list[tuple[Desideratum, Query]]:
    """Every desideratum expressible over the one-vendor model, each query once.

    An original desideratum whose one-vendor restatement is an extended one
    (``F ≺ P`` and ``F_i ≺ P``) is left to the extended one.
    """
    found: list[tuple[Desideratum, Query]] = []
    for desideratum in (*EXTENDED, *ORIGINAL):
        query = _in_one_vendor_model(desideratum)
        if query is not None and all(query != q for _, q in found):
            found.append((desideratum, query))
    return found


@cache
def implications() -> tuple[Implication, ...]:
    """Every pair in which an extended desideratum implies another desideratum.

    The stronger side is an extended desideratum over the one-vendor model;
    the weaker side is any other desideratum expressible there, the twelve
    original ones restated for the one vendor included.  A pair is left out
    when the weaker always holds within the pair's scope, because it then
    implies nothing about skill, and an equivalent pair is listed once.  The
    two-vendor desideratum has no partner in its model.
    """
    candidates = _candidates()
    order = {d: i for i, (d, _) in enumerate(candidates)}
    found: list[Implication] = []
    for strong, strong_query in candidates:
        if strong.group is Group.ORIGINAL:
            continue
        for weak, weak_query in candidates:
            if weak is strong or not implies(
                ONE_VENDOR_MODEL, strong_query, weak_query
            ):
                continue
            equivalent = implies(ONE_VENDOR_MODEL, weak_query, strong_query)
            if (
                equivalent
                and weak.group is not Group.ORIGINAL
                and order[weak] < order[strong]
            ):
                continue
            given = strong_query.given | weak_query.given
            weak_f = _frequency(
                ModelName.ONE_VENDOR, _scoped(weak_query, given)
            )
            if weak_f == 1:
                continue
            strong_f = _frequency(
                ModelName.ONE_VENDOR, _scoped(strong_query, given)
            )
            found.append(
                Implication(strong, weak, strong_f, weak_f, equivalent)
            )
    return tuple(found)
