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

"""The extended desiderata, scored in each vendor's scope (ADR-0182, ADR-0200).

A scope is one vendor (ADR-0200 rule 1): there is no case-wide scope.  Each
extended desideratum of ``process_model_desiderata.md``
(:data:`vultron.measure.baselines.EXTENDED`) that the one-vendor model holds
is scored for every vendor, on that vendor's one-vendor walk, in one of two
parts (ADR-0200 rule 3):

* **The end part**: the report-handling desiderata.  The original twelve
  join it in :class:`~vultron.measure.scoring.model.VendorScore`.
* **The embargo part**: the embargo desiderata, ``E`` and ``Ex_own`` before
  ``P``, ``X`` and ``A``, and ``F_i ≺ Ex_own``.

The multi-party desiderata are left out.  ``F_i ≺ P`` is the original
twelve's ``F ≺ P`` for each vendor, which the vendor's score already counts,
and move advice does not use ``V_i ≺ F_j`` (ADR-0200 rule 1, #6502).

A part counts each group of equivalent desiderata once
(:func:`scope_desiderata`, through
:func:`~vultron.measure.baselines.desiderata.count_once`): an embargo starts, and ends on its own terms,
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

Every walk reads one vendor and the case's events, never another vendor's:
the vendors' events are never combined into one sequence (CEH-05-006).
"""

from collections.abc import Iterable, Sequence
from fractions import Fraction
from functools import cache
from typing import NamedTuple

from vultron.measure.baselines import (
    EXTENDED,
    Desideratum,
    Event,
    Group,
    JointModel,
    ModelName,
    OrderingQuery,
    WalkPrefix,
    case_model,
    reachable_ends,
)
from vultron.measure.baselines.desiderata import (
    count_once,
    joint_values,
    weight,
)
from vultron.measure.baselines.values import CasePrefix
from vultron.measure.scoring.model import (
    ExtendedScore,
    TermScore,
    UnscoredScope,
    WalkScore,
)
from vultron.measure.scoring.record import CaseRecord, NotAJointStateError


class ScopeDesiderata(NamedTuple):
    """The extended desiderata of a vendor's scope, by part, in catalog
    order."""

    end: tuple[Desideratum, ...]
    """The report-handling desiderata, scored in the end part."""
    embargo: tuple[Desideratum, ...]
    """The embargo desiderata, ``F_i ≺ Ex_own`` included."""


@cache
def scope_desiderata() -> ScopeDesiderata:
    """The extended desiderata a vendor's scope scores, by part, each group
    of equivalent ones once.

    Computed on first use: finding the equivalent pairs walks the model.
    """
    held = [
        d
        for d in EXTENDED
        if d.model is ModelName.ONE_VENDOR and d.group is not Group.MULTI_PARTY
    ]
    return ScopeDesiderata(
        end=count_once(d for d in held if d.group is not Group.EMBARGO),
        embargo=count_once(d for d in held if d.group is Group.EMBARGO),
    )


def _history(
    record: CaseRecord, events: Iterable[Event], vendor: str
) -> tuple[frozenset[Event], ...]:
    """*events* the record holds, as the walk's history: one entry per
    position, in order, so events of one ledger entry are simultaneous."""
    by_position: dict[int, set[Event]] = {}
    for event in events:
        position = record.position(event, (vendor,))
        if position is not None:
            by_position.setdefault(position, set()).add(event)
    return tuple(frozenset(by_position[p]) for p in sorted(by_position))


@cache
def _ends(
    model: JointModel, query: OrderingQuery[Event], prefix: CasePrefix
) -> frozenset[tuple[frozenset[Event], frozenset[int]]]:
    return reachable_ends(model, query, prefix)


def _walk(
    record: CaseRecord, vendor: str, desiderata: Sequence[Desideratum]
) -> WalkScore:
    """Score *desiderata* for *vendor* on its one-vendor walk from where the
    case stands.

    The case's record is the walk's history, so an ordering it already
    settles stays settled.

    Raises:
        NotAJointStateError: the case stands in no state of the model.
    """
    state = record.state((record.path(vendor),))
    joined = OrderingQuery(
        tuple(o for d in desiderata for o in d.query.orderings),
        frozenset().union(*(d.query.given for d in desiderata)),
    )
    prefix: CasePrefix = WalkPrefix(
        state, _history(record, joined.watched, vendor)
    )
    scored: list[TermScore] = []
    spans: list[tuple[Fraction, frozenset[Event], range]] = []
    start = 0
    for desideratum in desiderata:
        term_weight = weight(desideratum)
        reading = joint_values(
            ModelName.ONE_VENDOR, desideratum.query
        ).reading(prefix)
        scored.append(
            TermScore(
                notation=desideratum.notation,
                group=desideratum.group,
                vendors=(vendor,),
                weight=term_weight,
                met=reading.outcome,
            )
        )
        count = len(desideratum.query.orderings)
        spans.append(
            (
                term_weight,
                desideratum.query.given,
                range(start, start + count),
            )
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
        for seen, met in _ends(case_model(1), joined, prefix)
    ]
    return WalkScore(
        terms=tuple(scored), best=max(outcomes), worst=min(outcomes)
    )


def vendor_scope(
    record: CaseRecord, vendor: str
) -> ExtendedScore | UnscoredScope:
    """*vendor*'s extended desiderata, each part on the one-vendor walk from
    its state, or why the case cannot be walked from.

    Raises:
        KeyError: *record* did not read *vendor*.
    """
    record.path(vendor)
    desiderata = scope_desiderata()
    try:
        return ExtendedScore(
            end=_walk(record, vendor, desiderata.end),
            embargo=_walk(record, vendor, desiderata.embargo),
        )
    except NotAJointStateError as exc:
        return UnscoredScope(reason=str(exc))
