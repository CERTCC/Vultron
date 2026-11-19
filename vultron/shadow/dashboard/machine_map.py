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

"""One state machine as a map: its states, its arrows, and its DOT (#6674).

A :class:`MachineMap` holds a machine's states and arrows and draws them as
Graphviz DOT source with one state marked as current, or several marked as
possible.  It knows no machine: :mod:`vultron.shadow.dashboard.minimap`
builds each one from its core transition table.  Nothing here calls
Streamlit.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.primitives import NonEmptyString


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
            or ``None``, so a small map is not crowded with words.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    dest: str
    triggers: tuple[str, ...]
    label: NonEmptyString | None = None


#: How the map draws its graph, its states and its arrows.  Streamlit draws
#: a Graphviz chart in the same colours whatever the app's theme, so the map
#: is a white card: its greys and reds read on it in a light and a dark
#: theme alike.
_GRAPH = (
    'graph [rankdir=LR, bgcolor="#ffffff", size="4,2",'
    ' nodesep=0.15, ranksep=0.3, pad=0.1, fontname="sans-serif"];'
)
_NODE = (
    'node [shape=box, style="rounded,filled", fillcolor="#f0f2f6",'
    ' color="#9aa0a6", fontcolor="#31333f", fontname="sans-serif",'
    ' fontsize=10, height=0.25, margin="0.06,0.03"];'
)
_EDGE = (
    'edge [color="#80868b", fontcolor="#3c4043", fontname="sans-serif",'
    " fontsize=8, arrowsize=0.5];"
)
#: The current state: filled, and drawn with a double border, so it is told
#: apart by its shape as well as its colour.
_CURRENT = (
    'fillcolor="#ff4b4b", color="#ff4b4b", fontcolor="#ffffff",'
    " penwidth=2, peripheries=2"
)
#: One of several states the reading allows, when its source cannot observe
#: an event of the machine: dashed, so it reads as possible, not as known.
_POSSIBLE = (
    'style="rounded,filled,dashed", fillcolor="#ffd6d6", color="#ff4b4b",'
    " penwidth=2"
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

    def dot(self, *marked: str) -> str:
        """The map as Graphviz DOT source, with the *marked* states marked.

        One state marked is the current state.  Several are each a state
        the reading allows, when its source cannot observe an event of the
        machine (CRD-02-005), and are drawn as possible.

        Raises:
            ValueError: no state is marked, or one is not one of its states.
        """
        ids = {s.id for s in self.states}
        unknown = [m for m in marked if m not in ids]
        if not marked or unknown:
            raise ValueError(
                f"{unknown or 'no state'} is not a {self.name} state"
            )
        mark = _CURRENT if len(set(marked)) == 1 else _POSSIBLE
        lines = [f"digraph {_quoted(self.name)} {{", _GRAPH, _NODE, _EDGE]
        for state in self.states:
            attributes = (
                f"label={_quoted(state.label)},"
                f" tooltip={_quoted(state.tooltip)}"
            )
            if state.id in marked:
                attributes += f", {mark}"
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


__all__ = ["MachineMap", "MapEdge", "MapState"]
