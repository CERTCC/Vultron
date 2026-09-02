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
"""Security-significant call-out gate default audit guard (#2676, BT-23-012).

ADR-0076 established a project-wide exception to the ceiling/floor rule
(BT-23-002/006/007): a call-out gate whose permissive backend would let a party
other than the Case Owner *unilaterally* cause canonical case-state adoption or
embargo teardown on the received side MUST default to the conservative (floor)
backend regardless of its stochastic ``p`` (BT-23-012). Issue #2676 audited
every ``CallOutBackendFactory`` field across all core bundles against that
criterion and found exactly two qualifying gates — both already flipped under
ADR-0076 (RSH-07-001, RSH-07-002).

This module is the regression guard for that audit. It fails in **both**
directions:

- if a non-qualifying gate is accidentally hardened to the blocking
  :class:`RequireCaseOwnerApprovalNode` default, or
- if a newly-added gate silently adopts the blocking default without being
  reflected in the known security-significant set here.

It also pins the two spec-mandated look-alike embargo gates permissive, so a
future reader auditing for ``AlwaysSucceed`` on an authorization-flavored gate
does not "harden" them (see ``notes/call-out-configuration.md`` §
"Security-Significant Gate Audit").
"""

import dataclasses
import importlib
import pkgutil
from typing import Any

import pytest
from py_trees.common import Status

from vultron.core.behaviors.call_out import bundles as core_bundles
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
)
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
)
from vultron.core.behaviors.call_out.nodes import RequireCaseOwnerApprovalNode

# The exact set of (singleton, field) pairs whose DETERMINISTIC default is the
# conservative blocking backend. Per the #2676 audit this is the two
# received-side status gates and nothing else (RSH-07-001, RSH-07-002).
EXPECTED_CONSERVATIVE_GATES = {
    ("STATUS_AUTHORIZATION_DETERMINISTIC", "status_adoption_gate_factory"),
    (
        "STATUS_AUTHORIZATION_DETERMINISTIC",
        "embargo_teardown_authorization_gate_factory",
    ),
}

# Look-alike embargo gates that share surface structure with the qualifying set
# but do NOT qualify, so they intentionally keep a permissive (SUCCESS) default.
# - CaseOwnerApprovesEmbargoResponse: EMB-15-001 (MUST) requires accept-by-default;
#   accepting an embargo is the protective direction, not teardown.
# - EmbargoExitPolicyGuard: trigger-side voluntary exit (self-authorized), gated
#   behind a fail-closed reason Selector; EMB-14-002 frames it as an optional veto.
PERMISSIVE_EMBARGO_LOOKALIKE_FIELDS = (
    "case_owner_approves_embargo_response_factory",
    "embargo_exit_policy_guard_factory",
)


def _core_deterministic_singletons() -> dict[str, Any]:
    """Collect every core ``<DOMAIN>_DETERMINISTIC`` bundle singleton.

    Walks the ``bundles`` *package modules* directly (not the ``__init__``
    namespace), so a newly-added bundle module is covered by the audit guard
    below even if its author forgets to re-export it from
    ``bundles/__init__.py``.  This matches the #2676 audit's scope claim — every
    ``CallOutBackendFactory`` field across all bundles under ``.../bundles/``.
    """
    out: dict[str, Any] = {}
    for mod_info in pkgutil.iter_modules(core_bundles.__path__):
        module = importlib.import_module(
            f"{core_bundles.__name__}.{mod_info.name}"
        )
        for name in dir(module):
            if not name.endswith("_DETERMINISTIC"):
                continue
            obj = getattr(module, name)
            # Frozen bundle *instances* only (skip classes / non-dataclasses).
            # Keyed by singleton name so a re-import from another module dedups.
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                out[name] = obj
    return out


def test_at_least_the_known_bundles_are_discovered():
    """Sanity: discovery finds the status + embargo bundles it must classify."""
    names = set(_core_deterministic_singletons())
    assert "STATUS_AUTHORIZATION_DETERMINISTIC" in names
    assert "EMBARGO_DETERMINISTIC" in names


@pytest.mark.spec("RSH-07-001")
@pytest.mark.spec("RSH-07-002")
@pytest.mark.spec("BT-23-012")
def test_conservative_default_set_is_exactly_the_two_status_gates():
    """Only the two received-side status gates default to RequireCaseOwnerApproval.

    Polices the security-significant conservative default specifically —
    :class:`RequireCaseOwnerApprovalNode` — not ``AlwaysFail``, which is a
    legitimate ceiling/floor default for many operational gates (BT-23-006).
    Fails if a non-security-significant gate is hardened to
    ``RequireCaseOwnerApprovalNode``, or if a new gate adopts it without
    updating EXPECTED_CONSERVATIVE_GATES (which must be a deliberate, reviewed
    classification per BT-23-012).
    """
    found: set[tuple[str, str]] = set()
    for singleton_name, singleton in _core_deterministic_singletons().items():
        for f in dataclasses.fields(singleton):
            node = getattr(singleton, f.name)(f.name)
            if isinstance(node, RequireCaseOwnerApprovalNode):
                found.add((singleton_name, f.name))
    assert found == EXPECTED_CONSERVATIVE_GATES


@pytest.mark.spec("RSH-07-001")
@pytest.mark.spec("RSH-07-002")
def test_status_gates_conservative_default_blocks():
    """Conservative path: both status gates tick FAILURE by default (block)."""
    for f in dataclasses.fields(STATUS_AUTHORIZATION_DETERMINISTIC):
        node = getattr(STATUS_AUTHORIZATION_DETERMINISTIC, f.name)(f.name)
        node.tick_once()
        assert node.status == Status.FAILURE


@pytest.mark.spec("EMB-15-001")
@pytest.mark.spec("EMB-14-002")
def test_embargo_lookalike_gates_stay_permissive():
    """Permissive path: the two spec-mandated look-alike gates tick SUCCESS.

    Locks in the #2676 finding that these must NOT be flipped conservative
    (EMB-15-001 accept-by-default; EMB-14-002 trigger-side optional veto).
    """
    for field_name in PERMISSIVE_EMBARGO_LOOKALIKE_FIELDS:
        node = getattr(EMBARGO_DETERMINISTIC, field_name)(field_name)
        node.tick_once()
        assert node.status == Status.SUCCESS
