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

"""The :class:`CVDmodel` state graph of a Coordinated Vulnerability Disclosure case."""

import logging
import re
from typing import Any

import networkx as nx
import pandas as pd

from vultron.core.case_states.hypercube._navigation import (
    CVDmodelNavigationMixin,
)
from vultron.core.case_states.hypercube._scoring import CVDmodelScoringMixin
from vultron.core.case_states.hypercube.graph import DESIDERATA, _create_graph
from vultron.core.case_states.validations import (
    ensure_valid_state_method_wrapper as ensure_valid_state,
    is_valid_pattern,
    is_valid_transition,
)
from vultron.errors import (
    CVDmodelError,
    PatternValidationError,
    TransitionValidationError,
)

logger = logging.getLogger(__name__)


class CVDmodel(CVDmodelNavigationMixin, CVDmodelScoringMixin):
    """
    A CVDmodel is a graph of states and transitions between them.
    The model reflects the CVD process and the actions that can be taken at a high level.
    It also has a set of histories that can be scored.
    """

    _D = DESIDERATA

    def __init__(self):
        # the graph of states
        self.G: Any = None

        # the set of histories
        self.H: Any = None
        self.H_prob: Any = None
        self.H_score: Any = None

        self._rounds_to_cover: Any = None
        self.d_cols: Any = None
        self.w_cols: Any = None
        self.H_df: Any = None
        self.S_df: Any = None
        self.f_d: Any = None
        self.d_to_state_pattern: Any = None
        self.state_pattern_to_d: Any = None
        self.not_d_to_state_pattern: Any = None
        self.state_pattern_to_not_d: Any = None
        self.state_good: Any = None
        self.state_bad: Any = None

        self._setup()

    def _setup(self):
        """
        Setup the model once it has been instantiated
        """
        # create the graph of states
        self.G = _create_graph()

        # walk the graph to collect histories
        self.H = self.histories

        # compute the probabilities of each history
        self.H_prob = self._compute_h_frequencies()

        # build a dataframe of what you have so far
        self.H_df = self._init_H_df()

        # once you have a dataframe you can compute
        # frequencies of individual desiderata weighted
        # by the frequencies of the histories in which
        # they occur
        self.f_d = self._compute_f_d()

        # add a column to our history data for h_scores
        self.H_df = self._compute_tfidf()

        # we need to turn our desiderata into state patterns
        # start with computing the position of each element
        # in our state naming convention
        self.idx = self._construct_index()

        # now turn the desiderata into state patterns
        self.d_to_state_pattern = self._construct_good_patterns()
        # invert the lookup too
        self.state_pattern_to_d = {
            v: k for k, v in self.d_to_state_pattern.items()
        }

        self.not_d_to_state_pattern = self._construct_bad_patterns()
        # invert the lookup too
        self.state_pattern_to_not_d = {
            v: k for k, v in self.not_d_to_state_pattern.items()
        }

        self.state_good = self._build_good()
        self.state_bad = self._build_bad()

        # self.S_score = self._compute_s_scores()
        # construct a dataframe for states
        self.S_df = self._init_sdf()

    def _construct_good_patterns(self):
        # construct a state regex pattern to correspond to each desiderata
        idx = self.idx

        g = {}
        for d in self._D:
            # a desiderata is a preference that one event precedes another
            # a and b are an ordered pair of transitions
            a, b = d

            # start with a wildcard pattern
            pat = list("......")

            # map a and b to their expected positions in the pattern
            idx1 = idx[a]
            idx2 = idx[b]

            # a precedes b is desired
            # which means we want states where a is capitalized and b is lowercase
            pat[idx1] = a.upper()
            pat[idx2] = b.lower()

            # reassemble the pattern characters into a string
            pat = "".join(pat)
            g[d] = pat

        return g

    def _construct_bad_patterns(self):
        g = self._construct_good_patterns()

        _b = {(b, a): v.swapcase() for (a, b), v in g.items()}
        return _b

    def _build_good(self):
        g = self._construct_good_patterns()
        f_d = self.f_d

        # convert f_d into regex patterns
        _g = {re.compile(g[k]): v for k, v in f_d.items()}

        return _g

    def _build_bad(self):
        g = self._construct_good_patterns()
        f_d = self.f_d

        # bad just inverts the pattern of good
        _b = {re.compile(g[k].swapcase()): (1 - v) for k, v in f_d.items()}

        return _b

    def _construct_index(self):
        # build a simple index of which position vfdpxa appear in the string
        _idx = {c: i for i, c in enumerate("vfdpxa")}
        idx = {}
        for k, v in _idx.items():
            k_upper = k.upper()
            idx[k] = v
            idx[k_upper] = v

        assert len(idx) == 12
        return idx

    def state_adjacency_matrix(self) -> pd.DataFrame:
        """
        Return the state adjacency matrix for the model

        Returns:
            a dataframe of the state adjacency matrix
        """
        G = self.G
        rows = G.nodes()
        cols = rows
        df = pd.DataFrame(
            nx.linalg.adjacency_matrix(G).todense(), index=rows, columns=cols
        )
        return df

    def state_transition_matrix(self) -> pd.DataFrame:
        """
        Return the state transition matrix for the model
        Returns:
            a dataframe of the state transition matrix
        """
        adj_df = self.state_adjacency_matrix()

        df = pd.DataFrame(adj_df)
        # normalize adjacency by the number of next hops
        df = df.div(df.sum(axis=1), axis=0).fillna(0)
        return df

    def find_states(self, pat: str) -> list:
        """
        Find states that match a given pattern
        Args:
            pat: a regex pattern to match

        Returns:
            a list of states that match the pattern

        Raises:
            CVDmodelError: if the pattern is invalid
        """
        try:
            is_valid_pattern(pat)
        except PatternValidationError as e:
            raise CVDmodelError(e)  # noqa: B904  # ruff-baseline #3353

        matches = []
        for state in self.states:
            if re.match(pat, state):
                matches.append(state)
        return matches

    @ensure_valid_state
    def move_score(self, from_state: str, to_state: str) -> float:
        """
        Compute the score of moving from one state to another
        Args:
            from_state: The state to move from
            to_state: The state to move to

        Returns:
            the score of the move
        """
        try:
            is_valid_transition(from_state, to_state)
        except TransitionValidationError as e:
            logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "Invalid transition from %s to %s: %s", from_state, to_state, e
            )
            raise

        curr_score = self.score_state(from_state)
        next_score = self.score_state(to_state)
        delta = next_score - curr_score
        return delta

    def compute_pagerank(self) -> dict[str, float]:
        """
        Compute the pagerank of each state in the model.
        Runs the NetworkX pagerank algorithm on the model graph 10000 times.
        Because the model is a directed graph, we need to add a wraparound link so that the pagerank algorithm can walk
        from the end back to the beginning naturally.

        Returns:
            a dict of state: pagerank

        """
        # copy the graph since we're going to modify it
        G: nx.DiGraph = nx.DiGraph(self.G)

        # add a wraparound link
        # this allows page rank to walk from the end back to the beginning naturally
        # and avoids biasing the pagerank algorithm against the early states
        G.add_edge("VFDPXA", "vfdpxa")

        # compute pagerank
        pr = nx.pagerank(G, max_iter=10000)

        # return a dict of node: pr
        return {str(node): float(score) for node, score in pr.items()}


def main():
    m = CVDmodel()
    print("## Histories")
    for h in m.histories:
        print(f"- {h} {m.score_hist(h)}")
    print("## States")
    for s in m.states:
        print(f"- {s} {m.score_state(s)}")

    for layer in nx.topological_generations(m.G):
        print(layer)

    print("## Pagerank")
    pr = m.compute_pagerank()
    for k, v in pr.items():
        print(f"- {k} {v}")
