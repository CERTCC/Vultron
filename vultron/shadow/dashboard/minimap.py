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

A :class:`MachineMap` is one protocol state machine drawn from its transition
table in :mod:`vultron.core.states`, never from a hand-drawn diagram, so the
map cannot drift from the code: RM from the RM table, EM from
:data:`~vultron.core.states.em.EM_TRANSITIONS`, PXA from the PXA table, and
the Vendor Fix Path (VFD) from the VF and D tables over the four VFD states
the compound case state allows.  :meth:`MachineMap.dot` draws it as Graphviz
DOT source with one state marked, for the page to lay out.

A :class:`Minimap` reads only the state it is given, so the page can draw
one for any standing, the ledger's last or an earlier one.  Nothing here
calls Streamlit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs.transitions import (
    _d_transitions,
    _pxa_transitions,
    _vf_transitions,
)
from vultron.core.states.cs_invariants import cs_dimensions
from vultron.core.states.em import EM, EM_Trigger, em_transition_rows
from vultron.core.states.rm import RM, _transitions as _rm_transitions
from vultron.measure.ledger import friendly_actor_name
from vultron.measure.standing import CaseStanding, ParticipantStanding
from vultron.shadow.dashboard import view


class MapState(BaseModel):
    """One state of a machine map.

    Fields:
        id: The state's node id: its enum name, or its VFD notation.
        label: What its node reads.
        tooltip: The state in words, shown on hover.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    tooltip: str


class MapEdge(BaseModel):
    """One arrow of a machine map: every trigger from one state to another.

    Fields:
        source: The node id it leaves.
        dest: The node id it enters.
        triggers: Each trigger of the table that moves *source* to *dest*,
            in table order and in words, shown on hover.
        label: What the arrow reads: a case-state trigger's event letter,
            or nothing, so a small map is not crowded with words.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    dest: str
    triggers: tuple[str, ...]
    label: str = ""


#: How the map draws its graph, its states and its arrows.
_GRAPH = (
    'graph [rankdir=LR, bgcolor="transparent", size="4,2",'
    ' nodesep=0.15, ranksep=0.3, pad=0.05, fontname="sans-serif"];'
)
_NODE = (
    'node [shape=box, style="rounded,filled", fillcolor="#f0f2f6",'
    ' color="#9aa0a6", fontcolor="#31333f", fontname="sans-serif",'
    ' fontsize=10, height=0.25, margin="0.06,0.03"];'
)
_EDGE = (
    'edge [color="#9aa0a6", fontcolor="#6b6f76", fontname="sans-serif",'
    " fontsize=8, arrowsize=0.5];"
)
#: The current state: filled, and drawn with a double border, so it is told
#: apart by its shape as well as its colour.
_CURRENT = (
    'fillcolor="#ff4b4b", color="#ff4b4b", fontcolor="#ffffff",'
    " penwidth=2, peripheries=2"
)


def _quoted(text: str) -> str:
    """*text* as a DOT quoted string."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class MachineMap(BaseModel):
    """One state machine as a map: its states and its arrows.

    Fields:
        name: The machine's name, such as ``RM``.
        title: Its name in words, the map's heading.
        states: Each state, in the machine's order.
        edges: Each arrow, in the order the table first names it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    title: str
    states: tuple[MapState, ...]
    edges: tuple[MapEdge, ...]

    @model_validator(mode="after")
    def _edges_join_its_states(self) -> MachineMap:
        """Each state once, and each arrow between two of them."""
        problems: list[str] = []
        ids = [s.id for s in self.states]
        twice = sorted(i for i, n in Counter(ids).items() if n > 1)
        if twice:
            problems.append(f"states listed twice: {twice}")
        for edge in self.edges:
            for end in (edge.source, edge.dest):
                if end not in ids:
                    problems.append(f"arrow end {end!r} is not a state")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def dot(self, current: str) -> str:
        """The map as Graphviz DOT source, with state *current* marked.

        Raises:
            ValueError: *current* is not one of its states.
        """
        if current not in {s.id for s in self.states}:
            raise ValueError(f"{current!r} is not a {self.name} state")
        lines = [f"digraph {_quoted(self.name)} {{", _GRAPH, _NODE, _EDGE]
        for state in self.states:
            attributes = (
                f"label={_quoted(state.label)},"
                f" tooltip={_quoted(state.tooltip)}"
            )
            if state.id == current:
                attributes += f", {_CURRENT}"
            lines.append(f"{_quoted(state.id)} [{attributes}];")
        for edge in self.edges:
            attributes = f"tooltip={_quoted(', '.join(edge.triggers))}"
            if edge.label:
                attributes = f"label={_quoted(edge.label)}, {attributes}"
            lines.append(
                f"{_quoted(edge.source)} -> {_quoted(edge.dest)}"
                f" [{attributes}];"
            )
        lines.append("}")
        return "\n".join(lines)


#: One transition as a map draws it: ``(words, label, source, dest)``,
#: its trigger in words and as its arrow reads it, and the two node ids.
type _Row = tuple[str, str, str, str]


def _edges(rows: Iterable[_Row]) -> tuple[MapEdge, ...]:
    """One arrow per (source, dest) of *rows*, carrying its triggers in row
    order."""
    triggers: dict[tuple[str, str], dict[str, str]] = {}
    for words, label, source, dest in rows:
        triggers.setdefault((source, dest), {}).setdefault(words, label)
    return tuple(
        MapEdge(
            source=source,
            dest=dest,
            triggers=tuple(named),
            label=", ".join(label for label in named.values() if label),
        )
        for (source, dest), named in triggers.items()
    )


def _words(trigger: Enum) -> str:
    """A trigger's value in words: ``public becomes aware``."""
    return str(trigger.value).replace("_", " ")


def _word_row(trigger: Enum, source: str, dest: str) -> _Row:
    """A report or embargo transition: its arrow reads nothing."""
    return (_words(trigger), "", source, dest)


def _letter_row(trigger: Enum, source: str, dest: str) -> _Row:
    """A case-state transition: its arrow reads its event letter, ``P``."""
    return (f"{trigger.name}: {_words(trigger)}", trigger.name, source, dest)


def _table_rows(
    table: Sequence[Mapping[str, Enum]],
    row: Callable[[Enum, str, str], _Row],
) -> list[_Row]:
    """A ``transitions``-form table as map rows, each state by its enum
    name."""
    return [row(t["trigger"], t["source"].name, t["dest"].name) for t in table]


def _word_states[S: Enum](
    states: Iterable[S], badges: Mapping[S, str]
) -> tuple[MapState, ...]:
    """A report or embargo machine's states, in enum order, each node
    reading its name as a word and its badge on hover."""
    return tuple(
        MapState(id=s.name, label=s.name.capitalize(), tooltip=badges[s])
        for s in states
    )


def _public_words(state: CS_pxa) -> str:
    """A public state as its three badges."""
    return " · ".join(view.public_badges(state))


def _rm_map() -> MachineMap:
    return MachineMap(
        name="RM",
        title="Report management",
        states=_word_states(RM, view.RM_BADGES),
        edges=_edges(_table_rows(_rm_transitions, _word_row)),
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
        edges=_edges(_table_rows(_pxa_transitions, _letter_row)),
    )


#: Each Vendor Fix Path state, as the compound case states allow it: a
#: ``(vf, d)`` pair, in the order the compound states first reach it.  A
#: fix is deployed only once it is ready, so of the six pairs only four.
VFD_STATES: tuple[tuple[CS_vf, CS_d], ...] = tuple(
    dict.fromkeys(cs_dimensions(s)[:2] for s in CS)
)


def vfd_id(vf: CS_vf, d: CS_d) -> str:
    """A Vendor Fix Path state in its notation: ``VFd``."""
    return f"{vf.value}{d.value}"


def _vfd_rows() -> list[_Row]:
    """The VF and D tables over :data:`VFD_STATES`: each VF row with D held,
    and each D row with VF held, wherever both ends are VFD states."""
    rows: list[_Row] = []
    for t in _vf_transitions:
        rows.extend(
            _letter_row(t["trigger"], vfd_id(vf, d), vfd_id(t["dest"], d))
            for vf, d in VFD_STATES
            if vf is t["source"] and (t["dest"], d) in VFD_STATES
        )
    for t in _d_transitions:
        rows.extend(
            _letter_row(t["trigger"], vfd_id(vf, d), vfd_id(vf, t["dest"]))
            for vf, d in VFD_STATES
            if d is t["source"] and (vf, t["dest"]) in VFD_STATES
        )
    return rows


def _vfd_map() -> MachineMap:
    return MachineMap(
        name="VFD",
        title="Vendor fix path",
        states=tuple(
            MapState(
                id=vfd_id(vf, d),
                label=vfd_id(vf, d),
                tooltip=view.VFD_BADGES[(vf, d)],
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


def _minimap(machine: MachineMap, current: str, caption: str) -> Minimap:
    return Minimap(
        title=machine.title, dot=machine.dot(current), caption=caption
    )


def rm_minimap(state: RM) -> Minimap:
    """A participant's report-management state on the RM map."""
    return _minimap(RM_MAP, state.name, view.RM_BADGES[state])


def em_minimap(state: EM) -> Minimap:
    """The case's embargo-management state on the EM map."""
    return _minimap(EM_MAP, state.name, view.EM_BADGES[state])


def pxa_minimap(state: CS_pxa) -> Minimap:
    """The case's public state on the PXA map."""
    return _minimap(PXA_MAP, state.name, _public_words(state))


def vfd_minimap(state: CS) -> Minimap:
    """The Vendor Fix Path of compound case state *state* on the VFD map."""
    vf, d, _ = cs_dimensions(state)
    return _minimap(VFD_MAP, vfd_id(vf, d), view.vfd_badge(state))


def case_minimaps(case: CaseStanding) -> tuple[Minimap, Minimap]:
    """The case's EM and public state, each on its map."""
    return em_minimap(case.em), pxa_minimap(case.pxa)


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
            vfd=None if p.case_state is None else vfd_minimap(p.case_state),
        )
        for label, p in zip(labels, participants, strict=True)
    ]


__all__ = [
    "EM_MAP",
    "NO_FIX_PATH",
    "PXA_MAP",
    "RM_MAP",
    "VFD_MAP",
    "VFD_STATES",
    "MachineMap",
    "MapEdge",
    "MapState",
    "Minimap",
    "ParticipantMinimaps",
    "case_minimaps",
    "em_minimap",
    "participant_minimaps",
    "pxa_minimap",
    "rm_minimap",
    "vfd_id",
    "vfd_minimap",
]
