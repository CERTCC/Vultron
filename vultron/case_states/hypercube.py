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
"""
The `vultron.case_states.hypercube` module contains the CVDmodel class, which represents the state graph of a Coordinated Vulnerability Disclosure case.

Based on
Householder, A. D., and Jonathan Spring.
[A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771).
Tech. Rep. CMU/SEI-2021-SR-021, Software Engineering Institute, Carnegie-Mellon University, Pittsburgh, PA, 2021.
"""

import logging
import random
import re
from itertools import product
from typing import Any, Generator

import networkx as nx
import numpy as np
import pandas as pd

from vultron.case_states.errors import (
    CVDmodelError,
    HistoryValidationError,
    PatternValidationError,
    ScoringError,
    StateValidationError,
    TransitionValidationError,
)
from vultron.case_states.patterns.embargo import (
    can_start_embargo,
    embargo_viable,
)
from vultron.case_states.patterns.explanations import explain
from vultron.case_states.patterns.info import info
from vultron.case_states.patterns.potential_actions import action
from vultron.case_states.patterns.zerodays import zeroday_type
from vultron.case_states.states import pxa, vfd
from vultron.case_states.validations import (
    ensure_valid_state_method_wrapper as ensure_valid_state,
)
from vultron.case_states.validations import (
    is_valid_history,
    is_valid_pattern,
    is_valid_state,
    is_valid_transition,
)

logger = logging.getLogger(__name__)


EVENTS = tuple("VFDPXA")


def _proto_states():
    proto_states = [f"{e.lower()}{e.upper()}" for e in EVENTS]
    return proto_states


def _create_states():
    states = []
    proto_states = _proto_states()
    for seq in product(*proto_states):
        state = "".join(seq)

        try:
            is_valid_state(state)
        except StateValidationError:
            continue

        states.append(state)

    return states


def _create_graph():
    states = _create_states()

    G = nx.DiGraph()
    G.add_nodes_from(states)

    # create edges when the edge is valid
    for s1, s2 in product(G.nodes, G.nodes):
        try:
            is_valid_transition(s1, s2)
        except TransitionValidationError:
            continue

        t = _diffstate(s1, s2)
        G.add_edge(s1, s2, label=t)

    return G


def _diffstate(s1, s2):
    """returns the transition between s1 and s2"""
    try:
        is_valid_transition(s1, s2)
    except TransitionValidationError:
        return None

    diff = [(c1, c2) for c1, c2 in zip(s1, s2) if c1 != c2]
    c1, c2 = diff[0]

    assert c1.upper() == c2.upper()
    return c2.upper()


DESIDERATA = (
    ("V", "P"),
    ("V", "X"),
    ("V", "A"),
    ("F", "P"),
    ("F", "X"),
    ("F", "A"),
    ("D", "P"),
    ("D", "X"),
    ("D", "A"),
    ("P", "X"),
    ("P", "A"),
    ("X", "A"),
)
"""
Taken directly from the [paper](https://doi.org/10.1184/R1/16416771):
 Given (A,B), you prefer histories in which A precedes B over ones in which B precedes A.
"""


class CVDmodel:
    """
    A CVDmodel is a graph of states and transitions between them.
    The model reflects the CVD process and the actions that can be taken at a high level.
    It also has a set of histories that can be scored.
    """

    _D = DESIDERATA

    def __init__(self):
        # the graph of states
        self.G = None

        # the set of histories
        self.H = None
        self.H_prob = None
        self.H_score = None

        self._rounds_to_cover = None
        self.d_cols = None
        self.w_cols = None
        self.H_df = None
        self.S_df = None
        self.f_d = None
        self.d_to_state_pattern = None
        self.state_pattern_to_d = None
        self.not_d_to_state_pattern = None
        self.state_pattern_to_not_d = None
        self.state_good = None
        self.state_bad = None

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
            "successors": list(self.next_state(state)),
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
    def next_state(self, state: str, transition=None):
        if transition is None:
            next_states = list(self.G.successors(state))
            return next_states

        # if you got here transition is not None
        for successor in self.G.successors(state):
            try:
                is_valid_transition(state, successor)
            except TransitionValidationError as e:
                raise CVDmodelError(e)

            edge_data = self.G.get_edge_data(state, successor)
            if edge_data["label"] == transition:
                return successor

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
        current = start
        path = []
        probabilities = []
        while current != end:
            neighbors = list(self.next_state(current))

            p = 0.0
            n = len(neighbors)
            if n:
                p = 1 / n

            next_state = random.choice(neighbors)
            step = (current, next_state)
            path.append(step)
            probabilities.append(p)
            current = next_state

        return path, probabilities

    def _compute_h_frequencies(self):
        h_coverage = {}
        # initialize coverage
        for h in self.H:
            h_coverage[h] = None

        count = 0
        while any([v is None for v in h_coverage.values()]):
            path, probs = self.walk_from(start="vfdpxa")
            h = self.transitions_in_path(path)
            h = "".join(h)

            # compute path probability

            p = np.prod(probs)

            h_coverage[h] = p
            count += 1

        self._rounds_to_cover = count
        return h_coverage

    def _compute_tfidf(self) -> pd.DataFrame:
        """
        Compute tf-idf scores for each desiderata in each history

        Returns:
            a dataframe with tf-idf scores for each desiderata in each history

        """
        df = pd.DataFrame(self.H_df)
        tfidf_cols = []

        assert len(self.d_cols) > 0

        for c in self.d_cols:
            wcol = f"w{c}"

            # total weight of the desiderata across all histories
            # weighted by history frequency
            docfreq = sum(df[wcol])

            numerator = 1 + 1
            denominator = docfreq + 1  # avoid div by 0
            idf = np.log(numerator / denominator) + 1

            tfidf_col = f"tfidf_{c}"
            tfidf_cols.append(tfidf_col)

            # df[c] = 1 when d is present in a history, 0 when absent
            df[tfidf_col] = df[c] * idf

        # total tf-idf is the sum of the scores for individual terms
        df["tfidf"] = df[tfidf_cols].sum(axis=1)
        # we don't need the individual tf-idf cols anymore
        df = df.drop(columns=tfidf_cols)

        # assign ranks and sort by rank
        df["rank"] = df["tfidf"].rank(method="dense")
        df = df.sort_values(by="rank").reset_index(drop=True)

        return df

    def _compute_s_scores(self) -> dict:
        """
        Compute the s scores for each state

        Returns:
            a dict of state: s score
        """
        score = {}
        for s in self.states:
            score[s] = self.score_state(s)
        return score

    def _init_H_df(self) -> pd.DataFrame:
        """
        Initialize the history dataframe

        Returns:
            a dataframe of histories and their scores

        Raises:
            CVDmodelError: if the history probabilities are uninitialized
        """
        # make sure we have the info we need before proceeding
        if self.H_prob is None:
            raise CVDmodelError("History probabilities are uninitialized")

        data = []
        d_cols = set()
        w_cols = set()
        for h, p in self.H_prob.items():
            # h is the history string of six events
            # p is the frequency of that history when we random walk the graph
            row = {"h": h, "p": p}

            # walk the desiderata set for this history
            D_h = self._assess_hist(h)

            for d, is_met in D_h.items():
                # d is a tuple of A,B where A<B
                # is_met is true/false, we want it as an int
                is_met = int(is_met)

                # simple unweighted history-vs-desiderata columns
                col = "<".join(d)
                row[col] = is_met
                d_cols.add(col)

                # history-vs-desiderata columns weighted by history likelihood
                col2 = f"w{col}"
                row[col2] = p * is_met
                w_cols.add(col2)

            data.append(row)

        self.d_cols = sorted(list(d_cols))
        self.w_cols = sorted(list(w_cols))

        df = pd.DataFrame(data)
        return df

    def _compute_f_d(self) -> dict:
        """

        Returns:
            a dict of desiderata: frequency
        """
        _f_d = self.H_df[self.w_cols].sum()

        f_d = {}
        for k, v in _f_d.items():
            k = k.replace("w", "")
            a, b = k.split("<")
            new_k = (a, b)
            f_d[new_k] = v

        return f_d

    def _compute_f_d_orig(self):
        f_d = self.H_df[self.d_cols].mean()
        return f_d

    def _assess_hist(self, h) -> dict:
        """
        Assess a history against the desiderata
        Args:
            h: the history to assess

        Returns:
            a dict of desiderata: is_met

        Raises:
            ScoringError: if the history is invalid
        """
        try:
            is_valid_history(h)
        except HistoryValidationError:
            raise ScoringError(f"Invalid history {h}")

        D_h = {(e1, e2): h.index(e1) < h.index(e2) for (e1, e2) in self._D}
        return D_h

    def score_hist(self, h: str) -> float:
        """
        Compute the score for a given history

        Args:
            h: the history to score

        Returns:
            the score for the history
        """
        # this is basically computing the dot product of
        # D_h dot (1-f_d)
        D_h = self._assess_hist(h)

        score = 0
        for k, v in D_h.items():
            if v:
                score += 1 - self.f_d[k]
        return score

    def d_to_col(self, d):
        # d is a tuple (a,b)
        return "<".join(d)

    def _init_sdf(self):
        data = []
        patcols = set()
        for s in self.states:
            row = {
                "state": s,
                "start_embargo": can_start_embargo(s),
                "embargo_viable": embargo_viable(s),
            }
            good, bad = self._assess_state(s)

            for pat, score in good.items():
                # convert pattern into colname
                k = pat.pattern
                d = self.state_pattern_to_d[k]
                col = self.d_to_col(d)
                row[col] = 1 - score
                patcols.add(col)

            for pat, score in bad.items():
                # convert pattern into colname
                k = pat.pattern
                d = self.state_pattern_to_not_d[k]
                col = self.d_to_col(d)
                row[col] = -(1 - score)
                patcols.add(col)

            data.append(row)

        # convert the columns into a list
        patcols = list(patcols)

        df = pd.DataFrame(data).fillna(0)
        df = df.set_index("state")

        # sum across all columns to get net state score
        df["score"] = df[patcols].sum(axis=1)
        df["rank"] = df["score"].rank(method="dense")

        # pagerank returns a dict of state: pr_score so convert to series before adding to df
        pr = self.compute_pagerank()
        prs = pd.Series(pr)
        df["pagerank"] = prs

        return df

    @ensure_valid_state
    def _assess_state(self, state):
        """
        Assess a state against the desiderata
        Args:
            state: the state to assess

        Returns:
            a tuple of (good, bad) patterns
        """
        plus = []
        for p, score in self.state_good.items():
            if p.match(state):
                plus.append((p, score))
        minus = []
        for p, score in self.state_bad.items():
            if p.match(state):
                minus.append((p, score))
        return dict(plus), dict(minus)

    @ensure_valid_state
    def _part_score_state(self, state):
        good, bad = self._assess_state(state)
        plus = sum([1 - g for g in good.values()])
        minus = sum([1 - g for g in bad.values()])

        res = {"plus": plus, "minus": minus}
        return res

    @ensure_valid_state
    def score_state(self, state):
        part = self._part_score_state(state)
        # net = part['plus'] - part['minus']
        net = part["plus"]
        return net

    def _construct_good_patterns(self):
        # construct a state regex pattern to correspond to each desiderata
        idx = self.idx

        g = {}
        for d in self._D:
            # a desiderata is a preference that one event precedes another
            # a and b are an ordered pair of transitions
            (a, b) = d

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
            raise CVDmodelError(e)

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
            logger.error(
                f"Invalid transition from {from_state} to {to_state}: {e}"
            )
            raise e

        curr_score = self.score_state(from_state)
        next_score = self.score_state(to_state)
        delta = next_score - curr_score
        return delta

    def compute_pagerank(self) -> dict:
        """
        Compute the pagerank of each state in the model.
        Runs the NetworkX pagerank algorithm on the model graph 10000 times.
        Because the model is a directed graph, we need to add a wraparound link so that the pagerank algorithm can walk
        from the end back to the beginning naturally.

        Returns:
            a dict of state: pagerank

        """
        # copy the graph since we're going to modify it
        G = nx.DiGraph(self.G)

        # add a wraparound link
        # this allows page rank to walk from the end back to the beginning naturally
        # and avoids biasing the pagerank algorithm against the early states
        G.add_edge("VFDPXA", "vfdpxa")

        # compute pagerank
        pr = nx.pagerank(G, max_iter=10000)

        # return a dict of node: pr
        return pr


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


if __name__ == "__main__":
    main()
