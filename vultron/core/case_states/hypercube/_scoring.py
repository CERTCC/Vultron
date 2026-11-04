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

"""Score CVD case histories and states against the desiderata."""

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from vultron.core.case_states.patterns.embargo import (
    can_start_embargo,
    embargo_viable,
)
from vultron.core.case_states.validations import (
    ensure_valid_state_method_wrapper as ensure_valid_state,
    is_valid_history,
)
from vultron.errors import (
    CVDmodelError,
    HistoryValidationError,
    ScoringError,
)


class CVDmodelScoringMixin:
    """History and state scoring methods of :class:`CVDmodel`."""

    if TYPE_CHECKING:
        # The model's state this mixin reads and writes.
        _D: tuple[tuple[str, str], ...]
        H: Any
        H_df: Any
        H_prob: Any
        _rounds_to_cover: Any
        d_cols: Any
        f_d: Any
        state_bad: Any
        state_good: Any
        state_pattern_to_d: Any
        state_pattern_to_not_d: Any
        w_cols: Any

        @property
        def states(self) -> list[str]: ...

        def compute_pagerank(self) -> dict[str, float]: ...

        def transitions_in_path(self, path: list) -> tuple[str]: ...

        def walk_from(
            self, start: str | None = None, end: str = "VFDPXA"
        ) -> tuple: ...

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
                met = int(is_met)

                # simple unweighted history-vs-desiderata columns
                col = "<".join(d)
                row[col] = met
                d_cols.add(col)

                # history-vs-desiderata columns weighted by history likelihood
                col2 = f"w{col}"
                row[col2] = p * met
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
            a, b = k.replace("w", "").split("<")
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
            raise ScoringError(f"Invalid history {h}")  # noqa: B904  # ruff-baseline #3353

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
    def score_state(self, state: str) -> float:
        part = self._part_score_state(state)
        # net = part['plus'] - part['minus']
        net = float(part["plus"])
        return net
