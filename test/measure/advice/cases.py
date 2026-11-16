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

"""Synthetic joint states for the move-band spike (#6450).

Each :class:`Case` is a point in a case of two to four vendors, reached by a
history of joint-model steps, with mixed vendor readiness, with or without
an active embargo.  The vendors are numbered as in
:attr:`~vultron.measure.baselines.JointState.vendors`:

* *unaware*: the vendor has not received the report;
* *unready*: the vendor has validated and accepted the report, no fix;
* *ready*: the vendor's fix is ready, not deployed;
* *deployed*: the vendor's fix is ready and deployed.

The cases name their vendors in that order, most advanced first, and none
is public yet.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache

from vultron.core.states.em import EM
from vultron.measure.advice import open_moves
from vultron.measure.baselines import (
    Event,
    EventKind,
    JointState,
    Step,
    WalkPrefix,
)
from vultron.measure.baselines.values import CasePrefix, case_model

_K = EventKind

COORDINATOR: frozenset[EventKind] = frozenset(
    {
        _K.V,
        _K.P,
        _K.EMBARGO_PROPOSED,
        _K.EMBARGO_START,
        _K.REVISION_PROPOSED,
        _K.REVISION_SETTLED,
        _K.EXIT_OWN_TERMS,
        _K.EXIT_OTHER,
    }
)
"""The kinds of move a coordinator makes: notify a vendor, publish, or act on
the embargo."""

_READINESS: dict[str, tuple[EventKind, ...]] = {
    "unaware": (),
    "unready": (_K.V, _K.VALIDATED, _K.ACCEPTED),
    "ready": (_K.V, _K.VALIDATED, _K.ACCEPTED, _K.F),
    "deployed": (_K.V, _K.VALIDATED, _K.ACCEPTED, _K.F, _K.D),
}


@dataclass(frozen=True)
class Case:
    """One synthetic point of a case, and the moves the advice is asked about.

    ``only``, when set, keeps only the moves of those kinds, as a page that
    shows one participant's moves would.
    """

    name: str
    readiness: tuple[str, ...]
    embargo: bool
    only: frozenset[EventKind] | None = field(default=None)

    @property
    def vendor_count(self) -> int:
        return len(self.readiness)

    @property
    def prefix(self) -> CasePrefix:
        return _prefix(self.readiness, self.embargo)

    def move(
        self, kind: EventKind, vendor: int | None = None
    ) -> Step[JointState, Event]:
        """The case's one open move of *kind*, for *vendor* if given."""
        (found,) = [m for m in self.moves if m.event == Event(kind, vendor)]
        return found

    def has(self, kind: EventKind, vendor: int | None = None) -> bool:
        return any(m.event == Event(kind, vendor) for m in self.moves)

    @property
    def moves(self) -> tuple[Step[JointState, Event], ...]:
        found = open_moves(self.prefix)
        if self.only is None:
            return found
        return tuple(m for m in found if m.event.kind in self.only)

    def yours(self, move: Step[JointState, Event]) -> bool:
        """Whether the coordinator makes *move*."""
        return move.event.kind in COORDINATOR

    def __str__(self) -> str:
        return self.name


def _events(readiness: Iterable[str], embargo: bool) -> list[Event]:
    events = [
        Event(kind, vendor)
        for vendor, ready in enumerate(readiness, start=1)
        for kind in _READINESS[ready]
    ]
    if embargo:
        events += [Event(_K.EMBARGO_PROPOSED), Event(_K.EMBARGO_START)]
    return events


@cache
def _prefix(readiness: tuple[str, ...], embargo: bool) -> CasePrefix:
    model = case_model(len(readiness))
    prefix: CasePrefix = WalkPrefix(model.initial)
    for event in _events(readiness, embargo):
        (step,) = [
            s
            for s in model.steps(prefix.state)
            if s.event == event
            and (event.kind is not _K.EMBARGO_START or s.state.em is EM.ACTIVE)
        ]
        prefix = prefix.then(step)
    return prefix


def _case(*readiness: str, embargo: bool) -> Case:
    name = "-".join(readiness) + (" embargo" if embargo else " no-embargo")
    return Case(name, readiness, embargo)


CASES: tuple[Case, ...] = tuple(
    _case(*readiness, embargo=embargo)
    for readiness in (
        ("ready", "unready"),
        ("unready", "unready"),
        ("ready", "unready", "unaware"),
        ("deployed", "ready", "unready", "unaware"),
    )
    for embargo in (True, False)
)
"""The cases every pathology runs over: two to four vendors, mixed readiness,
with and without an active embargo."""

NO_HARM_FREE = Case(
    "ready-unready embargo, three coordinator moves",
    ("ready", "unready"),
    True,
    frozenset({_K.P, _K.REVISION_PROPOSED, _K.EXIT_OTHER}),
)
"""A view of the case in which no shown move should be harm-free (P6)."""
