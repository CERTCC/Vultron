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
"""Planned behavior for the Case Owner's reinstatement naming the actor (ADR-0199).

Strict-``xfail`` probes for the CM-31 requirements written before the code that
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Use a Strict
``xfail`` for Not-Yet-Implemented Specs", and ``notes/as2-vocabulary-alignment.md``
§ "The Owner Sends Its Removal or Reinstatement".

A CM-31-043 to CM-31-045 probe passes once a test module elsewhere under
``test/`` carries its requirement's ID in a ``@pytest.mark.spec`` marker. CM-31-011
and CM-31-036 already carry markers on tests of today's ``Add(CaseParticipant)``
request, so their probe checks the behavior instead: it passes once the Case
Owner's ``Add(<Actor>)`` naming the actor is recognized. #6465 writes those tests and the pattern, so only
it flips the probes. When a probe XPASSes, ``strict=True`` fails the build and the
builder deletes the probe.
"""

from pathlib import Path

import pytest

from test.architecture._planned_probe import has_behavioral_test
from test.support.objects import make
from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.base.objects.actors import as_Person

_TRACKED = "Tracked by #6465 (the Case Owner's reinstatement names the actor)."

_HERE = Path(__file__)


def _has_behavioral_test(request: pytest.FixtureRequest) -> bool:
    """Return whether another test module marks this probe's spec IDs."""
    return has_behavioral_test(request, _HERE)


@pytest.mark.spec("CM-31-043")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-31-043: no Add(<Actor>) reinstatement to refuse. {_TRACKED}",
)
def test_a_non_owners_reinstatement_is_refused(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CM-31-044")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-31-044: the CASE_MANAGER neither admits the Case Owner's "
        f"Add(<Actor>) nor announces it. {_TRACKED}"
    ),
)
def test_an_admitted_reinstatement_is_ledgered_and_announced(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CM-31-045")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-31-045: no Announce of an Add(<Actor>) for a replica to ignore. {_TRACKED}",
)
def test_a_replica_applies_a_reinstatement_only_from_its_entry(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CM-31-011", "CM-31-036")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-31-011, CM-31-036: no pattern recognizes the Case Owner's "
        f"Add(<Actor>, target=<case>). {_TRACKED}"
    ),
)
def test_the_reinstatement_naming_the_actor_is_recognized() -> None:
    vendor = make(as_Person, id_="https://example.org/vendor")
    reinstatement = make(
        as_Add,
        actor="https://example.org/owner",
        object_=vendor,
        target="https://example.org/cases/1",
        to=["https://example.org/case-manager"],
    )

    assert (
        find_matching_semantics(reinstatement) is not MessageSemantics.UNKNOWN
    )
