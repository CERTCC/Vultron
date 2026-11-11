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
"""Planned behavior for CSAF documents in reports (ADR-0184, CSAF-01 to CSAF-05).

Strict-``xfail`` tests for requirements written before the code that satisfies
them exists; see ``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail``
for Not-Yet-Implemented Specs", and ``notes/csaf-report-content.md`` for the
planned layout.

One probe stands in for every planned requirement: a test module elsewhere
under ``test/`` carries the requirement's ID in a ``@pytest.mark.spec`` marker.
Each tracking issue's acceptance criteria name the behavioral tests it writes,
so the issue that builds a requirement is the only one whose change flips that
requirement's probe. A probe keyed on a module or field name would flip when
an earlier task created the name, and turn that task's build red on a probe it
does not own.

When the behavioral test lands, the probe XPASSes, ``strict=True`` fails the
build, and the builder deletes the probe. That promotion is the point: this
module is a ratchet, not a test of the feature.

CSAF-05-004 already holds, so its test is a real check, not a probe.
"""

import re
from functools import cache
from pathlib import Path

import pytest

from test.architecture import _corpus

_RECORDS = (
    "Tracked by #6093, which waits on #6235 (vulnerability items on a case)."
)


_HERE = Path(__file__).resolve()
_TEST_ROOT = _corpus.REPO_ROOT / "test"
_SPEC_MARKER = re.compile(r"spec\(([^)]*)\)")
_CSAF_ID = re.compile(r"""["'](CSAF-\d{2}-\d{3})["']""")
#: The CSAF Technical Committee keeps its test documents under this path of
#: its repository (CSAF-05-004).
_TC_TEST_DATA = "csaf_2.1/test/"


def _other_modules_mentioning(fragment: str) -> list[tuple[Path, str]]:
    """Return the test modules other than this one whose source holds ``fragment``."""
    return [
        (path, source)
        for path, source in _corpus.sources_mentioning(
            fragment, under=_TEST_ROOT
        )
        if path.resolve() != _HERE
    ]


@cache
def _csaf_ids_marked_elsewhere() -> frozenset[str]:
    """Return the CSAF IDs that a ``spec`` marker in another test module names."""
    return frozenset(
        spec_id
        for _, text in _other_modules_mentioning("CSAF-")
        for marker_args in _SPEC_MARKER.findall(text)
        for spec_id in _CSAF_ID.findall(marker_args)
    )


def _has_behavioral_test(request: pytest.FixtureRequest) -> bool:
    """Return whether another test module marks this probe's spec ID."""
    marker = request.node.get_closest_marker("spec")
    assert marker is not None and marker.args, "a probe needs a spec marker"
    return set(marker.args) <= _csaf_ids_marked_elsewhere()


@pytest.mark.spec("CSAF-03-008")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-008: the case has no vulnerability items. {_RECORDS}",
)
def test_each_csaf_vulnerability_becomes_a_vulnerability_item(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-009")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-009: the case has no case references. {_RECORDS}",
)
def test_each_csaf_reference_becomes_a_case_reference(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-004")
def test_the_suite_never_reads_the_tc_test_documents() -> None:
    readers = [
        str(path.relative_to(_TEST_ROOT))
        for path, _ in _other_modules_mentioning(_TC_TEST_DATA)
    ]
    assert readers == [], (
        f"CSAF-05-004: these test modules name the CSAF TC test data: {readers}"
    )
