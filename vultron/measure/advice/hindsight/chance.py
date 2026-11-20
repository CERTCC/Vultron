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

"""When an entry's change is chance: an event no participant chooses
(#6672).

An exploit made public or attacks observed (X, A) are chance.  So is the
public becoming aware of the vul (P), which a public exploit forces and a
leak may cause: the ledger records only that the case became public, never
whether a participant published.  The one exception is a case whose embargo
had ended on its own terms at or before that entry
(:func:`embargo_ended_on_own_terms`), where P is graded as a participant's
publication.  Telling a publication from a leak is #6732.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from vultron.core.states.cs import (
    AttackObservation,
    ExploitPublication,
    PublicAwareness,
    PxaState,
)
from vultron.measure.advice.hindsight.mark import (
    FORCED_BY_EXPLOIT,
    NO_KNOWN_PUBLISHER,
)
from vultron.measure.baselines import EmbargoEnd
from vultron.measure.history import (
    CaseEventHistory,
    EventKind as HistoryKind,
    ReachedState,
)
from vultron.measure.standing import embargo_end


def _entered(
    before: ReachedState,
    after: ReachedState,
    part: Callable[[PxaState], Enum],
    was: Enum,
    now: Enum,
) -> bool:
    """Whether *part* of the case's public state went from *was* to *now*
    with the entry from *before* to *after*."""
    return part(before.pxa.value) is was and part(after.pxa.value) is now


def made_public(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made the public aware of the vul."""
    return _entered(
        before,
        after,
        lambda pxa: pxa.public_awareness,
        PublicAwareness.PUBLIC_UNAWARE,
        PublicAwareness.PUBLIC_AWARE,
    )


def made_chance(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made an exploit public or attacks observed: the
    events no participant chooses
    (:data:`~vultron.measure.advice.shifts.CHANCE_EVENTS`)."""
    return _entered(
        before,
        after,
        lambda pxa: pxa.exploit_publication,
        ExploitPublication.NO_PUBLIC_EXPLOIT,
        ExploitPublication.EXPLOIT_PUBLIC,
    ) or _entered(
        before,
        after,
        lambda pxa: pxa.attack_observation,
        AttackObservation.NO_ATTACKS_OBSERVED,
        AttackObservation.ATTACKS_OBSERVED,
    )


def _forced_by_exploit(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made the public aware of a vul whose exploit was
    already public: a public exploit forces public awareness next, so no
    participant chose it, whoever's entry records it."""
    return (
        before.pxa.value.exploit_publication
        is ExploitPublication.EXPLOIT_PUBLIC
        and made_public(before, after)
    )


def unchosen_publicity(
    before: ReachedState, after: ReachedState, ended_on_own_terms: bool
) -> str | None:
    """Why the public becoming aware of the vul at this entry is chance, or
    ``None`` when it is not: a public exploit forced it, or no embargo that
    ended on its own terms precedes it, so the ledger cannot say that a
    participant published.  An entry that also made an exploit public or
    attacks observed is left to the chance event it records."""
    if _forced_by_exploit(before, after):
        return FORCED_BY_EXPLOIT
    if (
        made_public(before, after)
        and not made_chance(before, after)
        and not ended_on_own_terms
    ):
        return NO_KNOWN_PUBLISHER
    return None


def embargo_ended_on_own_terms(
    history: CaseEventHistory, log_index: int
) -> bool:
    """Whether the case's embargo had ended on its own terms at or before
    the entry at *log_index*, with no embargo in force again since.

    It ended on its own terms when it reached its end time or a fix ended
    it (:func:`~vultron.measure.standing.embargo_end`), the joint model's
    own-terms exit.
    """
    events = [
        event
        for event in history.of_kind(
            HistoryKind.EMBARGO_START, HistoryKind.EMBARGO_EXIT
        )
        if event.log_index <= log_index
    ]
    if not events or events[-1].kind is not HistoryKind.EMBARGO_EXIT:
        return False
    return embargo_end(events[-1]) is EmbargoEnd.OWN_TERMS


__all__ = [
    "embargo_ended_on_own_terms",
    "made_chance",
    "made_public",
    "unchosen_publicity",
]
