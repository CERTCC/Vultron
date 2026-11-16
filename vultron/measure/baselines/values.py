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

"""Each vendor's expected desiderata values from any point of a joint walk.

A case with any number of vendors stands at a :class:`.JointState`, reached by
a history of steps (a :class:`.WalkPrefix` of the case's :class:`.JointModel`).
:func:`desiderata_values` gives, for each vendor and each desideratum, the
exact chance that the desideratum holds if the case is left to chance from
there; :func:`expected_change` gives a step's expected change, the values
after the step minus the values before it, for each vendor.

Each value is taken in the desideratum's own model, the smallest that holds
its events (ADR-0182), never in a walk over the whole case: the case is
projected onto that model for the vendor.

* a one-vendor desideratum sees the vendor as vendor 1, with the case's
  public state and embargo;
* an original desideratum sees the vendor's six-event case state;
* the two-vendor desideratum ``V_i ≺ F_j`` sees vendor ``i`` as vendor 1 and
  each other vendor ``j`` as vendor 2, once for each ``j``.

So a step by one vendor leaves another vendor's one-vendor and original values
unchanged, and a step on the case's shared events (public awareness, an
exploit, attacks, the embargo) moves every vendor's values.  A projected step
that emits none of the projection's events is no step there, so it is left out
of the projected history.

At the model's start, every value equals the desideratum's :func:`.baseline`.
The solved tables are kept for the life of the process, so repeated lookups
cost little.
"""

from collections.abc import Iterable
from fractions import Fraction
from functools import cache
from typing import NamedTuple

from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import CSEvent, cs_from_dimensions
from vultron.measure.baselines.desiderata import (
    EXTENDED,
    JOINT_TO_CS,
    ORIGINAL,
    Desideratum,
    ModelName,
    case_state_values,
    joint_values,
)
from vultron.measure.baselines.joint import Event, JointModel, JointState
from vultron.measure.baselines.walk import (
    WalkPrefix,
    difference,
    find_step,
)

type CasePrefix = WalkPrefix[JointState, Event]
"""Where a case stands in its joint model: its state and the steps that reached it."""

type Values = dict[VendorDesideratum, Fraction | None]
"""A value for each vendor's desideratum, ``None`` where it is undefined."""


class VendorDesideratum(NamedTuple):
    """One desideratum, as it applies to one vendor of the case.

    ``vendor`` is the vendor ``i`` it is scored for, numbered as in
    :attr:`.JointState.vendors` (from 1).  ``other`` is the vendor ``j`` of
    the two-vendor desideratum, and ``None`` for every other desideratum.
    """

    desideratum: Desideratum
    vendor: int
    other: int | None = None


def vendor_desiderata(vendor_count: int) -> tuple[VendorDesideratum, ...]:
    """Every desideratum for each vendor of a case with *vendor_count* vendors.

    Each vendor has every original and extended desideratum, the two-vendor
    one once for each other vendor; in a one-vendor case it has none.

    Raises:
        ValueError: *vendor_count* is less than one.
    """
    if vendor_count < 1:
        raise ValueError(
            f"a case needs at least one vendor, not {vendor_count}"
        )
    vendors = range(1, vendor_count + 1)
    found: list[VendorDesideratum] = []
    for vendor in vendors:
        for desideratum in (*ORIGINAL, *EXTENDED):
            if desideratum.model is not ModelName.TWO_VENDOR:
                found.append(VendorDesideratum(desideratum, vendor))
                continue
            found += [
                VendorDesideratum(desideratum, vendor, other)
                for other in vendors
                if other != vendor
            ]
    return tuple(found)


def _renumber(
    events: Iterable[Event], numbering: dict[int, int]
) -> frozenset[Event]:
    """*events* of the vendors *numbering* keys, renumbered, with every case event."""
    return frozenset(
        event._replace(vendor=numbering[event.vendor])
        if event.vendor is not None
        else event
        for event in events
        if event.vendor is None or event.vendor in numbering
    )


def _project_joint(
    prefix: CasePrefix, numbering: dict[int, int]
) -> CasePrefix:
    """*prefix* seen by a joint model holding only the vendors *numbering* keys."""
    state = prefix.state
    kept = sorted(numbering, key=numbering.__getitem__)
    projected = state._replace(
        vendors=tuple(state.vendors[vendor - 1] for vendor in kept)
    )
    history = (_renumber(step, numbering) for step in prefix.history)
    return WalkPrefix(projected, tuple(step for step in history if step))


def _project_case_state(
    prefix: CasePrefix, vendor: int
) -> WalkPrefix[CS, CSEvent]:
    """*prefix* seen by the six-event model, for *vendor*."""
    path = prefix.state.vendors[vendor - 1]
    state = cs_from_dimensions(path.vf, path.d, prefix.state.pxa)
    history = (
        frozenset(
            JOINT_TO_CS[event]
            for event in _renumber(step, {vendor: 1})
            if event in JOINT_TO_CS
        )
        for step in prefix.history
    )
    return WalkPrefix(state, tuple(step for step in history if step))


def _value(key: VendorDesideratum, prefix: CasePrefix) -> Fraction | None:
    desideratum, vendor, other = key
    if desideratum.model is ModelName.CASE_STATE:
        return case_state_values(desideratum.query).at(
            _project_case_state(prefix, vendor)
        )
    numbering = {vendor: 1} if other is None else {vendor: 1, other: 2}
    return joint_values(desideratum.model, desideratum.query).at(
        _project_joint(prefix, numbering)
    )


def desiderata_values(prefix: CasePrefix) -> Values:
    """Each vendor's exact expected value of each desideratum from *prefix*.

    The vendors are those of ``prefix.state``.  A value is the chance that
    the desideratum holds for that vendor if the case is left to chance from
    *prefix*, among the walks that meet its scope; it is ``None`` when no
    walk from there meets the scope, such as a validation-scoped desideratum
    once the report is invalid.  At a state with no allowed step, each value
    is the case's own outcome.

    The history is taken as given, not replayed against the state: a caller
    that holds only the events uses :func:`.replay` or
    :meth:`.WalkPrefix.then` to build the prefix.

    Raises:
        ValueError: ``prefix.state`` holds no vendor.
        WalkNeverEndsError: a projected walk can circulate forever.
    """
    keys = vendor_desiderata(len(prefix.state.vendors))
    return {key: _value(key, prefix) for key in keys}


@cache
def _case_model(vendor_count: int) -> JointModel:
    """The joint model a case of *vendor_count* vendors steps through.

    Only its steps from a given state are read, never a walk over it.
    """
    return JointModel(vendor_count)


def expected_change(prefix: CasePrefix, event: Event) -> Values:
    """Each vendor's expected change, in each desideratum, of the step *event* from *prefix*.

    The value after the step minus the value before it
    (:func:`desiderata_values`): positive when the step makes the
    desideratum likelier to hold than leaving the case to chance from
    *prefix*.  ``None`` where either value is undefined.

    Raises:
        ValueError: ``prefix.state`` holds no vendor.
        VultronInvalidStateTransitionError: *event* is not one allowed step
            from the prefix's state in the case's joint model, or more than
            one (:func:`.find_step`).
    """
    model = _case_model(len(prefix.state.vendors))
    after = prefix.then(find_step(model, prefix.state, event))
    return _difference(desiderata_values(after), desiderata_values(prefix))


def _difference(after: Values, before: Values) -> Values:
    return {key: difference(after[key], before[key]) for key in before}
