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

"""The case state's two small machines, in notation and in words (#6674).

The Vendor Fix Path (VFD) and the public state (PXA) each spell their state
in three letters, one per case-state event: ``VFd``, ``PXa``.  An event the
source cannot observe is unknown, never false (CRD-02-005), so a reading of
a state allows every state that differs from it only by such an event
happening: :func:`possible_states`.  :func:`vfd_badge` names a fix path in
words, or each fix path it may be.  Nothing here calls Streamlit.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from vultron.core.states import PXA_EVENTS, VFD_EVENTS
from vultron.core.states.cs import CS, CS_d, CS_vf
from vultron.core.states.cs_invariants import CSEvent, cs_dimensions

#: The fix-path events, and the public-state events, in the order their
#: notation spells them.
VFD_NOTATION: tuple[CSEvent, ...] = tuple(
    e for e in CSEvent if e in VFD_EVENTS
)
PXA_NOTATION: tuple[CSEvent, ...] = tuple(
    e for e in CSEvent if e in PXA_EVENTS
)

#: Each Vendor Fix Path state, as the compound case states allow it: a
#: ``(vf, d)`` pair, in the order the compound states first reach it.  A
#: fix is deployed only once it is ready, so of the six pairs only four.
VFD_STATES: tuple[tuple[CS_vf, CS_d], ...] = tuple(
    dict.fromkeys(cs_dimensions(s)[:2] for s in CS)
)


def vfd_name(vf: CS_vf, d: CS_d) -> str:
    """A Vendor Fix Path state in its notation: ``VFd``."""
    return f"{vf.value}{d.value}"


#: Each Vendor Fix Path state's icon and its words.
VFD_WORDS: Mapping[tuple[CS_vf, CS_d], tuple[str, str]] = {
    (CS_vf.vf, CS_d.d): ("⚪", "Vendor unaware"),
    (CS_vf.Vf, CS_d.d): ("👀", "Vendor aware"),
    (CS_vf.VF, CS_d.d): ("🩹", "Fix ready"),
    (CS_vf.VF, CS_d.D): ("✅", "Fix deployed"),
}

#: Each Vendor Fix Path state as an icon and words: ``🩹 Fix ready``.
VFD_BADGES: Mapping[tuple[CS_vf, CS_d], str] = {
    pair: f"{icon} {words}" for pair, (icon, words) in VFD_WORDS.items()
}


def unknown_events(
    state: str,
    events: Sequence[CSEvent],
    unobservable: Collection[CSEvent],
) -> frozenset[CSEvent]:
    """Each of *events* the reading of *state*, in notation, leaves unknown.

    *events* are the events the notation's letters spell, in order.  An
    event the source cannot observe and *state* has not happened is unknown,
    never false (CRD-02-005): it may have happened.  An unobservable event
    the reading says happened is not unknown, so nothing the reading states
    is read as possibly false.
    """
    return frozenset(
        event
        for event, letter in zip(events, state, strict=True)
        if event in unobservable and letter.islower()
    )


def possible_states(
    state: str,
    states: Sequence[str],
    events: Sequence[CSEvent],
    unobservable: Collection[CSEvent],
) -> tuple[str, ...]:
    """Each of *states*, in notation, that the reading of *state* allows.

    Each letter of an event :func:`unknown_events` names may read either
    way; every other letter is as *state* spells it.
    """
    unknown = unknown_events(state, events, unobservable)
    free = {i for i, event in enumerate(events) if event in unknown}
    return tuple(
        s
        for s in states
        if all(s[i] == state[i] for i in range(len(events)) if i not in free)
    )


def _either(words: Sequence[str]) -> str:
    """*words* as one choice: ``a, b or c``."""
    if len(words) == 1:
        return words[0]
    return f"{', '.join(words[:-1])} or {words[-1]}"


def vfd_badge(state: CS, unobservable: Collection[CSEvent] = ()) -> str:
    """The Vendor Fix Path of compound case state *state*, in words.

    When the source cannot observe one of its events, the badge names each
    state the path may be in (CRD-02-005).
    """
    vf, d, _ = cs_dimensions(state)
    by_name = {vfd_name(*pair): pair for pair in VFD_STATES}
    possible = possible_states(
        vfd_name(vf, d), list(by_name), VFD_NOTATION, unobservable
    )
    if len(possible) == 1:
        return VFD_BADGES[(vf, d)]
    choice = _either([VFD_WORDS[by_name[n]][1].lower() for n in possible])
    return f"❔ {choice[0].upper()}{choice[1:]}"


__all__ = [
    "PXA_NOTATION",
    "VFD_BADGES",
    "VFD_NOTATION",
    "VFD_STATES",
    "VFD_WORDS",
    "possible_states",
    "unknown_events",
    "vfd_badge",
    "vfd_name",
]
