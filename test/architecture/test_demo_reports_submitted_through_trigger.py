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

"""Architecture gate (DEMOMA-05-001, CBT-01-005): no demo builds a report
submission or a case introduction itself.

A demo that builds ``Offer(VulnerabilityReport)`` with
``rm_submit_report_activity`` and posts it into the receiver's inbox skips
the reporter's ``submit-report`` trigger.  The trigger is where the reporter
writes the pending ``ReportCaseLink`` naming the receiver, so the reporter
then refuses the receiver's ``Create(VulnerabilityCase)`` introduction on
the unanchored route (CBT-01-011).  A demo that builds that
``Create(VulnerabilityCase)`` with ``create_case_activity`` spoofs the
receiver's introduction.  Both stayed hidden because each demo still got the
reporter a case another way (#4675).

Submit through ``vultron.demo.helpers.workflow.reporter_submits_report`` and
check the introduction with ``verify_reporter_trusts_introduction``.  This
covers all of ``vultron/demo/``, exchange demos included: their exemption
from the mail-carrying rule does not extend to forging these two activities.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_DEMO_DIR = _corpus.REPO_ROOT / "vultron" / "demo"

#: The wire factories that build the two activities only a trigger may send.
_FORGED_FACTORIES = frozenset(
    {"rm_submit_report_activity", "create_case_activity"}
)


def _forged_activity_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, factory)`` for every call to a forbidden factory."""
    return [
        (node.lineno, name)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (name := _corpus.callee_name(node.func) or "") in _FORGED_FACTORIES
    ]


def _demo_trees() -> list[tuple[Path, ast.AST]]:
    return list(_corpus.all_trees(_DEMO_DIR))


def test_demo_corpus_is_non_empty() -> None:
    """A zero-target gate proves nothing."""
    assert _demo_trees(), f"no demo modules under {_DEMO_DIR}"


@pytest.mark.spec("DEMOMA-05-001")
@pytest.mark.parametrize(
    ("path", "tree"),
    _demo_trees(),
    ids=lambda v: str(v.relative_to(_DEMO_DIR)) if isinstance(v, Path) else "",
)
def test_demo_does_not_forge_a_submission_or_introduction(
    path: Path, tree: ast.AST
) -> None:
    offenders = _forged_activity_calls(tree)
    assert not offenders, (
        f"{path.relative_to(_DEMO_DIR)} builds an activity only a trigger may"
        " send, at "
        + ", ".join(f"line {ln} ({name})" for ln, name in offenders)
        + "; submit through reporter_submits_report and check the receiver's"
        " introduction with verify_reporter_trusts_introduction"
        " (DEMOMA-05-001, CBT-01-005, #4675)."
    )


def test_gate_detects_both_forged_activities() -> None:
    """The detector fires on the shapes it exists to forbid."""
    source = (
        "def step(c):\n"
        "    offer = rm_submit_report_activity(report, actor=f, to=v)\n"
        "    create = factories.create_case_activity(case, actor=v, to=[f])\n"
        "    post_to_inbox_and_wait(c, v, offer)\n"
    )
    assert [
        name
        for _, name in _forged_activity_calls(_corpus.parse_inline(source))
    ] == ["rm_submit_report_activity", "create_case_activity"]
