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
"""Architecture test: every ``ActivityPattern`` is built in ``_instances.py``.

A registry module that builds its own pattern for a wire form keeps a second
copy of that form, which can drift from the one ``_instances.py`` defines, and
a reader looking for the wire forms does not find it there (VAM-01-002,
VAM-01-002b).

Spec: VAM-01-002, VAM-01-002b
"""

import ast

import pytest

from test.architecture import _corpus

_HOME = "vultron/wire/as2/extractor/_instances.py"


def _pattern_constructions() -> list[str]:
    """Return ``path:line`` for each ``ActivityPattern(...)`` call outside its home."""
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "ActivityPattern(", under=_corpus.REPO_ROOT / "vultron"
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        if rel == _HOME:
            continue
        sites.extend(
            f"{rel}:{_corpus.node_line(node)}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == "ActivityPattern"
        )
    return sites


@pytest.mark.spec("VAM-01-002", "VAM-01-002b")
def test_activity_patterns_are_built_only_in_instances() -> None:
    """No module other than ``_instances.py`` constructs an ``ActivityPattern``."""
    assert _pattern_constructions() == []


def test_the_scan_sees_the_home_module() -> None:
    """The scan's prefilter finds ``_instances.py``, so an empty result is real."""
    homes = [
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, _ in _corpus.files_mentioning(
            "ActivityPattern(", under=_corpus.REPO_ROOT / "vultron"
        )
    ]
    assert _HOME in homes
