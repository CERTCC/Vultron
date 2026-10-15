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
"""PR-only growth guards: no change adds an overlong spec YAML or Python doc line.

Markdown outside ``docs/`` is held to the 88-character limit by markdownlint's
``MD013`` (PD-10-001). Spec YAML and Python comments and docstrings predate the
limit by thousands of lines and have no linter that takes a baseline, so each
line is its own item (PD-10-002): the guards evaluate the per-line extractors of
:mod:`vultron.metadata.line_length` at the merge base with the base branch and
in the working tree, and fail on each overlong line the branch added. An edited
line is a new line, so the corpus moves toward the limit one touched line at a
time; a line a rename or module split only moved is not new. No count is
committed, so concurrent PRs cannot race on one (#3984).

When no base ref is available the guards skip with the reason; under GitHub
Actions they fail.

Specs: PD-10-002, PD-10-003.
"""

import pytest

from test.architecture import _corpus
from vultron.metadata.line_length import (
    LINE_LIMIT,
    PYTHON_ROOTS,
    SPEC_ROOT,
    added_overlong_lines,
    overlong_python_doc_lines,
    overlong_spec_yaml_lines,
)

_REMEDY = (
    f"Wrap each listed line to {LINE_LIMIT} characters or fewer. Only lines "
    f"this branch added or edited are listed; a line whose overflow is one "
    f"unbreakable token, such as a URL or a pytest node ID, already passes."
)


@pytest.mark.spec_corpus
@pytest.mark.spec("PD-10-003")
def test_no_pr_adds_an_overlong_spec_yaml_line():
    """No spec YAML line over the limit is new since the merge base."""
    check = added_overlong_lines(
        overlong_spec_yaml_lines,
        repo_root=_corpus.REPO_ROOT,
        paths=(SPEC_ROOT,),
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        f"spec YAML line(s) over {LINE_LIMIT} characters", _REMEDY
    )


@pytest.mark.spec("PD-10-003")
def test_no_pr_adds_an_overlong_python_doc_line():
    """No comment or docstring line over the limit is new since the base."""
    roots = tuple(r for r in PYTHON_ROOTS if (_corpus.REPO_ROOT / r).is_dir())
    check = added_overlong_lines(
        overlong_python_doc_lines,
        repo_root=_corpus.REPO_ROOT,
        paths=roots,
    )
    if check.skipped:
        pytest.skip(check.skipped)
    assert not check.added, check.failure_message(
        f"Python comment or docstring line(s) over {LINE_LIMIT} characters",
        _REMEDY,
    )
