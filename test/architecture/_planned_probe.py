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
"""Shared reader for the marker-presence strict-``xfail`` probes.

A ``*_planned.py`` probe holds the place of a requirement whose behavioral test
is not written yet (``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail``
for Not-Yet-Implemented Specs"). It passes once a test module other than its own
carries the requirement's ID in a ``@pytest.mark.spec`` marker, read with the
same AST reader ``spec-coverage`` uses, so a marker quoted in a docstring or a
comment does not flip it.
"""

from functools import cache
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.marked_tests import marked_spec_ids

_TEST_ROOT = _corpus.REPO_ROOT / "test"


@cache
def _ids_marked_outside(prefix: str, probe_file: Path) -> frozenset[str]:
    """Return the *prefix* IDs a ``spec`` marker names outside *probe_file*."""
    return frozenset(
        spec_id
        for path, text in _corpus.sources_mentioning(prefix, under=_TEST_ROOT)
        if path.resolve() != probe_file
        for spec_id in marked_spec_ids(text, str(path))
        if spec_id.startswith(prefix)
    )


def has_behavioral_test(
    request: pytest.FixtureRequest, probe_file: Path
) -> bool:
    """Return whether another test module marks every ID this probe names."""
    marker = request.node.get_closest_marker("spec")
    assert marker is not None and marker.args, "a probe needs a spec marker"
    ids = set(marker.args)
    marked: set[str] = set()
    for prefix in {spec_id.split("-", 1)[0] + "-" for spec_id in ids}:
        marked |= _ids_marked_outside(prefix, probe_file.resolve())
    return ids <= marked
