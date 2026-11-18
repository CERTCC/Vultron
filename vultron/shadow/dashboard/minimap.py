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

"""Each state as a small map of its state machine, current state marked (#6674).

Each machine is drawn as a
:class:`~vultron.shadow.dashboard.machine_map.MachineMap` from its transition
table in :mod:`vultron.core.states`, never from a hand-drawn diagram, so the
map cannot drift from the code: RM from the RM table, EM from
:data:`~vultron.core.states.em.EM_TRANSITIONS`, PXA from the PXA table, and
the Vendor Fix Path (VFD) from the VF and D tables over the four VFD states
the compound case state allows.  The map draws itself as Graphviz DOT source
with one state marked, for the page to lay out.

A :class:`Minimap` reads only the state it is given, so the page can draw
one for any standing, the ledger's last or an earlier one.  An event the
source cannot observe is unknown, never false (CRD-02-005): a map whose
machine has one marks every state the reading allows, as possible.
Nothing here calls Streamlit.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict

from vultron.core.states.cs import (
    CS,
    CS_pxa,
    d_transition_rows,
    pxa_transition_rows,
    vf_transition_rows,
)
from vultron.core.states.cs_invariants import CSEvent, cs_dimensions
from vultron.core.states.em import EM, EM_Trigger, em_transition_rows
from vultron.core.states.rm import RM, rm_transition_rows
from vultron.measure.ledger import friendly_actor_name
from vultron.measure.standing import CaseStanding, ParticipantStanding
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.case_state import (
    PXA_NOTATION,
    VFD_BADGES,
    VFD_NOTATION,
    VFD_STATES,
    possible_states,
    vfd_badge,
    vfd_name,
)
from vultron.shadow.dashboard.machine_map import MachineMap, MapEdge, MapState

#: One transition as a map draws it: ``(words, label, source, dest)``,
#: its trigger in words and as its arrow reads it (``None`` for no label),
#: and the two node ids.
type _Row = tuple[str, str | None, str, str]


def _edges(rows: Iterable[_Row]) -> tuple[MapEdge, ...]:
    """One arrow per (source, dest) of *rows*, carrying its triggers in row
    order."""
    triggers: dict[tuple[str, str], dict[str, str | None]] = {}
    for words, label, source, dest in rows:
        triggers.setdefault((source, dest), {}).setdefault(words, label)
    return tuple(
        MapEdge(
            source=source,
            dest=dest,
            triggers=tuple(named),
            label=", ".join(label for label in named.values() if label)
            or None,
        )
        for (source, dest), named in triggers.items()
    )


def _words(trigger: Enum) -> str:
    """A trigger's value in words: ``public becomes aware``."""
    return str(trigger.value).replace("_", " ")


def _word_row(trigger: Enum, source: str, dest: str) -> _Row:
    """A report or embargo transition: its arrow reads nothing."""
    return (_words(trigger), None, source, dest)


def _letter_row(trigger: Enum, source: str, dest: str) -> _Row:
    """A case-state transition: its arrow reads its event letter, ``P``."""
    return (f"{trigger.name}: {_words(trigger)}", trigger.name, source, dest)


def _table_rows(
    table: Iterable[tuple[Enum, Enum, Enum]],
    row: Callable[[Enum, str, str], _Row],
) -> list[_Row]:
    """``(trigger, source, dest)`` rows as map rows, each state by its enum
    name."""
    return [
        row(trigger, source.name, dest.name) for trigger, source, dest in table
    ]


def _word_states[S: Enum](
    states: Iterable[S], badges: Mapping[S, str]
) -> tuple[MapState, ...]:
    """A report or embargo machine's states, in enum order, each node
    reading its name as a word and its badge on hover."""
    return tuple(
        MapState(id=s.name, label=s.name.capitalize(), tooltip=badges[s])
        for s in states
    )


def _public_words(
    state: CS_pxa, unobservable: Collection[CSEvent] = ()
) -> str:
    """A public state as its three badges."""
    return " · ".join(view.public_badges(state, unobservable))


def _rm_map() -> MachineMap:
    return MachineMap(
        name="RM",
        title="Report management",
        states=_word_states(RM, view.RM_BADGES),
        edges=_edges(
            _table_rows(
                ((t.trigger, t.source, t.dest) for t in rm_transition_rows()),
                _word_row,
            )
        ),
    )


def _em_map() -> MachineMap:
    return MachineMap(
        name="EM",
        title="Embargo management",
        states=_word_states(EM, view.EM_BADGES),
        edges=_edges(
            _word_row(EM_Trigger(row["trigger"]), row["source"], row["dest"])
            for row in em_transition_rows()
        ),
    )


def _pxa_map() -> MachineMap:
    return MachineMap(
        name="PXA",
        title="Public state",
        states=tuple(
            MapState(id=s.name, label=s.name, tooltip=_public_words(s))
            for s in CS_pxa
        ),
        edges=_edges(
            _table_rows(
                ((t.trigger, t.source, t.dest) for t in pxa_transition_rows()),
                _letter_row,
            )
        ),
    )


def _vfd_rows() -> list[_Row]:
    """The VF and D tables over :data:`VFD_STATES`: each VF row with D held,
    and each D row with VF held, wherever both ends are VFD states."""
    rows: list[_Row] = []
    for vf_row in vf_transition_rows():
        rows.extend(
            _letter_row(
                vf_row.trigger, vfd_name(vf, d), vfd_name(vf_row.dest, d)
            )
            for vf, d in VFD_STATES
            if vf is vf_row.source and (vf_row.dest, d) in VFD_STATES
        )
    for d_row in d_transition_rows():
        rows.extend(
            _letter_row(
                d_row.trigger, vfd_name(vf, d), vfd_name(vf, d_row.dest)
            )
            for vf, d in VFD_STATES
            if d is d_row.source and (vf, d_row.dest) in VFD_STATES
        )
    return rows


def _vfd_map() -> MachineMap:
    return MachineMap(
        name="VFD",
        title="Vendor fix path",
        states=tuple(
            MapState(
                id=vfd_name(vf, d),
                label=vfd_name(vf, d),
                tooltip=VFD_BADGES[(vf, d)],
            )
            for vf, d in VFD_STATES
        ),
        edges=_edges(_vfd_rows()),
    )


#: Each machine's map, built once from its transition table.
RM_MAP = _rm_map()
EM_MAP = _em_map()
PXA_MAP = _pxa_map()
VFD_MAP = _vfd_map()


class Minimap(BaseModel):
    """One state on its machine's map, for the page to draw.

    Fields:
        title: The machine's name in words, the map's heading.
        dot: The map as Graphviz DOT source, the state marked.
        caption: The state in words.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    dot: str
    caption: str


def _minimap(
    machine: MachineMap, marked: Sequence[str], caption: str
) -> Minimap:
    return Minimap(
        title=machine.title, dot=machine.dot(*marked), caption=caption
    )


def _possible(
    machine: MachineMap,
    state: str,
    events: Sequence[CSEvent],
    unobservable: Collection[CSEvent],
) -> tuple[str, ...]:
    """Each state of *machine* the reading of *state* allows."""
    return possible_states(
        state, [s.id for s in machine.states], events, unobservable
    )


def rm_minimap(state: RM) -> Minimap:
    """A participant's report-management state on the RM map."""
    return _minimap(RM_MAP, (state.name,), view.RM_BADGES[state])


def em_minimap(state: EM) -> Minimap:
    """The case's embargo-management state on the EM map."""
    return _minimap(EM_MAP, (state.name,), view.EM_BADGES[state])


def pxa_minimap(
    state: CS_pxa, unobservable: Collection[CSEvent] = ()
) -> Minimap:
    """The case's public state on the PXA map.

    When the source cannot observe a public-state event, every state the
    reading allows is marked as possible (CRD-02-005).
    """
    return _minimap(
        PXA_MAP,
        _possible(PXA_MAP, state.name, PXA_NOTATION, unobservable),
        _public_words(state, unobservable),
    )


def vfd_minimap(state: CS, unobservable: Collection[CSEvent] = ()) -> Minimap:
    """The Vendor Fix Path of compound case state *state* on the VFD map.

    When the source cannot observe a fix-path event, every state the
    reading allows is marked as possible (CRD-02-005).
    """
    vf, d, _ = cs_dimensions(state)
    return _minimap(
        VFD_MAP,
        _possible(VFD_MAP, vfd_name(vf, d), VFD_NOTATION, unobservable),
        vfd_badge(state, unobservable),
    )


def case_minimaps(case: CaseStanding) -> tuple[Minimap, Minimap]:
    """The case's EM and public state, each on its map."""
    return em_minimap(case.em), pxa_minimap(case.pxa, case.unobservable)


#: Every ASCII punctuation character, each of which CommonMark lets a
#: backslash escape.
_PUNCTUATION = re.compile(r"([!-/:-@\[-`{-~])")


def markdown_literal(text: str) -> str:
    """*text* escaped, so Streamlit's Markdown shows it as written.

    A participant's name comes from the case's source, so a label such as
    a tab's must not render it: an image in it would have the browser fetch
    an outside URL.  Every ASCII punctuation character is escaped, which
    also covers Streamlit's own ``:emoji:`` and ``:color[...]`` directives.
    """
    return _PUNCTUATION.sub(r"\\\1", text)


#: What the page says in place of a participant's VFD map when it has no
#: case-state history.
NO_FIX_PATH = "No vendor fix path: the participant has no case-state history."


class ParticipantMinimaps(BaseModel):
    """One participant's states, each on its map.

    Fields:
        label: The participant, as its tab names it.
        rm: Its report-management state.
        vfd: Its Vendor Fix Path, or ``None`` with no case-state history.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    rm: Minimap
    vfd: Minimap | None

    @property
    def tab(self) -> str:
        """Its tab's label: :attr:`label` as literal Markdown text."""
        return markdown_literal(self.label)


def participant_minimaps(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> list[ParticipantMinimaps]:
    """Each participant's RM and VFD maps, in the participants' order.

    A participant is labelled by its short name; a name two participants
    share takes the participant's actor id as well, so no tab reads as
    another's.
    """
    labels = [friendly_actor_name(p.participant, names) for p in participants]
    counts = Counter(labels)
    return [
        ParticipantMinimaps(
            label=label
            if counts[label] == 1
            else f"{label} ({p.participant})",
            rm=rm_minimap(p.rm),
            vfd=None
            if p.case_state is None
            else vfd_minimap(p.case_state, p.case.unobservable),
        )
        for label, p in zip(labels, participants, strict=True)
    ]


__all__ = [
    "EM_MAP",
    "NO_FIX_PATH",
    "PXA_MAP",
    "RM_MAP",
    "VFD_MAP",
    "Minimap",
    "ParticipantMinimaps",
    "case_minimaps",
    "em_minimap",
    "markdown_literal",
    "participant_minimaps",
    "pxa_minimap",
    "rm_minimap",
    "vfd_minimap",
]
