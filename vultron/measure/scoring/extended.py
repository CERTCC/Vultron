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

"""The extended desiderata, scored in their scopes (ADR-0182, ADR-0200).

Each extended desideratum of ``process_model_desiderata.md``
(:data:`vultron.measure.baselines.EXTENDED`) is scored in the scope it
states (ADR-0200 rule 2):

* **Each vendor** (:func:`vendor_scope`): a one-vendor desideratum that
  names the vendor's own events and is not multi-party, so the
  report-handling desiderata and ``F_i ≺ Ex_own``.
* **The embargo group** (:func:`embargo_scope`): the embargo desiderata that
  name only the case's events, ``E`` and ``Ex_own`` before ``P``, ``X`` and
  ``A``.
* **The multi-party group** (:func:`multi_party_scope`): ``F_i ≺ P`` for
  each vendor, against the one-vendor model, and ``V_i ≺ F_j`` for each
  ordered pair of vendors, against the two-vendor model.

A desideratum the record has settled is met or not; one it has not is met
with the probability the walk gives it from where the case stands
(:class:`~vultron.measure.baselines.StartedAt`, ADR-0182 rule 3).  A
scoping event that has not yet occurred must still occur for the
desideratum to count.  Each term adds its weight ``1 - f_d`` when met, as
the twelve original desiderata do (:func:`.history_score`).

Every walk reads one vendor, or one pair, never all of them: the vendors'
events are never combined into one sequence (CEH-05-006).  The embargo
group's walk needs a vendor in the one-vendor model too; it takes the case's
first vendor to become aware, as a two-party case has its one vendor, or a
vendor not yet aware when the case has none.
"""

from collections.abc import Callable, Iterable, Sequence
from fractions import Fraction
from functools import cache
from itertools import permutations

from vultron.measure.baselines import (
    EXTENDED,
    ONE_VENDOR_MODEL,
    TWO_VENDOR_MODEL,
    Desideratum,
    Event,
    EventKind,
    Group,
    JointModel,
    JointState,
    ModelName,
    Ordering,
    OrderingQuery,
    StartedAt,
    baseline,
    frequency,
    reachable_ends,
)
from vultron.measure.scoring.model import (
    ScopeScore,
    TermScore,
    UnscoredScope,
    WalkScore,
)
from vultron.measure.scoring.record import (
    UNAWARE,
    CaseRecord,
    NotAJointStateError,
)

_NEVER = Event(EventKind.V, 0)
"""An event no step emits: no joint model has a vendor 0.

``g ≺ _NEVER`` holds exactly when ``g`` occurs, so a scoping event that has
not yet occurred becomes one more ordering of the walk's query.
"""


def _names_a_vendor(desideratum: Desideratum) -> bool:
    return any(e.vendor is not None for e in desideratum.query.watched)


VENDOR_DESIDERATA: tuple[Desideratum, ...] = tuple(
    d
    for d in EXTENDED
    if d.model is ModelName.ONE_VENDOR
    and d.group is not Group.MULTI_PARTY
    and _names_a_vendor(d)
)
"""The extended desiderata scored in each vendor's own scope."""

EMBARGO_DESIDERATA: tuple[Desideratum, ...] = tuple(
    d for d in EXTENDED if d.group is Group.EMBARGO and not _names_a_vendor(d)
)
"""The extended desiderata of the case-wide embargo group."""

MULTI_PARTY_DESIDERATA: tuple[Desideratum, ...] = tuple(
    d for d in EXTENDED if d.group is Group.MULTI_PARTY
)
"""The extended desiderata of the case-wide multi-party group."""

_MODELS: dict[ModelName, JointModel] = {
    ModelName.ONE_VENDOR: ONE_VENDOR_MODEL,
    ModelName.TWO_VENDOR: TWO_VENDOR_MODEL,
}


def _holds(
    ordering: Ordering[Event], at: Callable[[Event], int | None]
) -> bool:
    """Whether the record meets *ordering*, given each event's position.

    ``a ≺ b`` holds when ``a`` occurred strictly before ``b``, or ``a``
    occurred and ``b`` did not, as in the walk.
    """
    before, after = at(ordering.before), at(ordering.after)
    return before is not None and (after is None or before < after)


def _remaining(
    desideratum: Desideratum, at: Callable[[Event], int | None]
) -> OrderingQuery[Event] | None:
    """What the walk must still do for *desideratum* to be met.

    ``None`` when the record already fails it.  A settled ordering drops
    out; an open one stays; a scoping event not yet occurred becomes an
    ordering before :data:`_NEVER`.  An empty query is already met.
    """
    open_orderings: list[Ordering[Event]] = []
    for ordering in desideratum.query.orderings:
        if at(ordering.before) is None and at(ordering.after) is None:
            open_orderings.append(ordering)
        elif not _holds(ordering, at):
            return None
    pending = [
        Ordering(event, _NEVER)
        for event in sorted(desideratum.query.given, key=str)
        if at(event) is None
    ]
    return OrderingQuery((*open_orderings, *pending))


@cache
def _chance(
    model: JointModel, state: JointState, query: OrderingQuery[Event]
) -> Fraction:
    """The probability *query* holds on the walk from *state*."""
    if not query.orderings:
        return Fraction(1)
    return frequency(StartedAt(model, state), query)


@cache
def _ends(
    model: JointModel, state: JointState, query: OrderingQuery[Event]
) -> frozenset[frozenset[int]]:
    return reachable_ends(StartedAt(model, state), query)


def _walk(
    record: CaseRecord,
    paths: tuple[str, ...] | None,
    desiderata: Sequence[Desideratum],
    vendors: tuple[str, ...],
) -> WalkScore:
    """Score *desiderata* for *vendors* on one walk from where the case stands.

    The walk's vendor slots hold *paths*' vendors, or, when *paths* is
    ``None``, one vendor not yet aware.  Every desideratum takes the same
    model, the one each of them names.

    Raises:
        NotAJointStateError: the case stands in no state of the model.
    """
    (model,) = {_MODELS[d.model] for d in desiderata}
    state = record.state(
        (UNAWARE,)
        if paths is None
        else tuple(record.path(vendor) for vendor in paths)
    )

    def at(event: Event) -> int | None:
        return record.position(event, vendors)

    scored: list[TermScore] = []
    certain = Fraction(0)
    joined: list[Ordering[Event]] = []
    spans: list[tuple[Fraction, range]] = []
    for desideratum in desiderata:
        weight = 1 - baseline(desideratum)
        remaining = _remaining(desideratum, at)
        scored.append(
            TermScore(
                notation=desideratum.notation,
                group=desideratum.group,
                vendors=vendors,
                weight=weight,
                met=(
                    Fraction(0)
                    if remaining is None
                    else _chance(model, state, remaining)
                ),
            )
        )
        if remaining is None:
            continue
        if not remaining.orderings:
            certain += weight
            continue
        start = len(joined)
        joined.extend(remaining.orderings)
        spans.append((weight, range(start, len(joined))))
    ends = (
        _ends(model, state, OrderingQuery(tuple(joined)))
        if joined
        else frozenset({frozenset[int]()})
    )
    outcomes = [
        certain
        + sum(
            (w for w, span in spans if all(i in end for i in span)),
            Fraction(0),
        )
        for end in ends
    ]
    return WalkScore(
        terms=tuple(scored), best=max(outcomes), worst=min(outcomes)
    )


def _scope(
    walks: Callable[[], Iterable[WalkScore]],
) -> ScopeScore | UnscoredScope:
    """The scope *walks* score, or why the case cannot be walked from."""
    try:
        return ScopeScore(walks=tuple(walks()))
    except NotAJointStateError as exc:
        return UnscoredScope(reason=str(exc))


def vendor_scope(
    record: CaseRecord, vendor: str
) -> ScopeScore | UnscoredScope:
    """*vendor*'s extended desiderata, on the one-vendor walk from its state.

    Raises:
        KeyError: *record* did not read *vendor*.
    """
    record.path(vendor)
    return _scope(
        lambda: [_walk(record, (vendor,), VENDOR_DESIDERATA, (vendor,))]
    )


def embargo_scope(record: CaseRecord) -> ScopeScore | UnscoredScope:
    """The case's embargo group, on one one-vendor walk.

    The vendor slot holds the case's first vendor to become aware, or a
    vendor not yet aware when the case has none.
    """
    first = record.vendors[:1] or None
    return _scope(lambda: [_walk(record, first, EMBARGO_DESIDERATA, ())])


def _multi_party_walks(record: CaseRecord) -> Iterable[WalkScore]:
    for desideratum in MULTI_PARTY_DESIDERATA:
        if desideratum.model is ModelName.TWO_VENDOR:
            for pair in permutations(record.vendors, 2):
                yield _walk(record, pair, (desideratum,), pair)
            continue
        for vendor in record.vendors:
            yield _walk(record, (vendor,), (desideratum,), (vendor,))


def multi_party_scope(
    record: CaseRecord,
) -> ScopeScore | UnscoredScope | None:
    """The case's multi-party group, one walk per vendor and per pair.

    ``None`` when the case has no vendor, so no multi-party desideratum
    applies.  A two-vendor desideratum is walked for each ordered pair of
    vendors, vendor 1 the one whose report must reach Valid.
    """
    if not record.vendors:
        return None
    return _scope(lambda: _multi_party_walks(record))
