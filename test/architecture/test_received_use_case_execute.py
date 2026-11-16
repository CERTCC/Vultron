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
"""A received use case's ``execute()`` builds its tree and runs it, nothing more.

The rules about what a received ``execute()`` may hold besides building and
running its one tree (ADR-0195, CLP-10-005).  Each test here asks one
question of every received use case that runs a tree, over the same
transitive walk the CLP-10-005 and CLP-10-020 ratchets use
(:mod:`test.architecture._use_case_call_graph`).

- **No refusal before the tree runs (CLP-10-007, ARCH-10-001).**  A
  slot a message's meaning requires (its case id, its inline object) is a
  required slot of its event subtype, so a message without it fails event
  construction in the inbox's extraction step and never reaches a use case
  (ADR-0032).  An ``execute()`` that returns ``HandlerResult.refused(...)``
  itself, or reaches an indexed helper that does, decides a refusal outside
  the tree.  There is no exemption set: a use case that runs no tree at all
  (``UnknownUseCase``) is outside this rule and is named in CLP-10-005's
  exact ``RUNS_NO_TREE`` set instead.
  A refusal a nested reader returns after the run is read from the run and
  is not this rule's (#6494 turns those into node declarations).
"""

from collections.abc import Mapping

import pytest

from test.architecture import _corpus
from test.architecture._use_case_call_graph import (
    INDEXED_ROOTS,
    RECEIVED_ROOT,
    _UseCaseCorpus,
    build_use_case_corpus,
)


def _received_refusals(corpus: _UseCaseCorpus) -> dict[str, list[str]]:
    """The returned refusals of every received ``execute()`` that runs a tree."""
    found: dict[str, list[str]] = {}
    for module, _ in corpus.modules_under(RECEIVED_ROOT):
        runs = corpus.tree_runs_per_execute(module)
        for cls, refusals in corpus.refusals_per_execute(module).items():
            if runs.get(cls, 0):
                found[f"{module}.{cls}"] = refusals
    return found


@pytest.mark.spec("CLP-10-007")
def test_no_received_execute_refuses_before_its_tree_runs() -> None:
    """No received ``execute()`` that runs a tree returns a refusal itself."""
    refusals = _received_refusals(build_use_case_corpus())
    assert refusals, "corpus drifted: no received execute() runs a tree"
    violations = {name: sites for name, sites in refusals.items() if sites}
    assert not violations, (
        "received execute() methods returning HandlerResult.refused(...)"
        " outside their tree — make a missing slot a required slot of the"
        " event subtype, so extraction refuses it (ARCH-10-001, ADR-0032),"
        " and leave every other refusal to the tree (ADR-0195):\n"
        + "\n".join(
            f"  {name}: {', '.join(sites)}"
            for name, sites in sorted(violations.items())
        )
    )


# ---------------------------------------------------------------------------
# Detector self-tests on synthetic sources
# ---------------------------------------------------------------------------

_CORE = _corpus.REPO_ROOT / "vultron" / "core"


def _synthetic_refusals(
    source: str, others: Mapping[str, str] | None = None
) -> dict[str, list[str]]:
    """:func:`_received_refusals` over a synthetic received module.

    *others* adds modules beside it, keyed by path relative to
    ``vultron/core/``.
    """
    files = {"use_cases/received/synthetic.py": source, **(others or {})}
    return _received_refusals(
        _UseCaseCorpus(
            {
                _CORE / rel: _corpus.parse_inline(src)
                for rel, src in files.items()
            },
            roots=INDEXED_ROOTS,
        )
    )


_UC = "vultron.core.use_cases.received.synthetic.UC"


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return HandlerResult.refused('no case')\n"
            "        return run_received_tree(t)\n",
            True,
            id="pre-tree-refusal",
        ),
        pytest.param(
            "def _check(r):\n"
            "    if r.case_id is None:\n"
            "        return HandlerResult.refused('no case')\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        if (no := _check(self._r)) is not None:\n"
            "            return no\n"
            "        return run_received_tree(t)\n",
            True,
            id="refusal-in-a-helper",
        ),
        pytest.param(
            "class UC:\n"
            "    def _check(self):\n"
            "        return HandlerResult.refused('no case')\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return self._check()\n"
            "        return run_received_tree(t)\n",
            True,
            id="refusal-in-a-self-method",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        no = HandlerResult.refused('no case')\n"
            "        if self._r.case_id is None:\n"
            "            return no\n"
            "        return run_received_tree(t)\n",
            True,
            id="assigned-then-returned",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        return (\n"
            "            HandlerResult.refused('no case')\n"
            "            if self._r.case_id is None\n"
            "            else run_received_tree(t)\n"
            "        )\n",
            True,
            id="conditional-expression",
        ),
        pytest.param(
            "from vultron.core.models.use_case_result import (\n"
            "    HandlerResult as HR,\n"
            ")\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return HR.refused('no case')\n"
            "        return run_received_tree(t)\n",
            True,
            id="aliased-import",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        no: HandlerResult = HandlerResult.refused('no case')\n"
            "        if self._r.case_id is None:\n"
            "            return no\n"
            "        return run_received_tree(t)\n",
            True,
            id="annotated-then-returned",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        if (no := HandlerResult.refused('x')) and self._r.bad:\n"
            "            return no\n"
            "        return run_received_tree(t)\n",
            True,
            id="walrus-then-returned",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return HandlerResult(\n"
            "                disposition=HandlerDisposition.REFUSED,\n"
            "                reason='no case',\n"
            "            )\n"
            "        return run_received_tree(t)\n",
            True,
            id="constructed-with-refused-disposition",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return HandlerResult.no_use_case_found('x')\n"
            "        return run_received_tree(t)\n",
            True,
            id="no-use-case-found",
        ),
        pytest.param(
            "from vultron.core.models import use_case_result\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return use_case_result.HandlerResult.refused('x')\n"
            "        return run_received_tree(t)\n",
            True,
            id="module-qualified",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        return (\n"
            "            self._r.case_id is None and HandlerResult.refused('x')\n"
            "        ) or run_received_tree(t)\n",
            True,
            id="boolean-expression",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        self._no = HandlerResult.refused('no case')\n"
            "        if self._r.case_id is None:\n"
            "            return self._no\n"
            "        return run_received_tree(t)\n",
            True,
            id="attribute-then-returned",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        if self._r.case_id is None:\n"
            "            return HandlerResult.skipped('nothing to do')\n"
            "        return run_received_tree(t)\n",
            False,
            id="a-skip-is-not-a-refusal",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        return run_received_tree(tree_for(self._r))\n",
            False,
            id="tree-decides",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        def read(outcome):\n"
            "            return HandlerResult.refused('read from the run')\n"
            "        return run_received_tree(t, reader=read)\n",
            False,
            id="nested-reader-is-not-the-walks",
        ),
    ],
)
def test_the_detector_finds_a_returned_refusal(
    source: str, flagged: bool
) -> None:
    refusals = _synthetic_refusals(source)
    assert _UC in refusals
    assert bool(refusals[_UC]) is flagged


def test_the_detector_follows_an_imported_helper() -> None:
    refusals = _synthetic_refusals(
        "from ._helpers import check\n"
        "class UC:\n"
        "    def execute(self):\n"
        "        if (no := check(self._r)) is not None:\n"
        "            return no\n"
        "        return run_received_tree(t)\n",
        {
            "use_cases/received/_helpers.py": (
                "def check(r):\n    return HandlerResult.refused('no case')\n"
            )
        },
    )
    assert refusals[_UC] == ["vultron.core.use_cases.received._helpers:2"]


def test_a_use_case_that_runs_no_tree_is_out_of_scope() -> None:
    """Refusing with no tree is CLP-10-005's ``RUNS_NO_TREE``, not this rule."""
    refusals = _synthetic_refusals(
        "class UC:\n"
        "    def execute(self):\n"
        "        return HandlerResult.refused('unrecognized')\n"
    )
    assert _UC not in refusals
