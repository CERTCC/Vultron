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
"""Every received embargo handler runs one tree per delivery (CLP-10-005).

ADR-0135: a call to ``execute_with_setup()`` that ``execute()`` reaches through
any use-case or core-services helper counts as its own, and calls on
alternative branches are summed, so Python that chooses between two trees, or
runs a door check or a refusal as a tree of its own, counts as two.  Each
embargo handler's door guards, P/X/A refusal and late-Accept routing are
stages of its one tree (#4642), so every ``execute()`` under
``vultron/core/use_cases/received/embargo/`` reaches exactly one call.

The codebase-wide form of this count is #4645's; this test holds the embargo
package to it now.
"""

import pytest

from test.architecture import _corpus
from test.architecture._use_case_call_graph import _UseCaseCorpus

_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"
_EMBARGO_ROOT = _USE_CASES_ROOT / "received" / "embargo"
_SERVICES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "services"


def _corpus_of(trees: dict) -> _UseCaseCorpus:
    return _UseCaseCorpus(
        trees,
        roots={
            _USE_CASES_ROOT: "vultron.core.use_cases",
            _SERVICES_ROOT: "vultron.core.services",
        },
    )


def _real_corpus() -> _UseCaseCorpus:
    return _corpus_of(
        {
            **dict(_corpus.all_trees(under=_USE_CASES_ROOT)),
            **dict(_corpus.all_trees(under=_SERVICES_ROOT)),
        }
    )


@pytest.mark.spec("CLP-10-005")
def test_every_embargo_handler_reaches_one_tree_run() -> None:
    corpus = _real_corpus()
    counts = {
        f"{module}.{cls}": runs
        for module, _ in corpus.modules_under(_EMBARGO_ROOT)
        for cls, runs in corpus.tree_runs_per_execute(module).items()
    }
    assert counts, "no embargo handler found — corpus drifted?"
    assert {name: n for name, n in counts.items() if n != 1} == {}


def _synthetic(source: str) -> dict[str, int]:
    path = _EMBARGO_ROOT / "synthetic.py"
    corpus = _corpus_of({path: _corpus.parse_inline(source)})
    return corpus.tree_runs_per_execute(
        "vultron.core.use_cases.received.embargo.synthetic"
    )


@pytest.mark.parametrize(
    ("source", "runs"),
    [
        (
            "class UC:\n"
            "    def execute(self):\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            1,
        ),
        (
            "def _door(b):\n"
            "    return b.execute_with_setup(tree=d)\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        _door(self._b)\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
        ),
        (
            "class UC:\n"
            "    def _route(self):\n"
            "        self._b.execute_with_setup(tree=r)\n"
            "    def execute(self):\n"
            "        if late:\n"
            "            return self._route()\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
        ),
    ],
    ids=["one-run", "helper-door-check", "alternative-branch"],
)
def test_the_count_follows_helpers_and_sums_branches(
    source: str, runs: int
) -> None:
    assert _synthetic(source) == {"UC": runs}


def test_a_module_without_execute_counts_nothing() -> None:
    assert _synthetic("def helper():\n    pass\n") == {}
