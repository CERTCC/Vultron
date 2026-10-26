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
"""The pass rule applied to two navs."""

from __future__ import annotations

from test.metadata.docs.nav_usability._fixtures import (
    F,
    S,
    _results,
)
from vultron.metadata.docs import nav_usability as nu


class TestTally:
    def test_no_worse_passes(self):
        verdict = nu.tally(
            _results("b", {"T1": [S], "T2": [F]}),
            _results("p", {"T1": [F], "T2": [S]}),
        )
        assert (
            verdict.passed
            and verdict.worse == ["T1"]
            and verdict.better == ["T2"]
        )

    def test_worse_fails(self):
        verdict = nu.tally(
            _results("b", {"T1": [S], "T2": [S]}),
            _results("p", {"T1": [S], "T2": [F]}),
        )
        assert not verdict.passed

    def test_stall_fails_even_when_better(self):
        verdict = nu.tally(
            _results("b", {"T1": [F]}),
            _results("p", {"T1": [S], "T2": [F]}, stall="T2"),
        )
        assert not verdict.passed and verdict.stalls == ["T2"]

    def test_repeated_runs_average(self):
        verdict = nu.tally(
            _results("b", {"T1": [S, F]}),
            _results("p", {"T1": [S, S]}),
        )
        assert verdict.better == ["T1"]
