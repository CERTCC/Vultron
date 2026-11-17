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
"""Planned behavior for the Case Owner's reinstatement Offer (ADR-0199).

Strict-``xfail`` probes for the CM-31 requirements written before the code that
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Use a Strict
``xfail`` for Not-Yet-Implemented Specs", and ``notes/as2-vocabulary-alignment.md``
§ "The Owner Offers a Removal or Reinstatement".

A probe passes once a test module elsewhere under ``test/`` carries its
requirement's ID in a ``@pytest.mark.spec`` marker. #6465 writes those tests, so
only it flips the probes. When a probe XPASSes, ``strict=True`` fails the build
and the builder deletes the probe.
"""

import re
from functools import cache
from pathlib import Path

import pytest

from test.architecture import _corpus

_OFFER = "Tracked by #6465 (the Case Owner offers a reinstatement)."

_HERE = Path(__file__).resolve()
_TEST_ROOT = _corpus.REPO_ROOT / "test"
_SPEC_MARKER = re.compile(r"spec\(([^)]*)\)")
_CM_ID = re.compile(r"""["'](CM-\d{2}-\d{3})["']""")


@cache
def _cm_ids_marked_elsewhere() -> frozenset[str]:
    """Return the CM IDs that a ``spec`` marker in another test module names."""
    return frozenset(
        spec_id
        for path, text in _corpus.sources_mentioning("CM-", under=_TEST_ROOT)
        if path.resolve() != _HERE
        for marker_args in _SPEC_MARKER.findall(text)
        for spec_id in _CM_ID.findall(marker_args)
    )


def _has_behavioral_test(request: pytest.FixtureRequest) -> bool:
    """Return whether another test module marks this probe's spec ID."""
    marker = request.node.get_closest_marker("spec")
    assert marker is not None and marker.args, "a probe needs a spec marker"
    return set(marker.args) <= _cm_ids_marked_elsewhere()


@pytest.mark.spec("CM-31-043")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-31-043: no reinstatement Offer to refuse. {_OFFER}",
)
def test_a_non_owners_reinstatement_offer_is_refused(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CM-31-044")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-31-044: the CASE_MANAGER neither accepts a reinstatement Offer "
        f"nor makes its own Add(<Actor>). {_OFFER}"
    ),
)
def test_an_admitted_offer_is_accepted_and_the_add_made_in_one_act(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CM-31-045")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-31-045: no direct Add(<Actor>) for a replica to ignore. {_OFFER}",
)
def test_a_replica_applies_a_reinstatement_only_from_its_entry(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)
