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

"""Architecture invariant: a demo CaseActor client is constructed *bound*.

Under ADR-0072 a ``/datalayer/`` read names an actor, so
``DataLayerClient.dl_path()`` raises ``ValueError`` when the client carries no
``actor_id``.  A scenario that builds its CaseActor client as
``DataLayerClient(base_url=ca_url)`` therefore fails deterministically the first
time any verification step inspects the CaseActor's replica — which is every
containerized run of that scenario.

The unit suite could not catch it.  Every ``test/demo/`` test is marked
``integration`` and deselected by default, and the ones that do run substitute
``MagicMock()`` for the client, where ``MagicMock().dl_path(...)`` happily
returns another mock.  So the green unit suite and the red Demo Integration tier
were both telling the truth about different things.

This test reads the scenario sources instead of running them: it is not marked
``integration``, needs no containers, and fails at the construction site rather
than several hundred lines downstream at the raise.

Issue: #2484 (phase8-datalayerclient-unbound-actor-id-0)
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

#: A target name containing any of these is a CaseActor client: a client whose
#: reads are about the ``case-actor`` actor a dedicated container hosts.
_CASE_ACTOR_NAME_HINTS = ("case_actor_client", "caseactor_client")

#: Scenario ASTs from the shared corpus, keyed by path (TB-13-003).  Built at
#: import time so ``parametrize`` can enumerate the scenarios by name.
_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.all_trees(under=_SCENARIO_DIR)
    if path.name != "__init__.py"
}


def _unbound_case_actor_clients(tree: ast.AST) -> list[str]:
    """Return ``name`` for each unbound CaseActor ``DataLayerClient`` assignment.

    "Unbound" means the constructor call passes no ``actor_id`` keyword.  Only
    direct ``DataLayerClient(...)`` calls are inspected; a scenario that routes
    construction through a helper is that helper's problem, and none do today.
    """
    unbound: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )
        if callee != "DataLayerClient":
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(
            hint in name for name in names for hint in _CASE_ACTOR_NAME_HINTS
        ):
            continue
        if any(kw.arg == "actor_id" for kw in call.keywords):
            continue
        unbound.extend(names)
    return unbound


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_case_actor_client_is_constructed_with_an_actor_id(scenario: Path):
    """Every CaseActor ``DataLayerClient`` must be given an ``actor_id``."""
    unbound = _unbound_case_actor_clients(_SCENARIO_TREES[scenario])
    assert not unbound, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} constructs {unbound} without"
        " actor_id. A /datalayer/ read names an actor (ADR-0072), so"
        " dl_path() raises ValueError on the first verification step that"
        " inspects the CaseActor's replica. Pass"
        " actor_id=case_actor_id_on(<base_url>)."
    )


def test_the_check_can_actually_fail():
    """Guard the guard: the detector must flag a genuinely unbound construction.

    A source-reading ratchet that silently matches nothing is worse than no
    ratchet, because it reports success.
    """
    sample = _corpus.parse_inline(
        "from vultron.demo.utils import DataLayerClient\n"
        "case_actor_client = DataLayerClient(base_url=ca_url)\n"
    )
    assert _unbound_case_actor_clients(sample) == ["case_actor_client"]


def test_dl_path_raises_when_the_client_is_unbound():
    """The failure mode the ratchet above prevents, asserted directly."""
    from vultron.demo.utils import DataLayerClient

    client = DataLayerClient(base_url="http://case-actor:7999/api/v2")
    with pytest.raises(ValueError, match="requires an actor_id"):
        client.dl_path("VulnerabilityCases/")
