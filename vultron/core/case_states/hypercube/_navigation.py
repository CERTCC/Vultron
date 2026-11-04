#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# !/usr/bin/env python

"""Navigate the CVD state graph: states, paths, histories and walks."""

import random
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, cast, overload

import networkx as nx

from vultron.core.case_states.patterns.explanations import explain
from vultron.core.case_states.patterns.info import info
from vultron.core.case_states.patterns.potential_actions import action
from vultron.core.case_states.patterns.zerodays import zeroday_type
from vultron.core.case_states.validations import (
    ensure_valid_state_method_wrapper as ensure_valid_state,
    is_valid_transition,
)
from vultron.core.states.cs import pxa, vfd
from vultron.errors import (
    CVDmodelError,
    TransitionValidationError,
)


class CVDmodelNavigationMixin:
    """State, path and history navigation methods of :class:`CVDmodel`."""

    if TYPE_CHECKING:
        # The model's state this mixin reads.
        G: Any

        def score_state(self, state: str) -> float: ...

    @property
    def states(self) -> list[str]:
        """
        Returns the states in the model
        """
        states: list[str] = list(self.G.nodes)
        return states

    @ensure_valid_state
    def state_info(self, state: str) -> dict:
        """
        Returns the info for a given state

        Args:
            state: the state to return info for

        Returns:
            a dict of info for the state
        """

        data = {
            "state": state,
            "score": self.score_state(state),
            "vfd": vfd(state),
            "pxa": pxa(state),
            "predecessors": list(self.previous_state(state)),
            "successors": self.next_state(state),
            "explain": explain(state),
            "info": info(state),
            "actions": action(state),
            "zeroday_type": zeroday_type(state),
        }
        return data

    @ensure_valid_state
    def previous_state(self, state: str) -> list[str]:
        """
        For a given state, return the previous state(s)

        Args:
            state: the state to return the previous state(s) for

        Returns:
            a list of previous states
        """
        states: list[str] = list(self.G.predecessors(state))
        return states

    @ensure_valid_state
    @overload
    def next_state(self, state: str, transition: None = None) -> list[str]: ...

    @overload
    def next_state(self, state: str, transition: str) -> str | None: ...

    def next_state(
        self, state: str, transition: str | None = None
    ) -> list[str] | str | None:
        if transition is None:
            next_states = list(self.G.successors(state))
            return next_states

        # if you got here transition is not None
        for successor in self.G.successors(state):
            try:
                is_valid_transition(state, successor)
            except TransitionValidationError as e:
                raise CVDmodelError(e)  # noqa: B904  # ruff-baseline #3353

            edge_data = self.G.get_edge_data(state, successor)
            if edge_data["label"] == transition:
                return cast(str, successor)
        return None

    # paths are a list of edges from the graph
    # [(u,v),(v,w),(w,x)...]
    @ensure_valid_state
    def paths_between(
        self, start: str = "vfdpxa", end: str = "VFDPXA"
    ) -> Generator[list[Any] | list[tuple[Any, Any]], None, list[Any] | None]:
        """
        Return all paths of transitions between two states

        Args:
            start: the start state, default="vfdpxa"
            end: the end state, default="VFDPXA"

        Returns:
            a list of paths
        """
        G = self.G

        return nx.all_simple_edge_paths(G, start, end)

    @ensure_valid_state
    def paths_from(
        self, state: str = "vfdpxa"
    ) -> Generator[list[Any] | list[tuple[Any, Any]], None, list[Any] | None]:
        """
        Return all paths of transitions that lead from a given state

        Args:
            state: the state to return paths from, default="vfdpxa"

        Returns:
            a list of paths
        """
        return self.paths_between(start=state, end="VFDPXA")

    @ensure_valid_state
    def paths_to(
        self, state: str = "VFDPXA"
    ) -> Generator[list[Any] | list[tuple[Any, Any]], None, list[Any] | None]:
        """
        Return all paths of transitions that lead to a given state

        Args:
            state: the state to return paths to, default="VFDPXA"

        Returns:
            a list of paths
        """
        return self.paths_between(start="vfdpxa", end=state)

    @property
    def histories(self) -> list:
        """
        A list of all possible case histories traversing the case state space from _vfdpxa_ to _VFDPXA_.
        """
        _H = self.sequences_between(start="vfdpxa", end="VFDPXA")
        H = ["".join(h) for h in _H]
        return H

    # sequences are a list of the labels along edges from the graph
    # ["VPXFDA","XPVAFD"...], ["VAF", "XPV", ], etc.
    def sequences_from(self, state: str = "vfdpxa") -> list[tuple[str]]:
        """
        Return all sequences of transitions that lead from a given state

        Args:
            state: the state to return sequences from

        Returns:
            a list of sequences
        """
        return self.sequences_between(start=state)

    @ensure_valid_state
    def sequences_to(self, state: str) -> list[tuple[str]]:
        """
        Return all sequences of transitions that lead to a given state

        Args:
            state: the state to return sequences to

        Returns:
            a list of sequences

        """
        return self.sequences_between(end=state)

    @ensure_valid_state
    def sequences_between(
        self, start: str = "vfdpxa", end: str = "VFDPXA"
    ) -> list[tuple[str]]:
        """
        Return all sequences of transitions between two states

        Args:
            start: the start state, default="vfdpxa"
            end: the end state, default="VFDPXA"

        Returns:
            a list of sequences
        """
        sequences = []
        for path in self.paths_between(start=start, end=end):
            seq = self.transitions_in_path(path)
            sequences.append(seq)
        return sequences

    def transitions_in_path(self, path: list) -> tuple[str]:
        """
        Return the transitions in a path

        Args:
            path: a list of graph edges

        Returns:
            a tuple of the edge labels
        """
        G = self.G
        # path is a list of (node1,node2) edge tuples
        data = (G.get_edge_data(u, v, "label") for (u, v) in path)
        labels = (d["label"] for d in data)
        seq = tuple(labels)
        return seq

    @ensure_valid_state
    def walk_from(
        self, start: str | None = None, end: str = "VFDPXA"
    ) -> tuple:
        """
        Randomly walk from a given state to a given state

        Args:
            start: the start state, default=None
            end: the end state, default="VFDPXA"

        Returns:
            a tuple of the path and the probabilities of each step
        """
        current = start or "vfdpxa"
        path = []
        probabilities = []
        while current != end:
            neighbors = self.next_state(current)

            p = 0.0
            n = len(neighbors)
            if n:
                p = 1 / n

            # A random walk over the state graph, not a secret.
            next_state = random.choice(neighbors)  # noqa: S311
            step = (current, next_state)
            path.append(step)
            probabilities.append(p)
            current = next_state

        return path, probabilities
