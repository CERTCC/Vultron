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
states.  A scope is one vendor, or one case-wide desiderata group:

* **Each vendor** (:func:`vendor_scope`): a one-vendor desideratum that
  names the vendor's own events and is not multi-party, so the
  report-handling desiderata and ``F_i ≺ Ex_own``.  A vendor is a
  participant with a projected sequence (CEH-05-001); a vendor not yet
  aware of the vul has no events to read and no scope here.
* **The embargo group** (:func:`embargo_scope`): the embargo desiderata that
  name only the case's events, ``E`` and ``Ex_own`` before ``P``, ``X`` and
  ``A``.
* **The multi-party group** (:func:`multi_party_scope`): ``F_i ≺ P`` for
  each vendor, against the one-vendor model, and ``V_i ≺ F_j`` for each
  ordered pair of vendors, against the two-vendor model.

A scope counts each group of equivalent desiderata once
(:func:`scope_desiderata`): an embargo starts, and ends on its own terms,
only before all of ``P``, ``X`` and ``A``, so ``E ≺ P``, ``E ≺ X`` and
``E ≺ A`` are one desideratum, and so are the three ``Ex_own`` ones
(``process_model_desiderata.md`` § "The desiderata are not independent").

A desideratum the record has settled is met or not; one it has not is met
with the probability the walk gives it from where the case stands, the way
an incomplete case-state sequence is scored through its completions
(ADR-0182).  The case's record is the walk's history
(:class:`~vultron.measure.baselines.WalkPrefix`), and the chance comes from
the desideratum's solved table
(:meth:`~vultron.measure.baselines.ChanceValues.reading`).  Each term adds
its weight ``1 - f_d`` times its expected outcome
(:func:`~vultron.measure.baselines.expected_outcome`), in which a scope the
case never enters counts as met: a report that never reaches Valid does not
lose the desiderata scoped to Valid reports, because not taking a path that
needs a desideratum is not failing it.  The best and worst count it the same
way, at each end the walk can still reach.

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
from typing import NamedTuple

from vultron.measure.baselines import (
    EXTENDED,
    ONE_VENDOR_MODEL,
    TWO_VENDOR_MODEL,
    Desideratum,
    Event,
    Group,
    JointModel,
    ModelName,
    OrderingQuery,
    WalkPrefix,
    baseline,
    implications,
    reachable_ends,
)
from vultron.measure.baselines.desiderata import joint_values
from vultron.measure.baselines.values import CasePrefix
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


def _names_a_vendor(desideratum: Desideratum) -> bool:
    return any(e.vendor is not None for e in desideratum.query.watched)


class ScopeDesiderata(NamedTuple):
    """The extended desiderata of each kind of scope, in catalog order."""

    vendor: tuple[Desideratum, ...]
    """Scored in each vendor's own scope."""
    embargo: tuple[Desideratum, ...]
    """The case-wide embargo group."""
    multi_party: tuple[Desideratum, ...]
    """The case-wide multi-party group."""


def _count_once(
    desiderata: Iterable[Desideratum],
) -> tuple[Desideratum, ...]:
    """*desiderata* less each one equivalent to one listed before it."""
    equivalent = {
        frozenset((i.stronger, i.weaker))
        for i in implications()
        if i.equivalent
    }
    kept: list[Desideratum] = []
    for desideratum in desiderata:
        if all(frozenset((k, desideratum)) not in equivalent for k in kept):
            kept.append(desideratum)
    return tuple(kept)


@cache
def scope_desiderata() -> ScopeDesiderata:
    """The extended desiderata each kind of scope scores, each group of
    equivalent ones once.

    Computed on first use: finding the equivalent pairs walks the model.
    """
    return ScopeDesiderata(
        vendor=_count_once(
            d
            for d in EXTENDED
            if d.model is ModelName.ONE_VENDOR
            and d.group is not Group.MULTI_PARTY
            and _names_a_vendor(d)
        ),
        embargo=_count_once(
            d
            for d in EXTENDED
            if d.group is Group.EMBARGO and not _names_a_vendor(d)
        ),
        multi_party=_count_once(
            d for d in EXTENDED if d.group is Group.MULTI_PARTY
        ),
    )


_MODELS: dict[ModelName, JointModel] = {
    ModelName.ONE_VENDOR: ONE_VENDOR_MODEL,
    ModelName.TWO_VENDOR: TWO_VENDOR_MODEL,
}


def _history(
    record: CaseRecord,
    events: Iterable[Event],
    vendors: tuple[str, ...],
) -> tuple[frozenset[Event], ...]:
    """*events* the record holds, as the walk's history: one entry per
    position, in order, so events of one ledger entry are simultaneous."""
    by_position: dict[int, set[Event]] = {}
    for event in events:
        position = record.position(event, vendors)
        if position is not None:
            by_position.setdefault(position, set()).add(event)
    return tuple(frozenset(by_position[p]) for p in sorted(by_position))


@cache
def _ends(
    model: JointModel, query: OrderingQuery[Event], prefix: CasePrefix
) -> frozenset[tuple[frozenset[Event], frozenset[int]]]:
    return reachable_ends(model, query, prefix)


def _walk(
    record: CaseRecord,
    paths: tuple[str, ...] | None,
    desiderata: Sequence[Desideratum],
    vendors: tuple[str, ...],
) -> WalkScore:
    """Score *desiderata* for *vendors* on one walk from where the case stands.

    The walk's vendor slots hold *paths*' vendors, or, when *paths* is
    ``None``, one vendor not yet aware.  Every desideratum takes the same
    model, the one each of them names.  The case's record is the walk's
    history, so an ordering it already settles stays settled.

    Raises:
        NotAJointStateError: the case stands in no state of the model.
    """
    (name,) = {d.model for d in desiderata}
    model = _MODELS[name]
    state = record.state(
        (UNAWARE,)
        if paths is None
        else tuple(record.path(vendor) for vendor in paths)
    )
    joined = OrderingQuery(
        tuple(o for d in desiderata for o in d.query.orderings),
        frozenset().union(*(d.query.given for d in desiderata)),
    )
    prefix: CasePrefix = WalkPrefix(
        state, _history(record, joined.watched, vendors)
    )
    scored: list[TermScore] = []
    spans: list[tuple[Fraction, frozenset[Event], range]] = []
    start = 0
    for desideratum in desiderata:
        weight = 1 - baseline(desideratum)
        reading = joint_values(name, desideratum.query).reading(prefix)
        scored.append(
            TermScore(
                notation=desideratum.notation,
                group=desideratum.group,
                vendors=vendors,
                weight=weight,
                met=reading.outcome,
            )
        )
        count = len(desideratum.query.orderings)
        spans.append(
            (weight, desideratum.query.given, range(start, start + count))
        )
        start += count
    outcomes = [
        sum(
            (
                weight
                for weight, given, span in spans
                if not given <= seen or all(i in met for i in span)
            ),
            Fraction(0),
        )
        for seen, met in _ends(model, joined, prefix)
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
        lambda: [
            _walk(record, (vendor,), scope_desiderata().vendor, (vendor,))
        ]
    )


def embargo_scope(record: CaseRecord) -> ScopeScore | UnscoredScope:
    """The case's embargo group, on one one-vendor walk.

    The vendor slot holds the case's first vendor to become aware, or a
    vendor not yet aware when the case has none.
    """
    first = record.vendors[:1] or None
    return _scope(
        lambda: [_walk(record, first, scope_desiderata().embargo, ())]
    )


def _multi_party_walks(record: CaseRecord) -> Iterable[WalkScore]:
    for desideratum in scope_desiderata().multi_party:
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
